"""Wallet API schemas for request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateWalletRequest(BaseModel):
    """Request model for creating a wallet."""

    wallet_type: str = Field(..., description="Payment provider type (e.g., 'xendit')")
    api_key: str = Field(..., description="Provider API key")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "wallet_type": "xendit",
                "api_key": "xnd_development_...",
            }
        }


class WalletCreateResponse(BaseModel):
    """Response model for wallet creation.

    Includes callback_token (shown ONCE at creation time).
    The user must copy this to their provider's webhook settings.
    """

    id: UUID = Field(..., description="Unique identifier")
    wallet_type: str = Field(..., description="Payment provider type")
    is_active: bool = Field(..., description="Whether the wallet is active")
    webhook_url: str | None = Field(
        default=None, description="Webhook URL to configure in provider dashboard"
    )
    callback_token: str = Field(
        ...,
        description="Webhook verification token — copy to provider dashboard. Shown once.",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class WalletResponse(BaseModel):
    """Response model for wallet details.

    Credentials are never exposed in responses.
    """

    id: UUID = Field(..., description="Unique identifier")
    wallet_type: str = Field(..., description="Payment provider type")
    is_active: bool = Field(..., description="Whether the wallet is active")
    webhook_url: str | None = Field(
        default=None, description="Webhook URL to configure in provider dashboard"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class WalletListItem(BaseModel):
    """Response model for wallet in list view."""

    id: UUID = Field(..., description="Unique identifier")
    wallet_type: str = Field(..., description="Payment provider type")
    is_active: bool = Field(..., description="Whether the wallet is active")
    webhook_url: str | None = Field(default=None, description="Webhook URL")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True
