"""Payment API schemas for request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateInvoiceRequest(BaseModel):
    """Request model for creating a bundle purchase invoice.

    Wallet-scoped: the user buys credits against a wallet (not an endpoint).
    `endpoint_slug` is optional context for analytics — where the user clicked
    through from.
    """

    bundle_name: str = Field(..., description="Name of the bundle to purchase")
    endpoint_slug: str | None = Field(
        default=None,
        description="Optional originating endpoint slug (analytics context)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "bundle_name": "Pro",
                    "endpoint_slug": "my-rag",
                }
            ]
        }
    )


class InvoiceResponse(BaseModel):
    """Response model for invoice details."""

    id: UUID
    wallet_id: UUID | None
    endpoint_id: UUID | None
    user_email: str
    provider: str
    external_id: str
    checkout_url: str
    provider_session_id: str | None = None
    bundle_name: str
    amount: float
    currency: str
    status: str
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBalanceResponse(BaseModel):
    """Wallet-scoped money balance for a user."""

    wallet_id: UUID
    user_email: str
    balance: float
    currency: str

    model_config = ConfigDict(from_attributes=True)


class LedgerEntryResponse(BaseModel):
    """Single spend-ledger entry (debit or cancelled)."""

    id: UUID
    transaction_id: UUID
    type: str
    amount: float
    currency: str
    charge_unit: str
    charge_quantity: int
    user_email: str
    wallet_id: UUID | None
    endpoint_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LedgerEntryPage(BaseModel):
    """Cursor-paginated ledger entry listing."""

    items: list[LedgerEntryResponse]
    next_cursor: str | None = None
