"""Generic infrastructure for prepaid-balance payment policies.

Concrete subclasses declare ``PROVIDER_NAME``, ``NAME``, ``DESCRIPTION``,
and ``CONFIG_CLS``. Every other concern — config validation, schema
export, tier matching, identity boilerplate — is provider-agnostic and
lives here.
"""

from typing import Any, ClassVar, Literal, cast
from uuid import UUID

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    Capabilities,
    PolicyContext,
    PolicyMetadataEntry,
    TransactionRef,
)
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class PrepaidBalancePaymentPolicyBase(BasePolicyType):
    """Shared scaffolding for all prepaid-balance payment policies."""

    PROVIDER_NAME: ClassVar[str]  # "stripe", "xendit", ...
    NAME: ClassVar[str]
    DESCRIPTION: ClassVar[str]
    # Provider-specific Pydantic config class. Duck-typed against
    # ``applied_to: list[str]`` and ``price: float``.
    CONFIG_CLS: ClassVar[type]

    def __init__(self) -> None:
        pass

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return cls.DESCRIPTION

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return cls.CONFIG_CLS.model_json_schema(schema_generator=ConfigSchemaGenerator)

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(
            requires_wallet=True,
            required_wallet_type=cls.PROVIDER_NAME,
        )

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate the user-supplied config.

        ``unit_type`` is a typed Literal on the subclass's CONFIG_CLS so it
        flows through ``model_dump()`` naturally; nothing is injected here.
        """
        try:
            validated = cls.CONFIG_CLS(**config)
        except Exception as e:
            raise ValueError(f"Invalid {cls.PROVIDER_NAME} config: {e}") from e
        return validated.model_dump()

    def _find_matching_price(
        self, user_email: str, configs: list[dict[str, Any]]
    ) -> float | None:
        """Find the most specific matching price for a user.

        More specific patterns (longer, non-wildcard) take priority.
        Returns None if no config matches.
        """
        best_price: float | None = None
        best_specificity = -1

        for config in configs:
            validated = self.CONFIG_CLS(**config)
            for pattern in validated.applied_to:
                if not matches_any_pattern(user_email, [pattern]):
                    continue
                specificity = 0 if pattern == "*" else len(pattern.replace("*", ""))
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_price = validated.price

        return best_price

    # ----------------------------------------------------------------- #
    # PolicyMetadataEntry builders — keep emitted entries DRY across the #
    # per-request / per-document subclasses. Each fills in the invariant #
    # policy_type / kind / recipient and lets callers supply only the    #
    # varying fields.                                                    #
    # ----------------------------------------------------------------- #
    @staticmethod
    def _prepaid_transaction(
        wallet_type: str, transaction_id: UUID | str | None
    ) -> TransactionRef | None:
        """Build a TransactionRef, guarding a None ledger id.

        ``TransactionRef.id`` is a required str; defensively skip attaching a
        transaction when the ledger id is missing rather than letting pydantic
        raise after the balance was already reserved.
        """
        if transaction_id is None:
            return None
        return TransactionRef(
            rail=cast(Literal["xendit", "stripe"], wallet_type),
            id=str(transaction_id),
        )

    def _charged_entry(
        self,
        context: PolicyContext,
        *,
        amount: float,
        currency: str,
        wallet_type: str,
        transaction_id: UUID | str | None,
        details: dict[str, Any] | None = None,
    ) -> PolicyMetadataEntry:
        """Build a 'charged' entry."""
        return PolicyMetadataEntry(
            policy_type=self.NAME,
            kind="payment",
            status="charged",
            amount=amount,
            currency=currency,
            recipient=context.recipient,
            transaction=self._prepaid_transaction(wallet_type, transaction_id),
            details=details or {},
        )

    def _refunded_entry(
        self,
        context: PolicyContext,
        *,
        currency: str,
        wallet_type: str,
        transaction_id: UUID | str | None,
        details: dict[str, Any] | None = None,
    ) -> PolicyMetadataEntry:
        """Build a 'refunded' (amount=0) entry — reservation cancelled."""
        return PolicyMetadataEntry(
            policy_type=self.NAME,
            kind="payment",
            status="refunded",
            amount=0,
            currency=currency,
            recipient=context.recipient,
            transaction=self._prepaid_transaction(wallet_type, transaction_id),
            details=details or {},
        )

    def _free_entry(
        self,
        context: PolicyContext,
        *,
        currency: str,
        details: dict[str, Any] | None = None,
    ) -> PolicyMetadataEntry:
        """Build a 'free' (amount=0) entry — no charge made."""
        return PolicyMetadataEntry(
            policy_type=self.NAME,
            kind="payment",
            status="free",
            amount=0,
            currency=currency,
            recipient=context.recipient,
            details=details or {},
        )

    def _rejected_entry(
        self,
        context: PolicyContext,
        *,
        reason_code: str,
        reason: str,
        amount: float | None = None,
        currency: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> PolicyMetadataEntry:
        """Build a 'rejected' entry (no tier / insufficient balance)."""
        return PolicyMetadataEntry(
            policy_type=self.NAME,
            kind="payment",
            status="rejected",
            amount=amount,
            currency=currency,
            recipient=context.recipient,
            reason_code=reason_code,
            reason=reason,
            details=details or {},
        )
