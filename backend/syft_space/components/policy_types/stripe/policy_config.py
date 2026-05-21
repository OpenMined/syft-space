"""Configs for Stripe payment policies.

``StripePaymentConfig`` is the shared base — price + applied_to. Subclasses
fix ``unit_type`` to a Literal const so the field is part of the schema (not
runtime-injected) and surfaces naturally through ``model_dump()`` to be
published to SyftHub.

Currency and bundles live on the linked Wallet — not here. The wallet's
currency must match across all Stripe policies that share it (enforced by
CapabilityChecker via the shared-wallet rule).

The AliasChoices on ``price`` mirrors Xendit's behavior for forward-compat
with any pre-launch admin tooling that may have shipped the legacy
``price_per_request`` / ``price_per_document`` names.
"""

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class StripePaymentConfig(BaseModel):
    """Shared base for all Stripe payment configs."""

    price: float = Field(
        gt=0,
        description="Cost per unit in the wallet's currency",
        validation_alias=AliasChoices(
            "price", "price_per_request", "price_per_document"
        ),
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user emails or glob patterns. Use '*' for all users.",
    )


class StripePerRequestConfig(StripePaymentConfig):
    """Config for StripePerRequestPolicy — charges price per query."""

    unit_type: Literal["request"] = "request"


class StripePerDocumentConfig(StripePaymentConfig):
    """Config for StripePerDocumentPolicy — charges price per retrieved document."""

    unit_type: Literal["document"] = "document"
