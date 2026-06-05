"""Prepaid policy API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BundleTierResponse(BaseModel):
    """A bundle tier available for purchase."""

    volume: int
    price: float
    currency: str = "USD"


class PrepaidSubscriptionResponse(BaseModel):
    """Subscriber info for seller's admin view."""

    id: UUID
    buyer_email: str
    endpoint_id: UUID
    remaining_quota: int
    total_purchased: int
    total_used: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PrepaidPurchaseResponse(BaseModel):
    """Individual purchase record."""

    id: UUID
    buyer_email: str
    endpoint_id: UUID
    volume: int
    price: float
    currency: str
    unit: str
    status: str
    payment_provider: str
    payment_reference: str | None
    invoice_url: str | None
    created_at: datetime
    activated_at: datetime | None

    class Config:
        from_attributes = True


class PrepaidSubscriberDetail(BaseModel):
    """Combined subscriber info with purchase history."""

    subscription: PrepaidSubscriptionResponse
    purchases: list[PrepaidPurchaseResponse]


class PrepaidEndpointStats(BaseModel):
    """Aggregated prepaid stats for an endpoint."""

    endpoint_id: UUID
    total_subscribers: int
    total_active_quota: int
    total_purchased: int
    total_used: int
    total_revenue: float
    currency: str = "USD"
    subscribers: list[PrepaidSubscriptionResponse]


class ActivatePurchaseRequest(BaseModel):
    """Request to manually activate a purchase."""

    purchase_id: UUID = Field(..., description="ID of the purchase to activate")


class PrepaidQuotaResponse(BaseModel):
    """Buyer's quota info for a specific endpoint."""

    endpoint_id: UUID
    remaining_quota: int
    total_purchased: int
    total_used: int
    is_active: bool
