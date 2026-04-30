"""Gateway-specific wallet schemas."""

from pydantic import BaseModel, Field

from syft_space.components.wallets.gateway.xendit.config import (
    CountryCode,
    CurrencyCode,
)


class CreateXenditWalletRequest(BaseModel):
    """Request to create a Xendit wallet."""

    api_key: str = Field(..., description="Xendit API key")
    callback_token: str = Field(
        ..., description="Xendit webhook callback verification token"
    )
    currency: CurrencyCode = Field(..., description="Wallet currency")
    country: CountryCode = Field(..., description="Country code for Xendit API")
    name: str | None = Field(None, description="Optional wallet label")


class UpdateXenditWalletRequest(BaseModel):
    """Request to update Xendit wallet credentials."""

    api_key: str | None = Field(None, description="New Xendit API key")
    callback_token: str | None = Field(
        None, description="New callback verification token"
    )
