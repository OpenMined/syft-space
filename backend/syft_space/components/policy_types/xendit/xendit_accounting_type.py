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
    PolicyContext,
    PolicyViolationError,
    WalletPolicy,
)
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class XenditPolicyConfig(BaseModel):
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


class XenditAccountingPolicy(WalletPolicy):
    """Xendit pricing policy.

    Admin sets price_per_request. End users buy money bundles via the linked
    wallet, and balance is deducted by price_per_request on each query.
    Balance is fungible across all endpoints sharing the wallet.
    """

    NAME = "xendit"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Pay-per-request billed against a Xendit wallet's prepaid balance"

    def required_wallet_type(self) -> str:
        return "xendit"

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return XenditPolicyConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Reserve price_per_request from the user's wallet balance."""
        if not configs:
            return context

        user_email = str(context.sender_email)
        validated = [XenditPolicyConfig(**c) for c in configs]

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

        for config in validated:
            if not config.applies_to_user(user_email):
                continue

            try:
                transaction_id = await balance_service.reserve(
                    wallet_id=wallet_id,
                    tenant_id=tenant_id,
                    user_email=user_email,
                    endpoint_id=endpoint_id,
                    amount=config.price_per_request,
                    currency=currency,
                )
            except InsufficientBalanceError as exc:
                raise PolicyViolationError(
                    message="Insufficient balance. Please purchase more credits.",
                    policy_type=self.NAME,
                    details={
                        "user": user_email,
                        "price_per_request": config.price_per_request,
                        "currency": currency,
                    },
                ) from exc

            context.metadata["xendit_transaction_id"] = transaction_id
            # Surface the recognized revenue on the response so the analytics
            # adapter can read it without knowing about Xendit. Cleared in
            # post_hook on the empty-response refund path.
            context.response = context.response or {}
            summary = context.response.setdefault("summary", {})
            summary["cost"] = config.price_per_request
            summary["currency"] = currency
            # Only one applicable config per user — first match wins.
            break

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Cancel the reservation if the response is empty (no useful content)."""
        if not configs:
            return context

        transaction_id = context.metadata.get("xendit_transaction_id")
        if not transaction_id:
            return context

        response = context.response or {}
        has_summary = bool(
            response.get("summary") and response["summary"].get("message")
        )
        has_documents = bool(
            response.get("references") and response["references"].get("documents")
        )

        if has_summary or has_documents:
            return context

        balance_service = context.metadata.get("balance_service")
        if balance_service:
            await balance_service.cancel(transaction_id)
            # Refund issued — clear the cost/currency on the response so
            # downstream consumers don't see a charge.
            summary = (context.response or {}).get("summary") or {}
            summary["cost"] = None
            summary["currency"] = None

        return context

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = XenditPolicyConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid xendit config: {e}") from e
