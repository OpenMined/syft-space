"""Payment API schemas for request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateInvoiceRequest(BaseModel):
    """Request model for creating a bundle purchase invoice."""

    endpoint_slug: str = Field(..., description="Slug of the endpoint to purchase for")
    tier_name: str = Field(..., description="Name of the bundle tier to purchase")

    class Config:
        json_schema_extra = {
            "example": {
                "endpoint_slug": "my-rag",
                "tier_name": "Pro",
            }
        }


class InvoiceResponse(BaseModel):
    """Response model for invoice details."""

    id: UUID
    endpoint_id: UUID
    user_email: str
    provider: str
    external_id: str
    checkout_url: str
    tier_name: str
    tier_units: int
    unit_type: str
    amount: float
    currency: str
    status: str
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BundleUsageResponse(BaseModel):
    """Response model for bundle balance."""

    endpoint_slug: str
    user_email: str
    unit_type: str
    remaining_units: int
    total_purchased: int

    class Config:
        from_attributes = True
