"""Credits API request/response schemas.

These shapes are a wire contract: every provisioned space ships a credits
client that bills paid queries against this API. Deployed spaces cannot be
assumed to update in lockstep with the station, so field names, status
codes, and body shapes must stay backward compatible.
"""

from datetime import datetime
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
    are denominated in it. The SyftHub identity that verifies buyers is set
    separately, once per station.
    """

    provider: str = Field(description="Payment provider: xendit | stripe")
    currency: str = Field(min_length=3, max_length=3)
    credentials: dict = Field(
        description="Provider credentials: {api_key, callback_token} for "
        "Xendit, {secret_key, webhook_secret} for Stripe"
    )


class WalletStatusResponse(BaseModel):
    """Wallet state without secrets — served to admin and buyers alike.

    Bundles are intentionally absent: the purchase catalog lives with the
    spaces (per-currency, published on their endpoints). The station only
    moves money — it charges whatever amount a checkout names.
    """

    configured: bool
    provider: str | None = None
    currency: str | None = None


class WalletSetupResponse(WalletStatusResponse):
    """Setup result, including the rollout to pre-existing spaces."""

    spaces_attached: int = 0
    spaces_failed: int = 0


class CreateInvoiceRequest(BaseModel):
    """SyftHub buys a bundle by name — same body as the self-hosted gateway."""

    bundle_name: str = Field(description="Name of the bundle to purchase")
    endpoint_slug: str | None = Field(
        default=None,
        description="Optional originating endpoint slug (analytics context)",
    )


class BuyerInvoiceResponse(BaseModel):
    """One invoice, shaped exactly like the self-hosted gateway's
    InvoiceResponse — SyftHub reads managed and self-hosted with one client."""

    id: UUID
    wallet_id: UUID | None
    endpoint_id: UUID | None = None
    user_email: str
    provider: str
    client_reference: str
    checkout_url: str
    provider_session_id: str | None = None
    bundle_name: str
    amount: float
    currency: str
    status: str
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BuyerBalanceResponse(BaseModel):
    """Wallet-scoped balance — mirrors the gateway's UserBalanceResponse."""

    wallet_id: UUID
    user_email: str
    balance: float
    currency: str


class TopUpInfo(BaseModel):
    """One purchase — the buyer's own history and the admin feed."""

    invoice_id: UUID
    user_email: str
    bundle_name: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    paid_at: datetime | None


# ── Earnings + payouts (station admin) ──────────────────────────────────────


class EarningsTotals(BaseModel):
    credits_sold: float = Field(description="Σ settled top-ups")
    earned: float = Field(description="Σ debits − reversals, all spaces")
    paid_out: float = Field(description="Σ recorded payouts")
    outstanding_balance: float = Field(description="Σ unspent user credit")


class SpaceEarnings(BaseModel):
    space_id: UUID
    name: str
    subdomain: str
    owner_email: str
    deleted: bool = Field(description="Space was torn down; money stays payable")
    earned: float
    query_count: int = Field(description="Paid queries net of reversals")
    paid_out: float
    payable: float = Field(description="earned − paid_out")


class EndpointEarnings(BaseModel):
    space_id: UUID
    endpoint: str
    earned: float
    query_count: int


class DailyEarnings(BaseModel):
    day: str = Field(description="YYYY-MM-DD")
    space_id: UUID
    earned: float
    query_count: int


class PayoutInfo(BaseModel):
    id: UUID
    space_id: UUID
    amount: float
    note: str
    created_at: datetime


class EarningsResponse(BaseModel):
    """Everything the Earnings dashboard renders, derived from the ledger.

    Space rows carry their own name/owner attribution (resolved from the
    request rows, which survive deletion) — endpoint/daily rows carry
    space_id only and group under them.
    """

    currency: str
    totals: EarningsTotals
    spaces: list[SpaceEarnings]
    endpoints: list[EndpointEarnings]
    daily: list[DailyEarnings]
    recent_top_ups: list[TopUpInfo]
    payouts: list[PayoutInfo]


class MemberSpaceEarnings(BaseModel):
    """One of the member's spaces, money-wise. The headline number for
    members is payable — what the admin still owes them."""

    space_id: UUID
    name: str
    subdomain: str
    deleted: bool = Field(description="Space was torn down; money stays payable")
    earned: float
    query_count: int
    paid_out: float
    payable: float


class MemberEarningsResponse(BaseModel):
    currency: str
    spaces: list[MemberSpaceEarnings]
    total_earned: float
    total_paid_out: float
    total_payable: float


class OutstandingBalance(BaseModel):
    user_email: str
    topped_up: float
    spent: float
    balance: float


class OutstandingBalancesResponse(BaseModel):
    total: float
    balances: list[OutstandingBalance]


class PayoutRequest(BaseModel):
    space_id: UUID
    amount: float = Field(gt=0)
    note: str = ""


class PayoutResponse(BaseModel):
    id: UUID
    space_id: UUID
    amount: float
    note: str
    created_at: datetime
    payable_after: float = Field(description="What the space is still owed")


class ReversalResponse(BaseModel):
    reversed: bool = True
