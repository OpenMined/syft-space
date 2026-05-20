"""Configs for Xendit payment policies.

`XenditPaymentConfig` is the shared base — price + applied_to. Subclasses
fix `unit_type` to a Literal const so the field is part of the schema (not
runtime-injected) and surfaces naturally through `model_dump()` to be
published to SyftHub.

Currency, country, and bundles live on the linked Wallet — not here.
The wallet's currency must match across all xendit policies that share it.
Older policy rows used `price_per_request` or `price_per_document` as the
field name — both still validate via AliasChoices.
"""

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class XenditPaymentConfig(BaseModel):
    """Shared base for all Xendit payment configs."""

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


class XenditPerRequestConfig(XenditPaymentConfig):
    """Config for XenditPerRequestPolicy — charges price per query."""

    unit_type: Literal["request"] = "request"


class XenditPerDocumentConfig(XenditPaymentConfig):
    """Config for XenditPerDocumentPolicy — charges price per retrieved document."""

    unit_type: Literal["document"] = "document"
