"""Marketplace API schemas for request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from syftai_space.config import app_settings


class RegisterMarketplaceRequest(BaseModel):
    """Request model for registering a new marketplace (new SyftHub account)."""

    name: str = Field(..., description="Marketplace display name (unique per tenant)")
    username: str = Field(..., description="Marketplace username (unique per tenant)")
    url: HttpUrl = Field(
        description="Marketplace base URL (unique per tenant)",
        default=app_settings.default_marketplace_url,
    )
    email: EmailStr = Field(..., description="Login email for marketplace")
    password: str = Field(..., description="Login password for marketplace")
    accounting_url: HttpUrl = Field(
        description="Accounting service URL",
        default=app_settings.default_accounting_url,
    )
    accounting_password: str | None = Field(
        None, description="Accounting service password"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "My Marketplace",
                "username": "myusername",
                "url": "https://marketplace.example.com",
                "email": "user@example.com",
                "password": "secret123",
                "accounting_url": "https://accounting.example.com",
            }
        }


class ConnectMarketplaceRequest(BaseModel):
    """Request model for connecting to an existing SyftHub account."""

    username: str = Field(..., description="SyftHub username")
    password: str = Field(..., description="SyftHub password")
    url: HttpUrl = Field(
        description="Marketplace base URL",
        default=app_settings.default_marketplace_url,
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "username": "myusername",
                "password": "secret123",
                "url": "https://marketplace.example.com",
            }
        }


class MarketplaceResponse(BaseModel):
    """Response model for marketplace details."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Marketplace display name")
    url: str = Field(..., description="Marketplace base URL")
    email: str = Field(..., description="Login email")
    # Note: password is NOT returned for security
    is_default: bool = Field(..., description="Is this the default marketplace")
    is_active: bool = Field(..., description="Can be used for publishing")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class MarketplaceListItem(BaseModel):
    """Response model for marketplace in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Marketplace display name")
    url: str = Field(..., description="Marketplace base URL")
    is_default: bool = Field(..., description="Is this the default marketplace")
    is_active: bool = Field(..., description="Can be used for publishing")

    class Config:
        """Pydantic config."""

        from_attributes = True


class BalanceResponse(BaseModel):
    """Response model for account balance."""

    balance: float = Field(..., description="Current account balance")
    currency: str = Field(default="USD", description="Currency unit")
