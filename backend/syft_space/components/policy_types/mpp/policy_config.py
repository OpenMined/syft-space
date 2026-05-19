"""Shared config for MPP payment policies (per-request, per-document).

The policy slug discriminates the unit; `price` is per-unit in USD.
Older policy rows used `price_per_request` or `price_per_document` —
both still validate via AliasChoices for graceful migration.
"""

from pydantic import AliasChoices, BaseModel, Field


class MppPaymentConfig(BaseModel):
    """Configuration shared by MPP per-request and per-document policies."""

    price: float = Field(
        ge=0,
        description="Price per unit in USD",
        validation_alias=AliasChoices(
            "price", "price_per_request", "price_per_document"
        ),
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user email patterns. Use '*' for all users.",
    )
