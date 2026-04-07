"""Payment database entities."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from syft_space.components.endpoints.entities import Endpoint
    from syft_space.components.tenants.entities import Tenant


class InvoiceStatus(str, Enum):
    """Invoice lifecycle status."""

    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    FAILED = "failed"


class Invoice(SQLModel, table=True):
    """Invoice entity tracking payment lifecycle.

    Created when a user initiates a bundle purchase. Status transitions:
    pending → paid (webhook confirms payment)
    pending → expired (provider timeout)
    pending → failed (payment declined)
    """

    __tablename__ = "invoices"
    __table_args__ = (
        Index("idx_invoice_external_id", "external_id", unique=True),
        Index("idx_invoice_tenant_user", "tenant_id", "user_email"),
        Index("idx_invoice_status", "status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    endpoint_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("endpoints.id", ondelete="SET NULL"), nullable=True
        ),
        description="Endpoint this invoice is for (NULL if endpoint deleted)",
    )
    user_email: str = Field(..., description="Email of the purchasing user")
    provider: str = Field(..., description="Payment provider (e.g., 'xendit')")
    external_id: str = Field(..., description="Provider invoice ID (webhook join key)")
    checkout_url: str = Field(..., description="Provider hosted checkout URL")
    tier_name: str = Field(..., description="Bundle tier name at time of purchase")
    tier_units: int = Field(..., description="Number of units in the purchased tier")
    unit_type: str = Field(..., description="Unit type (e.g., 'requests', 'tokens')")
    amount: float = Field(..., description="Invoice amount")
    currency: str = Field(..., description="Currency code (e.g., 'USD')")
    status: str = Field(
        default=InvoiceStatus.PENDING.value, description="Invoice status"
    )
    webhook_payload: dict | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Raw provider webhook payload",
    )
    paid_at: datetime | None = Field(
        default=None, description="When payment was confirmed"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="invoices")
    endpoint: "Endpoint" = Relationship(back_populates="invoices")


class BundleUsage(SQLModel, table=True):
    """Bundle usage tracking per (user, endpoint, unit_type).

    Remaining units stack on purchase and decrement atomically on query.
    """

    __tablename__ = "bundle_usage"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "endpoint_id",
            "user_email",
            "unit_type",
            name="uq_bundle_usage_user_endpoint_type",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    endpoint_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("endpoints.id", ondelete="CASCADE")),
        description="Endpoint this usage tracks",
    )
    user_email: str = Field(..., description="User email")
    unit_type: str = Field(
        ..., description="Unit type (e.g., 'requests', 'tokens', 'documents')"
    )
    remaining_units: int = Field(default=0, description="Remaining units available")
    total_purchased: int = Field(
        default=0, description="Lifetime total units purchased"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="bundle_usages")
    endpoint: "Endpoint" = Relationship(back_populates="bundle_usages")
