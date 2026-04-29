"""Gateway-specific wallet schemas."""

from pydantic import BaseModel, Field

from syft_space.components.wallets.gateway.xendit.config import (
    CountryCode,
    CurrencyCode,
    MoneyBundle,
)


class CreateXenditWalletRequest(BaseModel):
    """Request to create a Xendit wallet."""

    api_key: str = Field(..., description="Xendit API key")
    callback_token: str = Field(
        ..., description="Xendit webhook callback verification token"
    )
    currency: CurrencyCode = Field(..., description="Wallet currency")
    country: CountryCode = Field(..., description="Country code for Xendit API")
    bundles: list[MoneyBundle] | None = Field(
        default=None,
        description="Custom money bundles. Defaults for the currency are used if omitted.",
    )
    name: str | None = Field(None, description="Optional wallet label")


class UpdateXenditWalletRequest(BaseModel):
    """Request to update Xendit wallet credentials."""

    api_key: str | None = Field(None, description="New Xendit API key")
    callback_token: str | None = Field(
        None, description="New callback verification token"
    )
    bundles: list[MoneyBundle] | None = Field(
        None, description="Replacement money bundles (currency/country are immutable)"
    )
