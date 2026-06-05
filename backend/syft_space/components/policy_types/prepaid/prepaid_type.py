"""Prepaid quota policy: buyers purchase bundles in advance, each call decrements, zero blocks."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator


class PrepaidUnit(str, Enum):
    """Unit type for prepaid quota tracking."""

    REQUEST = "request"
    DOCUMENT = "document"


class BundleTier(BaseModel):
    """A single bundle tier offered to buyers."""

    volume: int = Field(..., gt=0, description="Number of units in this bundle")
    price: float = Field(..., ge=0, description="Price for this bundle")
    currency: str = Field(default="USD", description="Currency code")


class PrepaidConfig(BaseModel):
    """Bundle tiers + unit/provider settings stored in Policy.configuration."""

    bundle_tiers: list[BundleTier] = Field(
        ...,
        min_length=1,
        description="Available bundle tiers (volume + price pairs)",
    )
    unit: PrepaidUnit = Field(
        default=PrepaidUnit.REQUEST,
        description="Unit type: per request or per document",
    )
    payment_provider: str = Field(
        default="xendit",
        description="Payment provider: xendit or syft_accounting",
    )
    payment_provider_api_key: str | None = Field(
        default=None,
        description="API key for the payment provider",
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Users this policy applies to; ['*'] means all users",
    )


class PrepaidPolicy(BasePolicyType):
    """Prepaid quota policy: pre_hook checks remaining quota, post_hook decrements."""

    NAME = "prepaid"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Prepaid quota: buyers purchase bundles of requests in advance"

    @classmethod
    def icon(cls) -> str:
        return "🎟️"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return PrepaidConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Check if the user has remaining prepaid quota.

        Hard-blocks with a clear error if quota is exhausted.
        """
        if not configs:
            return context

        user_email = str(context.sender_email)
        prepaid_repo = context.metadata.get("prepaid_repository")

        if not prepaid_repo:
            raise PolicyViolationError(
                message="Prepaid policy system not configured",
                policy_type=self.NAME,
            )

        endpoint_id = context.metadata.get("endpoint_id")
        tenant_id = context.metadata.get("tenant_id")

        if not endpoint_id or not tenant_id:
            raise PolicyViolationError(
                message="Missing endpoint context for prepaid policy",
                policy_type=self.NAME,
            )

        subscription = await prepaid_repo.get_subscription(
            buyer_email=user_email,
            endpoint_id=endpoint_id,
        )

        if not subscription:
            raise PolicyViolationError(
                message=(
                    "No prepaid quota found. Please purchase a bundle to access this endpoint."
                ),
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "remaining_quota": 0,
                    "action": "purchase_required",
                },
            )

        if subscription.remaining_quota <= 0:
            raise PolicyViolationError(
                message=(
                    "Prepaid quota exhausted. Please purchase a new bundle to continue."
                ),
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "remaining_quota": 0,
                    "total_used": subscription.total_used,
                    "action": "purchase_required",
                },
            )

        context.metadata["prepaid_subscription_id"] = str(subscription.id)
        context.metadata["prepaid_remaining_before"] = subscription.remaining_quota
        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Decrement the user's prepaid quota after successful request."""
        if not configs:
            return context

        subscription_id = context.metadata.get("prepaid_subscription_id")
        if not subscription_id:
            return context

        prepaid_repo = context.metadata.get("prepaid_repository")
        if not prepaid_repo:
            return context

        decremented = await prepaid_repo.decrement_quota(subscription_id)
        before = context.metadata.get("prepaid_remaining_before", 0)
        remaining = max(before - 1, 0) if decremented else 0
        if context.response:
            if context.response.get("summary"):
                context.response["summary"]["prepaid_remaining"] = remaining
            if context.response.get("references"):
                context.response["references"]["prepaid_remaining"] = remaining

        return context

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = PrepaidConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid prepaid config: {e}") from e
