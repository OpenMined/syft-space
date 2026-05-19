"""Xendit per-request policy type implementation.

Wallet-scoped money-balance model. The policy carries only price and
applied_to. Currency, country, and bundles live on the Wallet (linked via
Policy.wallet_id), so the same balance is fungible across all endpoints
that reference the same wallet.
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


class XenditPerRequestPolicy(BasePolicyType):
    """Xendit per-request pricing policy.

    Admin sets price. End users buy money bundles via the linked wallet,
    and balance is deducted by price on each query. Balance is fungible
    across all endpoints sharing the wallet.
    """

    NAME = "xendit_per_request"

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(requires_wallet=True, required_wallet_type="xendit")

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Pay-per-request billed against a Xendit wallet's prepaid balance"

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return XenditPaymentConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

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
        """Reserve price from the user's wallet balance."""
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
        try:
            transaction_id = await charger.reserve(
                user_email=user_email,
                amount=price,
                charge_unit="request",
                charge_quantity=1,
            )
        except BalanceShortfallError as exc:
            raise PolicyViolationError(
                message="Insufficient balance. Please purchase more credits.",
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "price": price,
                    "currency": exc.currency,
                },
            ) from exc

        context.metadata["xendit_transaction_id"] = transaction_id
        context.metadata["xendit_price"] = price

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Cancel the reservation if the response is empty (no useful content)."""
        if not configs:
            return context

        transaction_id = context.metadata.get("xendit_transaction_id")
        price = context.metadata.get("xendit_price")

        # No transaction ID means the request was not charged
        if not transaction_id:
            return context

        charger = context.payment_chargers.xendit()
        currency = charger.currency
        response = context.response or {}

        has_summary = bool(
            response.get("summary") and response["summary"].get("message")
        )
        has_documents = bool(
            response.get("references") and response["references"].get("documents")
        )

        # Set the cost and currency on the response
        if has_summary:
            response["summary"]["cost"] = price
            response["summary"]["currency"] = currency
        if has_documents:
            response["references"]["cost"] = price
            response["references"]["currency"] = currency

        if has_summary or has_documents:
            return context

        # Cancel the reservation if the response is empty (no useful content)
        await charger.cancel(transaction_id)

        return context

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = XenditPaymentConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid xendit config: {e}") from e
