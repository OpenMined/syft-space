"""Tenant request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTenantRequest(BaseModel):
    """Request schema for creating a tenant."""

    name: str = Field(..., description="Unique tenant slug (e.g., 'acme-corp')")
    display_name: str = Field(
        ..., description="Display name (e.g., 'ACME Corporation')"
    )
    domain: str | None = Field(
        None, description="Optional domain for subdomain-based tenant resolution"
    )
    meta: dict = Field(
        default_factory=dict, description="Additional metadata (billing, limits, etc.)"
    )


class TenantResponse(BaseModel):
    """Response schema for tenant details."""

    id: UUID
    name: str
    display_name: str
    domain: str | None
    is_active: bool
    meta: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class TenantListItem(BaseModel):
    """Response schema for tenant list items."""

    id: UUID
    name: str
    display_name: str
    domain: str | None
    is_active: bool
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True
