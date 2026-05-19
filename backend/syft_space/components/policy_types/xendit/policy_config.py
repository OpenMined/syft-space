"""Shared config for Xendit payment policies (per-request, per-document).

Currency, country, and bundles live on the linked Wallet — not here.
The wallet's currency must match across all xendit policies that share it.
The policy slug discriminates the unit; `price` is per-unit in the wallet's
currency. Older policy rows used `price_per_request` or
`price_per_document` — both still validate via AliasChoices.
"""

from pydantic import AliasChoices, BaseModel, Field


class XenditPaymentConfig(BaseModel):
    """Configuration shared by Xendit per-request and per-document policies."""

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
