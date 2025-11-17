"""Tenant request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTenantRequest(BaseModel):
    """Request schema for creating a tenant."""

    name: str = Field(..., description="Unique tenant slug (e.g., 'acme-corp')")
    display_name: str = Field(
        ..., description="Display name (e.g., 'ACME Corporation')"
    )
    domain: Optional[str] = Field(
        None, description="Optional domain for subdomain-based tenant resolution"
    )
    metadata: dict = Field(
        default_factory=dict, description="Additional metadata (billing, limits, etc.)"
    )


class TenantResponse(BaseModel):
    """Response schema for tenant details."""

    id: UUID
    name: str
    display_name: str
    domain: Optional[str]
    is_active: bool
    metadata: dict
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
    domain: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True
