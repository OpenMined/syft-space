"""Gateway-specific wallet schemas."""

from pydantic import BaseModel, Field

from syft_space.components.wallets.gateway.stripe.config import StripeCurrencyCode
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


class CreateStripeWalletRequest(BaseModel):
    """Request to create a Stripe wallet.

    Unlike Xendit, there is no ``country`` field — Stripe doesn't require
    a per-wallet country lock.
    """

    secret_key: str = Field(
        ..., description="Stripe secret API key (sk_test_… or sk_live_…)"
    )
    webhook_secret: str = Field(
        ..., description="Stripe webhook endpoint signing secret (whsec_…)"
    )
    currency: StripeCurrencyCode = Field(..., description="Wallet currency")
    name: str | None = Field(None, description="Optional wallet label")


class UpdateStripeWalletRequest(BaseModel):
    """Request to update Stripe wallet credentials."""

    secret_key: str | None = Field(None, description="New Stripe secret key")
    webhook_secret: str | None = Field(None, description="New webhook signing secret")
