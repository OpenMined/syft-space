"""Shared PolicyMetadataEntry construction for payment policies.

Every payment policy — prepaid-balance (Stripe/Xendit) and MPP alike — emits
entries with the same invariant shape: ``policy_type`` / ``kind="payment"`` /
``recipient``, varying only in status and the rail-specific ``TransactionRef``.
This mixin owns that invariant so an entry's shape is defined exactly once; each
family supplies only its rail's transaction via ``_charged_entry`` /
``_refunded_entry``.
"""

from typing import Any, ClassVar

from syft_space.components.policy_types.interfaces import (
    PolicyContext,
    PolicyMetadataEntry,
    ReasonCode,
    TransactionRef,
)


class PaymentMetadataMixin:
    """Builds the invariant parts of a payment policy's PolicyMetadataEntry."""

    NAME: ClassVar[str]

    def _payment_entry(
        self,
        context: PolicyContext,
        *,
        status: str,
        amount: float | None = None,
        currency: str | None = None,
        transaction: TransactionRef | None = None,
        reason_code: ReasonCode | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> PolicyMetadataEntry:
        """Assemble a payment entry, filling the fields invariant across rails."""
        return PolicyMetadataEntry(
            policy_type=self.NAME,
            kind="payment",
            status=status,
            amount=amount,
            currency=currency,
            recipient=context.recipient,
            transaction=transaction,
            reason_code=reason_code,
            reason=reason,
            details=details or {},
        )

    def _free_entry(
        self,
        context: PolicyContext,
        *,
        currency: str = "USD",
        details: dict[str, Any] | None = None,
    ) -> PolicyMetadataEntry:
        """Build a 'free' (amount=0) entry — no charge made."""
        return self._payment_entry(
            context, status="free", amount=0, currency=currency, details=details
        )

    def _rejected_entry(
        self,
        context: PolicyContext,
        *,
        reason_code: ReasonCode,
        reason: str,
        amount: float | None = None,
        currency: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> PolicyMetadataEntry:
        """Build a 'rejected' entry (no tier / insufficient balance / etc.)."""
        return self._payment_entry(
            context,
            status="rejected",
            amount=amount,
            currency=currency,
            reason_code=reason_code,
            reason=reason,
            details=details,
        )
