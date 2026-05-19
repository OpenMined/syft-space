"""Xendit per-document policy type.

Charges price per retrieved document, settled in post_hook once the search
has returned. A cheap pre_hook floor check refuses the request when the
user's balance can't cover even a single document.
"""

from typing import Any

from syft_space.components.policy_types.interfaces import (
    BalanceShortfallError,
    BasePolicyType,
    Capabilities,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.policy_types.xendit.policy_config import (
    XenditPaymentConfig,
)
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class XenditPerDocumentPolicy(BasePolicyType):
    """Xendit per-document pricing policy.

    Pre-hook: cheap floor check (balance >= price) so a user with zero
    balance can't keep triggering search compute.

    Post-hook: count the documents in the response, settle for
    count * price via the same BalanceService.reserve path used by
    per-request. On insufficient balance the response is dropped (we don't
    ship documents we can't charge for).
    """

    NAME = "xendit_per_document"

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(
            requires_wallet=True,
            required_wallet_type="xendit",
            requires_endpoint_dataset=True,
        )

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Pay-per-document billed against a Xendit wallet's prepaid balance"

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return XenditPaymentConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = XenditPaymentConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid xendit_per_document config: {e}") from e

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
            validated = XenditPaymentConfig(**config)
            for pattern in validated.applied_to:
                if not matches_any_pattern(user_email, [pattern]):
                    continue
                specificity = 0 if pattern == "*" else len(pattern.replace("*", ""))
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_price = validated.price

        return best_price

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Floor check: balance must cover at least one document."""
        if not configs:
            return context

        user_email = str(context.sender_email)
        price = self._find_matching_price(user_email, configs)

        # If no price is found, deny the request
        if price is None:
            raise PolicyViolationError(
                message="No pricing tier matches your account",
                policy_type=self.NAME,
            )

        charger = context.payment_chargers.xendit()
        balance = await charger.get_balance(user_email)
        if balance < price:
            raise PolicyViolationError(
                message="Insufficient balance. Please purchase more credits.",
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "balance": balance,
                    "price": price,
                    "currency": charger.currency,
                },
            )

        context.metadata["xendit_per_doc_price"] = price

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Settle for actual document count.

        Reserve happens here (not pre_hook) because we don't know the
        document count until the search returns. On insufficient balance
        we raise; an empty response means no documents were charged.
        """
        if not configs:
            return context

        price = context.metadata.get("xendit_per_doc_price")
        if price is None:
            return context

        response = context.response or {}
        references = response.get("references") or {}
        documents = references.get("documents") or []
        count = len(documents)
        if count == 0:
            return context

        total = count * price
        user_email = str(context.sender_email)
        charger = context.payment_chargers.xendit()

        try:
            await charger.reserve(
                user_email=user_email,
                amount=total,
                charge_unit="document",
                charge_quantity=count,
            )
        except BalanceShortfallError as exc:
            raise PolicyViolationError(
                message="Insufficient balance for the documents retrieved.",
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "documents": count,
                    "price": price,
                    "total": total,
                    "currency": exc.currency,
                },
            ) from exc

        if response.get("references"):
            response["references"]["cost"] = total
            response["references"]["currency"] = charger.currency

        return context
