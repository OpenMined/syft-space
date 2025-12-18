"""Tenant database entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from components.datasets.entities import Dataset
    from components.endpoints.entities import Endpoint
    from components.marketplaces.entities import Marketplace
    from components.models.entities import Model
    from components.payments.entities import PaymentService
    from components.policies.entities import Policy


class Tenant(SQLModel, table=True):
    """Tenant entity for multi-tenancy support."""

    __tablename__ = "tenants"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(
        ...,
        unique=True,
        index=True,
        description="Unique tenant slug (e.g., 'acme-corp')",
    )
    display_name: str = Field(
        ..., description="Display name (e.g., 'ACME Corporation')"
    )
    domain: str | None = Field(
        default=None,
        unique=True,
        index=True,
        description="Optional domain for subdomain-based tenant resolution",
    )
    is_active: bool = Field(default=True, description="Whether tenant is active")
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Additional metadata (billing, limits, etc.)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Reverse relationships
    datasets: list["Dataset"] = Relationship(back_populates="tenant")
    models: list["Model"] = Relationship(back_populates="tenant")
    endpoints: list["Endpoint"] = Relationship(back_populates="tenant")
    policies: list["Policy"] = Relationship(back_populates="tenant")
    marketplaces: list["Marketplace"] = Relationship(back_populates="tenant")
    payment_service: Optional["PaymentService"] = Relationship(back_populates="tenant")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "acme-corp",
                "display_name": "ACME Corporation",
                "domain": "acme.example.com",
                "is_active": True,
                "meta": {"billing_plan": "enterprise", "max_users": 100},
            }
        }
