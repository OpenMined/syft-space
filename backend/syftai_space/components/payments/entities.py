"""PaymentService database entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from syftai_space.components.tenants.entities import Tenant


class PaymentService(SQLModel, table=True):
    """PaymentService entity for external payment service configuration (one per tenant)."""

    __tablename__ = "payment_services"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_payment_service_tenant"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant this payment service belongs to",
    )

    # Payment service credentials
    url: str = Field(default="", description="Payment service URL")
    email: str = Field(default="", description="Login email for payment service")
    password: str = Field(default="", description="Login password for payment service")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="payment_service")
