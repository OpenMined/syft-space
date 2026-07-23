"""Credits persistence: the CreditsLedger unit-of-work + standalone repos.

The money path (balances + entries + invoices) goes through CreditsLedger —
an async context manager that hands all three repos one shared session and
commits (or rolls back) their writes as a single transaction:

    async with CreditsLedger(db) as ledger:
        ok = await ledger.balances.atomic_deduct(email, amount)
        if not ok:
            raise ...
        ledger.entries.insert(entry)
        await ledger.commit()

If an exception leaves the block, everything rolls back — including a
constraint violation on the idempotency UNIQUE, which is how replayed
debits/refunds stay side-effect-free.

Wallets and space credit tokens are low-frequency CRUD and use plain
own-session repositories.
"""

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from syft_station.components.credits.entities import (
    Invoice,
    InvoiceStatus,
    LedgerEntry,
    SpaceCreditToken,
    UserBalance,
    Wallet,
)
from syft_station.components.shared.database import AsyncBaseRepository, AsyncDatabase

# Statuses a webhook may settle from. Anything else is already terminal.
_SETTLABLE = (InvoiceStatus.PENDING.value, InvoiceStatus.PROCESSING.value)


class UserBalanceRepository:
    """Session-bound queries and atomic mutations for UserBalance rows."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_email: str) -> UserBalance | None:
        statement = select(UserBalance).where(UserBalance.user_email == user_email)
        result = await self.session.exec(statement)
        return result.first()

    async def upsert_credit(self, user_email: str, amount: float) -> UserBalance:
        """Add credit to a user's balance, creating the row if missing."""
        existing = await self.get(user_email)
        now = datetime.now(UTC)
        if existing:
            existing.balance += amount
            existing.updated_at = now
            self.session.add(existing)
            return existing
        row = UserBalance(user_email=user_email, balance=amount)
        self.session.add(row)
        return row

    async def atomic_deduct(self, user_email: str, amount: float) -> bool:
        """Race-free check-and-decrement. False ⇒ insufficient balance.

        A single conditional UPDATE — concurrent debits can never drive the
        balance negative, and there is no check-then-act window.
        """
        stmt = (
            update(UserBalance)
            .where(
                UserBalance.user_email == user_email,
                UserBalance.balance >= amount,
            )
            .values(
                balance=UserBalance.balance - amount,
                updated_at=datetime.now(UTC),
            )
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0

    async def atomic_restore(self, user_email: str, amount: float) -> None:
        """Give a debited amount back (refund/reversal)."""
        stmt = (
            update(UserBalance)
            .where(UserBalance.user_email == user_email)
            .values(
                balance=UserBalance.balance + amount,
                updated_at=datetime.now(UTC),
            )
        )
        await self.session.exec(stmt)


class LedgerEntryRepository:
    """Session-bound access to the append-only spend ledger."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def insert(self, entry: LedgerEntry) -> LedgerEntry:
        """Stage an entry. The UNIQUE(transaction_id, type) constraint fires
        at commit/flush — callers rely on that for idempotency."""
        self.session.add(entry)
        return entry

    async def get(self, transaction_id: UUID, type_: str) -> LedgerEntry | None:
        statement = select(LedgerEntry).where(
            LedgerEntry.transaction_id == transaction_id,
            LedgerEntry.type == type_,
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_for_user(
        self, user_email: str, limit: int = 100
    ) -> list[LedgerEntry]:
        statement = (
            select(LedgerEntry)
            .where(LedgerEntry.user_email == user_email)
            .order_by(LedgerEntry.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all())


class InvoiceRepository:
    """Session-bound invoice access with status-guarded transitions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def insert(self, invoice: Invoice) -> Invoice:
        self.session.add(invoice)
        return invoice

    async def get(self, invoice_id: UUID) -> Invoice | None:
        return await self.session.get(Invoice, invoice_id)

    async def get_by_client_reference(self, client_reference: str) -> Invoice | None:
        statement = select(Invoice).where(Invoice.client_reference == client_reference)
        result = await self.session.exec(statement)
        return result.first()

    async def mark_paid(self, invoice_id: UUID, webhook_payload: dict) -> bool:
        """Settle an invoice. False ⇒ already settled (duplicate webhook).

        Conditional UPDATE from a settlable status makes duplicate webhook
        deliveries no-ops — the caller must credit the balance only on True.
        """
        now = datetime.now(UTC)
        stmt = (
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.status.in_(_SETTLABLE))  # type: ignore[attr-defined]
            .values(
                status=InvoiceStatus.PAID.value,
                webhook_payload=webhook_payload,
                paid_at=now,
                updated_at=now,
            )
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0

    async def update_status(self, invoice_id: UUID, status: str) -> bool:
        """Move to a non-PAID status (expired/cancelled/processing) — same
        settlable-status guard, so a late event can't reopen a paid invoice."""
        stmt = (
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.status.in_(_SETTLABLE))  # type: ignore[attr-defined]
            .values(status=status, updated_at=datetime.now(UTC))
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0

    async def set_checkout_metadata(
        self, invoice_id: UUID, checkout_url: str, provider_session_id: str | None
    ) -> bool:
        """Attach the provider session after creation (PENDING rows only)."""
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == invoice_id,
                Invoice.status == InvoiceStatus.PENDING.value,
            )
            .values(
                checkout_url=checkout_url,
                provider_session_id=provider_session_id,
                updated_at=datetime.now(UTC),
            )
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0


class CreditsLedger:
    """Unit-of-work: one session across balances + entries + invoices.

    Repos never commit; this ledger commits all staged writes together or
    rolls them back if an exception leaves the block.
    """

    def __init__(self, db: AsyncDatabase):
        self._db = db
        self._session_ctx: AbstractAsyncContextManager | None = None
        self.session: AsyncSession | None = None
        self.balances: UserBalanceRepository = None  # type: ignore[assignment]
        self.entries: LedgerEntryRepository = None  # type: ignore[assignment]
        self.invoices: InvoiceRepository = None  # type: ignore[assignment]

    async def __aenter__(self) -> "CreditsLedger":
        self._session_ctx = self._db.get_session()
        self.session = await self._session_ctx.__aenter__()
        self.balances = UserBalanceRepository(self.session)
        self.entries = LedgerEntryRepository(self.session)
        self.invoices = InvoiceRepository(self.session)
        return self

    async def commit(self) -> None:
        await self.session.commit()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.session.rollback()
        await self._session_ctx.__aexit__(exc_type, exc, tb)


class WalletRepository(AsyncBaseRepository[Wallet]):
    """Wallet CRUD. v1 policy (one wallet per station) lives in the handler."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Wallet)

    async def get_active(self) -> Wallet | None:
        """The station's shared wallet — v1 has at most one row."""
        async with self.db.get_session() as session:
            result = await session.exec(select(Wallet))
            return result.first()


class SpaceCreditTokenRepository(AsyncBaseRepository[SpaceCreditToken]):
    """Space credits tokens — each active row binds a space to a wallet."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, SpaceCreditToken)

    async def get_active_by_hash(self, token_hash: str) -> SpaceCreditToken | None:
        """Resolve a presented bearer token (already hashed) to its binding."""
        async with self.db.get_session() as session:
            statement = select(SpaceCreditToken).where(
                SpaceCreditToken.token_hash == token_hash,
                SpaceCreditToken.revoked_at.is_(None),  # type: ignore[union-attr]
            )
            result = await session.exec(statement)
            return result.first()

    async def get_active_for_space(self, space_id: UUID) -> SpaceCreditToken | None:
        async with self.db.get_session() as session:
            statement = select(SpaceCreditToken).where(
                SpaceCreditToken.space_id == space_id,
                SpaceCreditToken.revoked_at.is_(None),  # type: ignore[union-attr]
            )
            result = await session.exec(statement)
            return result.first()

    async def revoke_for_space(self, space_id: UUID) -> int:
        """Revoke every active token for a space (delete/purge, rotation)."""
        async with self.db.get_session() as session:
            stmt = (
                update(SpaceCreditToken)
                .where(
                    SpaceCreditToken.space_id == space_id,
                    SpaceCreditToken.revoked_at.is_(None),  # type: ignore[union-attr]
                )
                .values(revoked_at=datetime.now(UTC))
            )
            result = await session.exec(stmt)
            await session.commit()
            return result.rowcount
