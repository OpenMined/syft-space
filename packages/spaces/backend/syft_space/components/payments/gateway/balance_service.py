"""Balance service — orchestrates user balance changes through the PaymentLedger.

Top-ups are recorded on Invoice (status=paid is the source of truth). Spends
are recorded on LedgerEntry (debit / cancelled). Each money movement pairs a
balance update with the appropriate row.

Every public mutation borrows one PaymentLedger; balance and ledger writes
commit together or roll back together. The service owns *meaning* (which
business operation), the PaymentLedger owns *mechanism* (the transaction
boundary). The service never imports SQL or sessions.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from syft_space.components.payments.gateway.entities import (
    EntryType,
    Invoice,
    LedgerEntry,
)
from syft_space.components.payments.gateway.payment_ledger import PaymentLedger


class InsufficientBalanceError(Exception):
    """Raised when a reservation cannot proceed due to shortfall."""


class BalanceService:
    """Orchestrates credit_invoice / reserve / cancel / get_balance."""

    def __init__(self, payment_ledger_factory: Callable[[], PaymentLedger]):
        self._ledger = payment_ledger_factory

    async def credit_invoice(
        self,
        invoice: Invoice,
        paid_at: datetime,
        webhook_payload: dict,
    ) -> bool:
        """Atomically transition invoice PENDING→PAID and credit wallet balance.

        Idempotent: only PENDING invoices flip; retried webhooks become no-ops.
        Returns True if the credit was applied, False if already processed.
        """
        if invoice.wallet_id is None:
            return False

        async with self._ledger() as ledger:
            applied = await ledger.invoices.mark_paid(
                id=invoice.id,
                paid_at=paid_at,
                webhook_payload=webhook_payload,
            )
            if not applied:
                return False

            await ledger.balances.upsert_credit(
                tenant_id=invoice.tenant_id,
                wallet_id=invoice.wallet_id,
                user_email=invoice.user_email,
                amount=invoice.amount,
            )

            await ledger.commit()
            return True

    async def reserve(
        self,
        *,
        wallet_id: UUID,
        tenant_id: UUID,
        user_email: str,
        endpoint_id: UUID,
        amount: float,
        currency: str,
        charge_unit: str,
        charge_quantity: int,
    ) -> UUID:
        """Atomically deduct `amount` from balance and write a debit entry.

        Raises InsufficientBalanceError on shortfall. Returns the new
        transaction_id (correlation key for matching cancel).
        """
        async with self._ledger() as ledger:
            deducted = await ledger.balances.atomic_deduct(
                user_email=user_email,
                wallet_id=wallet_id,
                tenant_id=tenant_id,
                amount=amount,
            )
            if not deducted:
                raise InsufficientBalanceError(
                    f"Balance below {amount} {currency} for user {user_email}"
                )

            transaction_id = uuid4()
            await ledger.entries.insert(
                LedgerEntry(
                    tenant_id=tenant_id,
                    wallet_id=wallet_id,
                    user_email=user_email,
                    transaction_id=transaction_id,
                    type=EntryType.DEBIT.value,
                    endpoint_id=endpoint_id,
                    amount=amount,
                    currency=currency,
                    charge_unit=charge_unit,
                    charge_quantity=charge_quantity,
                )
            )

            await ledger.commit()
            return transaction_id

    async def cancel(self, transaction_id: UUID) -> None:
        """Reverse a reservation by its transaction_id.

        Looks up the original debit, writes a cancelled row, and restores
        balance — all in one ledger. Idempotent via UNIQUE(transaction_id,
        type): a duplicate cancel collides on insert and the transaction
        rolls back, leaving balance untouched.
        """
        async with self._ledger() as ledger:
            debit = await ledger.entries.get_debit_by_transaction_id(transaction_id)
            if not debit:
                return  # nothing to reverse
            if debit.wallet_id is None:
                return  # original wallet gone; balance row already cascaded away

            await ledger.entries.insert(
                LedgerEntry(
                    tenant_id=debit.tenant_id,
                    wallet_id=debit.wallet_id,
                    user_email=debit.user_email,
                    transaction_id=transaction_id,
                    type=EntryType.CANCELLED.value,
                    endpoint_id=debit.endpoint_id,
                    amount=debit.amount,
                    currency=debit.currency,
                    charge_unit=debit.charge_unit,
                    charge_quantity=debit.charge_quantity,
                )
            )
            await ledger.balances.atomic_restore(
                user_email=debit.user_email,
                wallet_id=debit.wallet_id,
                tenant_id=debit.tenant_id,
                amount=debit.amount,
            )

            await ledger.commit()

    async def record_external_debit(
        self,
        *,
        wallet_id: UUID,
        tenant_id: UUID,
        user_email: str,
        endpoint_id: UUID,
        transaction_id: UUID,
        amount: float,
        currency: str,
        charge_unit: str,
        charge_quantity: int,
    ) -> None:
        """Journal a debit that settled on an external ledger (record-only).

        For wallets whose authoritative balance lives outside this space
        (cluster credits): writes the LedgerEntry so spend history is
        queryable locally. Never touches UserBalance, and must never be
        read for money decisions.
        """
        async with self._ledger() as ledger:
            await ledger.entries.insert(
                LedgerEntry(
                    tenant_id=tenant_id,
                    wallet_id=wallet_id,
                    user_email=user_email,
                    transaction_id=transaction_id,
                    type=EntryType.DEBIT.value,
                    endpoint_id=endpoint_id,
                    amount=amount,
                    currency=currency,
                    charge_unit=charge_unit,
                    charge_quantity=charge_quantity,
                )
            )
            await ledger.commit()

    async def record_external_cancel(self, transaction_id: UUID) -> None:
        """Journal the reversal of an external debit (record-only).

        Mirrors cancel() minus the balance restore. Missing debit (journal
        write failed earlier) is a no-op — the cluster ledger stays
        authoritative.
        """
        async with self._ledger() as ledger:
            debit = await ledger.entries.get_debit_by_transaction_id(transaction_id)
            if not debit or debit.wallet_id is None:
                return
            await ledger.entries.insert(
                LedgerEntry(
                    tenant_id=debit.tenant_id,
                    wallet_id=debit.wallet_id,
                    user_email=debit.user_email,
                    transaction_id=transaction_id,
                    type=EntryType.CANCELLED.value,
                    endpoint_id=debit.endpoint_id,
                    amount=debit.amount,
                    currency=debit.currency,
                    charge_unit=debit.charge_unit,
                    charge_quantity=debit.charge_quantity,
                )
            )
            await ledger.commit()

    async def get_balance(
        self, *, wallet_id: UUID, tenant_id: UUID, user_email: str
    ) -> float:
        """Read the current balance. Returns 0.0 if no row exists."""
        async with self._ledger() as ledger:
            row = await ledger.balances.get_by_user_wallet(
                user_email=user_email, wallet_id=wallet_id, tenant_id=tenant_id
            )
            return row.balance if row else 0.0
