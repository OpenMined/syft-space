"""Xendit payment policy type implementation.

Wallet-scoped money-balance model. The policy carries only price_per_request
and applied_to. Currency, country, and bundles live on the Wallet (linked
via Policy.wallet_id), so the same balance is fungible across all endpoints
that reference the same wallet.
"""

from typing import Any

from pydantic import BaseModel, Field

from syft_space.components.payments.gateway.balance_service import (
    InsufficientBalanceError,
)
from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    Capabilities,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class XenditPerRequestConfig(BaseModel):
    """Configuration schema for xendit pricing policy.

    Currency, country, and bundles live on the linked Wallet — not here.
    The wallet's currency must match across all xendit policies that share it.
    """

    price_per_request: float = Field(
        ..., gt=0, description="Cost per request in the wallet's currency"
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user emails or glob patterns. Use '*' for all users.",
    )

    def applies_to_user(self, user_email: str) -> bool:
        """Check if this policy applies to the given user email."""
        return matches_any_pattern(user_email, self.applied_to)


class XenditPerRequestPolicy(BasePolicyType):
    """Xendit pricing policy.

    Admin sets price_per_request. End users buy money bundles via the linked
    wallet, and balance is deducted by price_per_request on each query.
    Balance is fungible across all endpoints sharing the wallet.
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
        return XenditPerRequestConfig.model_json_schema(
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
            validated = XenditPerRequestConfig(**config)
            for pattern in validated.applied_to:
                if not matches_any_pattern(user_email, [pattern]):
                    continue
                specificity = 0 if pattern == "*" else len(pattern.replace("*", ""))
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_price = validated.price_per_request

        return best_price

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Reserve price_per_request from the user's wallet balance."""
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

        balance_service = context.metadata.get("balance_service")
        if not balance_service:
            raise PolicyViolationError(
                message="Balance service not available",
                policy_type=self.NAME,
                details={"user": user_email},
            )

        wallet_id = context.metadata.get("xendit_wallet_id")
        currency = context.metadata.get("xendit_wallet_currency")
        endpoint_id = context.metadata.get("endpoint_id")
        tenant_id = context.metadata.get("tenant_id")
        if not wallet_id or not currency or not endpoint_id or not tenant_id:
            raise PolicyViolationError(
                message="Missing wallet/endpoint context for bundle check",
                policy_type=self.NAME,
                details={"user": user_email},
            )

        try:
            transaction_id = await balance_service.reserve(
                wallet_id=wallet_id,
                tenant_id=tenant_id,
                user_email=user_email,
                endpoint_id=endpoint_id,
                amount=price,
                currency=currency,
                charge_unit="request",
                charge_quantity=1,
            )
        except InsufficientBalanceError as exc:
            raise PolicyViolationError(
                message="Insufficient balance. Please purchase more credits.",
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "price_per_request": price,
                    "currency": currency,
                },
            ) from exc

        context.metadata["xendit_transaction_id"] = transaction_id
        context.metadata["xendit_price_per_request"] = price

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Cancel the reservation if the response is empty (no useful content)."""
        if not configs:
            return context

        transaction_id = context.metadata.get("xendit_transaction_id")
        price = context.metadata.get("xendit_price_per_request")
        currency = context.metadata.get("xendit_wallet_currency")

        # No transaction ID means the request was not charged
        if not transaction_id:
            return context

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
        balance_service = context.metadata["balance_service"]

        await balance_service.cancel(transaction_id)

        return context

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = XenditPerRequestConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid xendit config: {e}") from e
