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
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, func, update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from syft_station.components.credits.entities import (
    EntryType,
    Invoice,
    InvoiceStatus,
    LedgerEntry,
    Payout,
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

    async def list_nonzero(self) -> list[UserBalance]:
        """Outstanding credit per user — the station's liability list."""
        statement = (
            select(UserBalance)
            .where(UserBalance.balance > 0)
            .order_by(UserBalance.balance.desc())  # type: ignore[attr-defined]
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def total_outstanding(self) -> float:
        statement = select(func.coalesce(func.sum(UserBalance.balance), 0.0))
        result = await self.session.exec(statement)
        return float(result.one())


@dataclass(frozen=True)
class EarningsRow:
    """One aggregation bucket over the spend ledger.

    ``earned`` and ``query_count`` are net of reversals: a CANCELLED row
    subtracts what its DEBIT added, so fully refunded queries count as zero.
    """

    space_id: UUID
    earned: float
    query_count: int
    endpoint: str = ""
    day: str = ""


# CANCELLED rows negate their DEBIT in every aggregate.
_SIGNED_AMOUNT = case(
    (LedgerEntry.type == EntryType.DEBIT.value, LedgerEntry.amount),
    else_=-LedgerEntry.amount,
)
_SIGNED_COUNT = case((LedgerEntry.type == EntryType.DEBIT.value, 1), else_=-1)


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

    # --- Earnings aggregates (all plain GROUP BYs, no joins) ---

    async def earnings_by_space(self) -> list[EarningsRow]:
        statement = select(
            LedgerEntry.space_id,
            func.sum(_SIGNED_AMOUNT),
            func.sum(_SIGNED_COUNT),
        ).group_by(LedgerEntry.space_id)
        result = await self.session.exec(statement)
        return [
            EarningsRow(space_id=sid, earned=earned or 0.0, query_count=count or 0)
            for sid, earned, count in result.all()
        ]

    async def earned_for_space(self, space_id: UUID) -> float:
        statement = select(func.coalesce(func.sum(_SIGNED_AMOUNT), 0.0)).where(
            LedgerEntry.space_id == space_id
        )
        result = await self.session.exec(statement)
        return float(result.one())

    async def earnings_by_endpoint(self) -> list[EarningsRow]:
        statement = select(
            LedgerEntry.space_id,
            LedgerEntry.endpoint,
            func.sum(_SIGNED_AMOUNT),
            func.sum(_SIGNED_COUNT),
        ).group_by(LedgerEntry.space_id, LedgerEntry.endpoint)
        result = await self.session.exec(statement)
        return [
            EarningsRow(
                space_id=sid,
                endpoint=endpoint,
                earned=earned or 0.0,
                query_count=count or 0,
            )
            for sid, endpoint, earned, count in result.all()
        ]

    async def net_spend_by_user(self) -> dict[str, float]:
        """Σ debits − reversals per user — the 'spent' column."""
        statement = select(LedgerEntry.user_email, func.sum(_SIGNED_AMOUNT)).group_by(
            LedgerEntry.user_email
        )
        result = await self.session.exec(statement)
        return {email: float(total or 0.0) for email, total in result.all()}

    async def earnings_by_day(self) -> list[EarningsRow]:
        day = func.date(LedgerEntry.created_at)
        statement = (
            select(
                LedgerEntry.space_id,
                day,
                func.sum(_SIGNED_AMOUNT),
                func.sum(_SIGNED_COUNT),
            )
            .group_by(LedgerEntry.space_id, day)
            .order_by(day)
        )
        result = await self.session.exec(statement)
        return [
            EarningsRow(
                space_id=sid, day=d, earned=earned or 0.0, query_count=count or 0
            )
            for sid, d, earned, count in result.all()
        ]


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

    async def list_for_user(self, user_email: str, limit: int = 50) -> list[Invoice]:
        statement = (
            select(Invoice)
            .where(Invoice.user_email == user_email)
            .order_by(Invoice.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def total_paid(self) -> float:
        """Credits sold — the sum of every settled top-up."""
        statement = select(func.coalesce(func.sum(Invoice.amount), 0.0)).where(
            Invoice.status == InvoiceStatus.PAID.value
        )
        result = await self.session.exec(statement)
        return float(result.one())

    async def list_recent_paid(self, limit: int = 20) -> list[Invoice]:
        """The freshest settled top-ups — the admin dashboard's feed."""
        statement = (
            select(Invoice)
            .where(Invoice.status == InvoiceStatus.PAID.value)
            .order_by(Invoice.paid_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def paid_totals_by_user(self) -> dict[str, float]:
        """Σ settled top-ups per user — the 'bought' column."""
        statement = (
            select(Invoice.user_email, func.sum(Invoice.amount))
            .where(Invoice.status == InvoiceStatus.PAID.value)
            .group_by(Invoice.user_email)
        )
        result = await self.session.exec(statement)
        return {email: float(total) for email, total in result.all()}

    async def mark_paid(
        self,
        invoice_id: UUID,
        webhook_payload: dict,
        paid_at: datetime | None = None,
    ) -> bool:
        """Settle an invoice. False ⇒ already settled (duplicate webhook).

        Conditional UPDATE from a settlable status makes duplicate webhook
        deliveries no-ops — the caller must credit the balance only on True.
        ``paid_at`` defaults to now; pass the provider's settlement
        timestamp when the webhook carries one.
        """
        now = datetime.now(UTC)
        stmt = (
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.status.in_(_SETTLABLE))  # type: ignore[attr-defined]
            .values(
                status=InvoiceStatus.PAID.value,
                webhook_payload=webhook_payload,
                paid_at=paid_at or now,
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


class PayoutRepository(AsyncBaseRepository[Payout]):
    """Payout records — appended by the admin, summed for payables."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Payout)

    async def totals_by_space(self) -> dict[UUID, float]:
        async with self.db.get_session() as session:
            statement = select(
                Payout.space_id, func.coalesce(func.sum(Payout.amount), 0.0)
            ).group_by(Payout.space_id)
            result = await session.exec(statement)
            return {space_id: float(total) for space_id, total in result.all()}

    async def total_for_space(self, space_id: UUID) -> float:
        async with self.db.get_session() as session:
            statement = select(func.coalesce(func.sum(Payout.amount), 0.0)).where(
                Payout.space_id == space_id
            )
            result = await session.exec(statement)
            return float(result.one())

    async def list_for_space(self, space_id: UUID) -> list[Payout]:
        async with self.db.get_session() as session:
            statement = (
                select(Payout)
                .where(Payout.space_id == space_id)
                .order_by(Payout.created_at.desc())  # type: ignore[attr-defined]
            )
            result = await session.exec(statement)
            return list(result.all())

    async def list_recent(self, limit: int = 20) -> list[Payout]:
        async with self.db.get_session() as session:
            statement = (
                select(Payout)
                .order_by(Payout.created_at.desc())  # type: ignore[attr-defined]
                .limit(limit)
            )
            result = await session.exec(statement)
            return list(result.all())


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
