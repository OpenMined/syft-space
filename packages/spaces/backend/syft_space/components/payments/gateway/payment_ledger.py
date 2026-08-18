"""PaymentLedger — atomic boundary across the payment repos.

A unit-of-work that hands `invoices`, `balances`, and `entries` repos a
shared session, then commits (or rolls back) all writes as one transaction.

Service code never sees a session or a database handle — it borrows a
ledger for the duration of one business operation:

    async with payment_ledger() as ledger:
        ok = await ledger.balances.atomic_deduct(...)
        if not ok: raise InsufficientBalanceError(...)
        await ledger.entries.insert(LedgerEntry(...))
        await ledger.commit()

If an exception leaves the `async with` block, the ledger rolls back.
Read-only flows can omit `commit()` — exit closes the session cleanly.
"""

from contextlib import AbstractAsyncContextManager

from sqlmodel.ext.asyncio.session import AsyncSession

from syft_space.components.payments.gateway.invoice_repository import InvoiceRepository
from syft_space.components.payments.gateway.ledger_entry_repository import (
    LedgerEntryRepository,
)
from syft_space.components.payments.gateway.user_balance_repository import (
    UserBalanceRepository,
)
from syft_space.components.shared.database import AsyncDatabase


class PaymentLedger:
    """Async context manager grouping the three payment repos under one session."""

    def __init__(self, db: AsyncDatabase):
        self._db = db
        self._session_ctx: AbstractAsyncContextManager | None = None
        self.session: AsyncSession | None = None
        self.invoices: InvoiceRepository | None = None
        self.balances: UserBalanceRepository | None = None
        self.entries: LedgerEntryRepository | None = None

    async def __aenter__(self) -> "PaymentLedger":
        self._session_ctx = self._db.get_session()
        self.session = await self._session_ctx.__aenter__()
        self.invoices = InvoiceRepository(self.session)
        self.balances = UserBalanceRepository(self.session)
        self.entries = LedgerEntryRepository(self.session)
        return self

    async def commit(self) -> None:
        """Commit all staged writes from this ledger's repos."""
        await self.session.commit()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.session.rollback()
        await self._session_ctx.__aexit__(exc_type, exc, tb)
