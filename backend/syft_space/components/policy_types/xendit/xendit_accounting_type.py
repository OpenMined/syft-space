"""Xendit bundle payment policy type implementation."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from syft_space.components.policy_types.interfaces import (
    PolicyContext,
    PolicyViolationError,
    WalletPolicy,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator


class BundleTier(BaseModel):
    """A single bundle tier within the xendit policy config."""

    name: str = Field(..., description="Tier display name (e.g., 'Starter', 'Pro')")
    units: int = Field(..., gt=0, description="Number of units in this tier")
    unit_type: str = Field(
        default="requests",
        description="Unit type: 'requests', 'tokens', or 'documents'",
    )
    price: float = Field(..., gt=0, description="Price for this tier")


class XenditPolicyConfig(BaseModel):
    """Configuration schema for xendit policy."""

    bundle_tiers: list[BundleTier] = Field(
        ..., min_length=1, description="Available bundle tiers for purchase"
    )
    currency: str = Field(default="USD", description="Currency for all tiers")
    country: str = Field(
        default="ID",
        description="ISO 3166-1 alpha-2 country code (e.g., 'ID', 'PH', 'SG', 'MY', 'VN', 'TH')",
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user emails or glob patterns. Use '*' for all users.",
    )

    @model_validator(mode="after")
    def validate_consistent_unit_type(self) -> "XenditPolicyConfig":
        """All tiers must have the same unit_type."""
        unit_types = {tier.unit_type for tier in self.bundle_tiers}
        if len(unit_types) > 1:
            raise ValueError(
                f"All tiers must have the same unit_type, got: {sorted(unit_types)}"
            )
        return self


class XenditAccountingPolicy(WalletPolicy):
    """Xendit bundle payment policy type.

    Pre-purchased request bundles via Xendit payment provider.
    Users buy a bundle of N requests, then consume them on queries.

    Mutually exclusive with AccountingPolicy (same POLICY_GROUP = "payment").
    """

    NAME = "xendit"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Pre-purchased request bundles via Xendit payment"

    @classmethod
    def required_wallet_type(cls) -> str:
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
        """Pre-hook: reserve units from the user's bundle balance.

        Reads BundleService from context.metadata (injected by endpoint handler).
        For unit_type="requests", reserves 1 unit per query.
        """
        if not configs:
            return context

        user_email = str(context.sender_email)

        # Validate configs
        validated = [XenditPolicyConfig(**c) for c in configs]

        bundle_service = context.metadata.get("bundle_service")
        if not bundle_service:
            raise PolicyViolationError(
                message="Bundle service not available",
                policy_type=self.NAME,
                details={"user": user_email},
            )

        for config in validated:
            if not self._applies_to_user(user_email, config.applied_to):
                continue

            # Use the first tier's unit_type to determine reservation
            # All tiers on an endpoint share the same unit_type
            unit_type = config.bundle_tiers[0].unit_type

            if unit_type == "requests":
                reserve_amount = 1
            else:
                # For tokens/documents, reserve max from tier config
                # (settle will refund unused portion)
                max_units = max(t.units for t in config.bundle_tiers)
                reserve_amount = context.metadata.get("max_units_per_query", max_units)

            endpoint_id = context.metadata.get("endpoint_id")
            tenant_id = context.metadata.get("tenant_id")

            if not endpoint_id or not tenant_id:
                raise PolicyViolationError(
                    message="Missing endpoint context for bundle check",
                    policy_type=self.NAME,
                    details={"user": user_email},
                )

            success = await bundle_service.reserve(
                user_email, endpoint_id, tenant_id, unit_type, reserve_amount
            )

            if not success:
                raise PolicyViolationError(
                    message="Insufficient bundle balance. Please purchase more units.",
                    policy_type=self.NAME,
                    details={
                        "user": user_email,
                        "unit_type": unit_type,
                        "required": reserve_amount,
                    },
                )

            # Store reservation info for post-hook
            context.metadata["xendit_reserved_amount"] = reserve_amount
            context.metadata["xendit_unit_type"] = unit_type

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook: settle reservation (refund unused portion if applicable).

        For unit_type="requests", actual always equals reserved (no refund).
        For tokens/documents, actual_usage from query pipeline determines refund.
        """
        if not configs:
            return context

        reserved_amount = context.metadata.get("xendit_reserved_amount")
        if not reserved_amount:
            return context

        unit_type = context.metadata.get("xendit_unit_type", "requests")
        actual_usage = context.metadata.get("actual_usage", reserved_amount)
        refund = reserved_amount - actual_usage

        if refund > 0:
            bundle_service = context.metadata.get("bundle_service")
            if bundle_service:
                user_email = str(context.sender_email)
                endpoint_id = context.metadata.get("endpoint_id")
                tenant_id = context.metadata.get("tenant_id")

                if endpoint_id and tenant_id:
                    await bundle_service.settle(
                        user_email, endpoint_id, tenant_id, unit_type, refund
                    )

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
