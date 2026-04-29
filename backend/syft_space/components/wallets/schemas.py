"""Shared wallet schemas for request/response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    """Response model for wallet details.

    The `display` field carries type-specific info for the frontend:
    - MPP: {"wallet_address": "0x..."}
    - Xendit: {"webhook_url": "https://..."}

    Credentials are NEVER exposed in responses.
    """

    id: UUID = Field(..., description="Wallet ID")
    wallet_type: str = Field(..., description="Wallet type (e.g., 'mpp', 'xendit')")
    name: str = Field(..., description="User-facing wallet label")
    currency: str = Field(..., description="Wallet currency (e.g., 'IDR', 'USD')")
    country: str | None = Field(default=None, description="Country code (ISO 3166-1)")
    is_active: bool = Field(..., description="Whether wallet is active")
    display: dict[str, Any] = Field(
        default_factory=dict, description="Type-specific display info for frontend"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class WalletListItem(BaseModel):
    """Compact response model for wallet in list view."""

    id: UUID = Field(..., description="Wallet ID")
    wallet_type: str = Field(..., description="Wallet type")
    name: str = Field(..., description="User-facing wallet label")
    currency: str = Field(..., description="Wallet currency")
    country: str | None = Field(default=None, description="Country code")
    is_active: bool = Field(..., description="Whether wallet is active")
    display: dict[str, Any] = Field(
        default_factory=dict, description="Type-specific display info"
    )
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True
