"""Prepaid policy database entities for quota tracking."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Index
from sqlmodel import Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from syft_space.components.endpoints.entities import Endpoint
    from syft_space.components.tenants.entities import Tenant


class PurchaseStatus(str, Enum):
    """Status of a prepaid purchase."""

    PENDING = "pending"
    PAID = "paid"
    ACTIVATED = "activated"
    EXPIRED = "expired"


class PrepaidSubscription(SQLModel, table=True):
    """Tracks a buyer's prepaid quota for a specific endpoint.

    One subscription per (buyer_email, endpoint_id) pair. Multiple purchases
    stack their quotas into this single subscription record.
    """

    __tablename__ = "prepaid_subscriptions"
    __table_args__ = (
        Index(
            "idx_prepaid_sub_tenant_endpoint",
            "tenant_id",
            "endpoint_id",
        ),
        Index(
            "idx_prepaid_sub_buyer_endpoint",
            "buyer_email",
            "endpoint_id",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
    )
    endpoint_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("endpoints.id", ondelete="CASCADE")),
    )
    buyer_email: str = Field(..., description="Email of the buyer")
    remaining_quota: int = Field(
        default=0, description="Remaining requests in the quota"
    )
    total_purchased: int = Field(
        default=0, description="Total requests ever purchased (across all bundles)"
    )
    total_used: int = Field(
        default=0, description="Total requests consumed"
    )
    is_active: bool = Field(default=True, description="Whether the subscription is active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    tenant: "Tenant" = Relationship()
    endpoint: "Endpoint" = Relationship()
    purchases: list["PrepaidPurchase"] = Relationship(back_populates="subscription")


class PrepaidPurchase(SQLModel, table=True):
    """Records an individual bundle purchase within a prepaid subscription.

    Each purchase represents a single bundle buy (e.g. 1000 requests for $10).
    When activated, the volume is added to the subscription's remaining_quota.
    """

    __tablename__ = "prepaid_purchases"
    __table_args__ = (
        Index(
            "idx_prepaid_purchase_subscription",
            "subscription_id",
        ),
        Index(
            "idx_prepaid_purchase_payment_ref",
            "payment_reference",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
    )
    subscription_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("prepaid_subscriptions.id", ondelete="CASCADE")),
    )
    endpoint_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("endpoints.id", ondelete="CASCADE")),
    )
    buyer_email: str = Field(..., description="Email of the buyer")
    volume: int = Field(..., description="Number of requests in this bundle")
    price: float = Field(..., description="Price paid for this bundle")
    currency: str = Field(default="USD", description="Currency of the price")
    unit: str = Field(default="request", description="Unit type: request or document")
    status: PurchaseStatus = Field(
        default=PurchaseStatus.PENDING, description="Purchase status"
    )
    payment_provider: str = Field(
        default="manual", description="Payment provider (xendit, manual)"
    )
    payment_reference: str | None = Field(
        default=None, description="External payment/invoice ID"
    )
    invoice_url: str | None = Field(
        default=None, description="URL for buyer to complete payment"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: datetime | None = Field(
        default=None, description="When the purchase was activated"
    )

    subscription: PrepaidSubscription = Relationship(back_populates="purchases")
