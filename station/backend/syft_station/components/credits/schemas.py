"""Credits API request/response schemas.

These shapes are a wire contract: every provisioned space ships a credits
client that bills paid queries against this API. Deployed spaces cannot be
assumed to update in lockstep with the station, so field names, status
codes, and body shapes must stay backward compatible.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class DebitRequest(BaseModel):
    """A space charging a paid query against a user's balance."""

    transaction_id: UUID = Field(
        description="Space-generated idempotency + correlation key"
    )
    user_email: str = Field(description="Space-asserted end user")
    amount: float = Field(gt=0, description="Charge in the station currency")
    endpoint: str = Field(default="", description="Endpoint slug (audit context)")
    charge_unit: str = Field(default="per_query")
    charge_quantity: int = Field(default=1, ge=1)


class DebitResponse(BaseModel):
    transaction_id: UUID
    balance_after: float
    currency: str


class RefundRequest(BaseModel):
    transaction_id: UUID = Field(description="The debit to reverse")


class RefundResponse(BaseModel):
    refunded: bool = True


class BalanceResponse(BaseModel):
    balance: float
    currency: str


# ── Wallet admin (station admin session) ────────────────────────────────────


class WalletSetupRequest(BaseModel):
    """Create or replace the station wallet.

    Credentials are provider-specific and validated by the matching
    gateway. On replace, the currency must stay the same — user balances
    are denominated in it.
    """

    provider: str = Field(description="Payment provider: xendit")
    currency: str = Field(min_length=3, max_length=3)
    credentials: dict = Field(
        description="Provider credentials, e.g. {api_key, callback_token}"
    )


class BundleInfo(BaseModel):
    name: str
    amount: float


class WalletStatusResponse(BaseModel):
    """Wallet state without secrets — served to admin and buyers alike."""

    configured: bool
    provider: str | None = None
    currency: str | None = None
    bundles: list[BundleInfo] = []


class WalletSetupResponse(WalletStatusResponse):
    """Setup result, including the rollout to pre-existing spaces."""

    spaces_attached: int = 0
    spaces_failed: int = 0


# ── Buyer checkout (any signed-in session) ──────────────────────────────────


class CheckoutRequest(BaseModel):
    bundle_name: str


class CheckoutResponse(BaseModel):
    invoice_id: UUID
    checkout_url: str
    amount: float
    currency: str
