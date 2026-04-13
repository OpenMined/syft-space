"""Xendit payment policy type implementation.

Admin sets a price-per-request in a chosen currency. End users purchase
money bundles (pre-defined or custom). Balance is tracked as money and
deducted by price_per_request on each query.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from syft_space.components.policy_types.interfaces import (
    PolicyContext,
    PolicyViolationError,
    WalletPolicy,
)
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class CountryCode(StrEnum):
    """Country for Xendit accounting policy."""

    ID = "ID"
    PH = "PH"
    SG = "SG"
    MY = "MY"
    VN = "VN"
    TH = "TH"


class CurrencyCode(StrEnum):
    """Currency for Xendit accounting policy."""

    IDR = "IDR"
    USD = "USD"
    PHP = "PHP"
    SGD = "SGD"
    MYR = "MYR"
    VND = "VND"
    THB = "THB"


# Sensible default bundle amounts per currency.
# Used when the admin does not provide custom bundles.
DEFAULT_BUNDLES: dict[str, list["MoneyBundle"]] = {}  # populated after class def


class MoneyBundle(BaseModel):
    """A purchasable money bundle."""

    name: str = Field(..., description="Display name (e.g., 'Starter', 'Pro')")
    amount: float = Field(..., gt=0, description="Bundle price in the policy currency")


# Populate defaults now that MoneyBundle is defined
DEFAULT_BUNDLES.update(
    {
        CurrencyCode.IDR: [
            MoneyBundle(name="Starter", amount=10_000),
            MoneyBundle(name="Basic", amount=50_000),
            MoneyBundle(name="Pro", amount=100_000),
            MoneyBundle(name="Enterprise", amount=500_000),
        ],
        CurrencyCode.USD: [
            MoneyBundle(name="Starter", amount=1),
            MoneyBundle(name="Basic", amount=5),
            MoneyBundle(name="Pro", amount=10),
            MoneyBundle(name="Enterprise", amount=50),
        ],
        CurrencyCode.PHP: [
            MoneyBundle(name="Starter", amount=100),
            MoneyBundle(name="Basic", amount=500),
            MoneyBundle(name="Pro", amount=1_000),
            MoneyBundle(name="Enterprise", amount=5_000),
        ],
        CurrencyCode.SGD: [
            MoneyBundle(name="Starter", amount=1),
            MoneyBundle(name="Basic", amount=5),
            MoneyBundle(name="Pro", amount=10),
            MoneyBundle(name="Enterprise", amount=50),
        ],
        CurrencyCode.MYR: [
            MoneyBundle(name="Starter", amount=5),
            MoneyBundle(name="Basic", amount=20),
            MoneyBundle(name="Pro", amount=50),
            MoneyBundle(name="Enterprise", amount=200),
        ],
        CurrencyCode.VND: [
            MoneyBundle(name="Starter", amount=25_000),
            MoneyBundle(name="Basic", amount=100_000),
            MoneyBundle(name="Pro", amount=250_000),
            MoneyBundle(name="Enterprise", amount=1_000_000),
        ],
        CurrencyCode.THB: [
            MoneyBundle(name="Starter", amount=35),
            MoneyBundle(name="Basic", amount=150),
            MoneyBundle(name="Pro", amount=350),
            MoneyBundle(name="Enterprise", amount=1_500),
        ],
    }
)


class XenditPolicyConfig(BaseModel):
    """Configuration schema for xendit policy.

    Core pricing: price_per_request + currency.
    Bundles: optional list of MoneyBundle; defaults per currency if omitted.
    """

    price_per_request: float = Field(
        ..., gt=0, description="Cost per request in the chosen currency"
    )
    currency: CurrencyCode = Field(
        default=CurrencyCode.IDR, description="Currency code"
    )
    country: CountryCode = Field(
        default=CountryCode.ID, description="Country code for Xendit API"
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user emails or glob patterns. Use '*' for all users.",
    )
    bundles: list[MoneyBundle] | None = Field(
        default=None,
        description="Custom money bundles. If omitted, defaults for the currency are used.",
    )

    def applies_to_user(self, user_email: str) -> bool:
        """Check if this policy applies to the given user email."""
        return matches_any_pattern(user_email, self.applied_to)

    def get_bundles(self) -> list[MoneyBundle]:
        """Return custom bundles or currency defaults."""
        if self.bundles:
            return self.bundles
        return DEFAULT_BUNDLES.get(self.currency, [])

    def get_bundle(self, bundle_name: str) -> MoneyBundle | None:
        """Find a bundle by name, or None if not found."""
        return next((b for b in self.get_bundles() if b.name == bundle_name), None)


class XenditAccountingPolicy(WalletPolicy):
    """Xendit payment policy type.

    Admin sets price_per_request in a currency. End users buy money bundles
    and their balance is deducted by price_per_request on each query.
    """

    NAME = "xendit"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Pay-per-request via Xendit payment"

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
        """Pre-hook: deduct price_per_request from the user's money balance."""
        if not configs:
            return context

        user_email = str(context.sender_email)

        validated = [XenditPolicyConfig(**c) for c in configs]

        bundle_service = context.metadata.get("bundle_service")
        if not bundle_service:
            raise PolicyViolationError(
                message="Bundle service not available",
                policy_type=self.NAME,
                details={"user": user_email},
            )

        for config in validated:
            if not config.applies_to_user(user_email):
                continue

            endpoint_id = context.metadata.get("endpoint_id")
            tenant_id = context.metadata.get("tenant_id")

            if not endpoint_id or not tenant_id:
                raise PolicyViolationError(
                    message="Missing endpoint context for bundle check",
                    policy_type=self.NAME,
                    details={"user": user_email},
                )

            success = await bundle_service.reserve(
                user_email, endpoint_id, tenant_id, config.price_per_request
            )

            if not success:
                raise PolicyViolationError(
                    message="Insufficient balance. Please purchase more credits.",
                    policy_type=self.NAME,
                    details={
                        "user": user_email,
                        "price_per_request": config.price_per_request,
                        "currency": config.currency,
                    },
                )

            # Store for post-hook (no refund for requests, but keep pattern)
            context.metadata["xendit_deducted"] = config.price_per_request

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook: refund if the query produced no useful results."""
        if not configs:
            return context

        deducted = context.metadata.get("xendit_deducted")
        if not deducted:
            return context

        # Check whether the response has any content worth charging for
        response = context.response or {}
        has_summary = bool(
            response.get("summary") and response["summary"].get("message")
        )
        has_documents = bool(
            response.get("references") and response["references"].get("documents")
        )

        if has_summary or has_documents:
            return context

        # Empty response — refund the deduction
        bundle_service = context.metadata.get("bundle_service")
        if bundle_service:
            user_email = str(context.sender_email)
            endpoint_id = context.metadata.get("endpoint_id")
            tenant_id = context.metadata.get("tenant_id")

            if endpoint_id and tenant_id:
                await bundle_service.settle(
                    user_email, endpoint_id, tenant_id, deducted
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
