"""Credits API request/response schemas.

The space-facing shapes implement the pinned credits contract (station.md,
2026-07-16) that syft-space's ClusterCreditsClient is already built
against — field names and status semantics are frozen by that client.
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
