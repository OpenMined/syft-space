"""Marketplace database entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Column, Field, ForeignKey, Relationship, SQLModel

from syft_space.config import app_settings

if TYPE_CHECKING:
    from syft_space.components.tenants.entities import Tenant


class Marketplace(SQLModel, table=True):
    """Marketplace entity representing an external marketplace for publishing endpoints."""

    __tablename__ = "marketplaces"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    name: str = Field(..., description="Marketplace display name")
    username: str = Field(..., description="Marketplace username")
    url: str = Field(
        default_factory=lambda: str(app_settings.default_marketplace_url),
        description="Marketplace base URL",
    )
    email: str = Field(default="", description="Login email for marketplace")
    password: str = Field(default="", description="Login password for marketplace")
    satellite_id: str | None = Field(
        default=None,
        description="Id of this space's satellite on the marketplace — the "
        "registry row that scopes endpoint sync, health and token audience "
        "to this space rather than the whole account",
    )
    is_default: bool = Field(
        default=False, description="Is this the default marketplace (e.g., SyftHub)"
    )
    is_active: bool = Field(
        default=True, description="Can be used for publishing endpoints"
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="marketplaces")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "SyftHub",
                "url": "https://syftbox.openmined.org",
                "email": "user@example.com",
                "password": "secret",
                "is_default": True,
                "is_active": True,
            }
        }
