"""Payment API schemas for request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateInvoiceRequest(BaseModel):
    """Request model for creating a bundle purchase invoice."""

    endpoint_slug: str = Field(..., description="Slug of the endpoint to purchase for")
    bundle_name: str = Field(..., description="Name of the bundle to purchase")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "endpoint_slug": "my-rag",
                    "bundle_name": "Pro",
                }
            ]
        }
    )


class InvoiceResponse(BaseModel):
    """Response model for invoice details."""

    id: UUID
    endpoint_id: UUID
    user_email: str
    provider: str
    external_id: str
    checkout_url: str
    bundle_name: str
    amount: float
    currency: str
    status: str
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BundleUsageResponse(BaseModel):
    """Response model for bundle balance."""

    endpoint_slug: str
    user_email: str
    remaining_balance: float
    total_deposited: float

    model_config = ConfigDict(from_attributes=True)
