"""LedgerEntry repository — append-only money-movement ledger.

Session-bound: every method runs against the session passed at construction
time. Repos do not commit; the owning PaymentLedger commits or rolls back.
"""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from syft_space.components.payments.gateway.entities import EntryType, LedgerEntry


def _encode_cursor(created_at: datetime, entry_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{entry_id}"
    return urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    raw = urlsafe_b64decode(padded.encode()).decode()
    ts, tid = raw.split("|", 1)
    return datetime.fromisoformat(ts), UUID(tid)


class LedgerEntryRepository:
    """Append-only writes; cursor-paginated reads."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert(self, entry: LedgerEntry) -> LedgerEntry:
        """Stage an entry on the session. PaymentLedger commits."""
        self.session.add(entry)
        return entry

    async def get_debit_by_transaction_id(
        self, transaction_id: UUID
    ) -> LedgerEntry | None:
        """Look up a debit row by its correlation id (used by cancel)."""
        statement = select(LedgerEntry).where(
            LedgerEntry.transaction_id == transaction_id,
            LedgerEntry.type == EntryType.DEBIT.value,
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_for_user(
        self,
        tenant_id: UUID,
        wallet_id: UUID,
        user_email: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[LedgerEntry], str | None]:
        """Cursor-paginated user-facing history. Newest first.

        Cursor encodes (created_at, id) for stable ordering across appends.
        Returns (rows, next_cursor) where next_cursor is None at the end.
        """
        statement = select(LedgerEntry).where(
            LedgerEntry.tenant_id == tenant_id,
            LedgerEntry.wallet_id == wallet_id,
            LedgerEntry.user_email == user_email,
        )
        if cursor:
            cursor_ts, cursor_id = _decode_cursor(cursor)
            statement = statement.where(
                (LedgerEntry.created_at < cursor_ts)
                | ((LedgerEntry.created_at == cursor_ts) & (LedgerEntry.id < cursor_id))
            )
        statement = statement.order_by(
            LedgerEntry.created_at.desc(), LedgerEntry.id.desc()
        ).limit(limit + 1)

        result = await self.session.exec(statement)
        rows = list(result.all())

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            tail = rows[-1]
            next_cursor = _encode_cursor(tail.created_at, tail.id)
        return rows, next_cursor

    async def list_for_wallet(
        self,
        tenant_id: UUID,
        wallet_id: UUID,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[LedgerEntry], str | None]:
        """Cursor-paginated admin history across all users for a wallet."""
        statement = select(LedgerEntry).where(
            LedgerEntry.tenant_id == tenant_id,
            LedgerEntry.wallet_id == wallet_id,
        )
        if cursor:
            cursor_ts, cursor_id = _decode_cursor(cursor)
            statement = statement.where(
                (LedgerEntry.created_at < cursor_ts)
                | ((LedgerEntry.created_at == cursor_ts) & (LedgerEntry.id < cursor_id))
            )
        statement = statement.order_by(
            LedgerEntry.created_at.desc(), LedgerEntry.id.desc()
        ).limit(limit + 1)

        result = await self.session.exec(statement)
        rows = list(result.all())

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            tail = rows[-1]
            next_cursor = _encode_cursor(tail.created_at, tail.id)
        return rows, next_cursor

    async def list_for_endpoint(
        self,
        tenant_id: UUID,
        endpoint_id: UUID,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[LedgerEntry], str | None]:
        """Cursor-paginated admin history across all users for an endpoint.

        Spans wallets — historical entries for an endpoint that was previously
        bound to a different wallet remain visible. Entries for deleted
        endpoints disappear from this view (endpoint_id is SET NULL on delete).
        """
        statement = select(LedgerEntry).where(
            LedgerEntry.tenant_id == tenant_id,
            LedgerEntry.endpoint_id == endpoint_id,
        )
        if cursor:
            cursor_ts, cursor_id = _decode_cursor(cursor)
            statement = statement.where(
                (LedgerEntry.created_at < cursor_ts)
                | ((LedgerEntry.created_at == cursor_ts) & (LedgerEntry.id < cursor_id))
            )
        statement = statement.order_by(
            LedgerEntry.created_at.desc(), LedgerEntry.id.desc()
        ).limit(limit + 1)

        result = await self.session.exec(statement)
        rows = list(result.all())

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            tail = rows[-1]
            next_cursor = _encode_cursor(tail.created_at, tail.id)
        return rows, next_cursor

    async def aggregate_spent(
        self, tenant_id: UUID, wallet_id: UUID, user_email: str
    ) -> float:
        """Sum debits − cancelled for (tenant, wallet, user) to derive total_spent.

        Top-ups (total_deposited) are derived from invoices, not this table.
        """
        debits_stmt = select(LedgerEntry).where(
            LedgerEntry.tenant_id == tenant_id,
            LedgerEntry.wallet_id == wallet_id,
            LedgerEntry.user_email == user_email,
            LedgerEntry.type == EntryType.DEBIT.value,
        )
        cancels_stmt = select(LedgerEntry).where(
            LedgerEntry.tenant_id == tenant_id,
            LedgerEntry.wallet_id == wallet_id,
            LedgerEntry.user_email == user_email,
            LedgerEntry.type == EntryType.CANCELLED.value,
        )
        debits = (await self.session.exec(debits_stmt)).all()
        cancels = (await self.session.exec(cancels_stmt)).all()
        return float(sum(d.amount for d in debits) - sum(c.amount for c in cancels))
