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
from syft_space.components.policy_types.payment_metadata import PaymentMetadataMixin
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class PrepaidBalancePaymentPolicyBase(PaymentMetadataMixin, BasePolicyType):
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

    # PolicyMetadataEntry builders. The invariant shape (policy_type / kind /
    # recipient / status) lives in PaymentMetadataMixin; only the prepaid-rail
    # TransactionRef is built here. `_free_entry` / `_rejected_entry` are
    # inherited from the mixin.
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
        # The cast silences mypy, so it can NOT catch a wallet type missing
        # from TransactionRef.rail — pydantic raises at runtime instead,
        # after the balance was already reserved (bit us live when "cluster"
        # was absent). Adding a wallet type? Extend the rail Literal first.
        return TransactionRef(
            rail=cast(Literal["xendit", "stripe", "cluster"], wallet_type),
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
        return self._payment_entry(
            context,
            status="charged",
            amount=amount,
            currency=currency,
            transaction=self._prepaid_transaction(wallet_type, transaction_id),
            details=details,
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
        return self._payment_entry(
            context,
            status="refunded",
            amount=0,
            currency=currency,
            transaction=self._prepaid_transaction(wallet_type, transaction_id),
            details=details,
        )
