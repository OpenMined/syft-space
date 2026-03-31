"""Marketplace API schemas for request/response models."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from syft_space.config import app_settings


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

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "My Marketplace",
                "username": "myusername",
                "url": "https://marketplace.example.com",
                "email": "user@example.com",
                "password": "secret123",
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
    username: str = Field(..., description="Marketplace username")
    email: str = Field(..., description="Login email")
    url: str = Field(..., description="Marketplace base URL")
    is_default: bool = Field(..., description="Is this the default marketplace")
    is_active: bool = Field(..., description="Can be used for publishing")

    class Config:
        """Pydantic config."""

        from_attributes = True


class TransactionResponse(BaseModel):
    """Response model for a transaction."""

    id: str = Field(..., description="Transaction ID")
    sender_email: str = Field(..., description="Sender's email")
    recipient_email: str = Field(..., description="Recipient's email")
    amount: float = Field(..., description="Transaction amount")
    status: str = Field(..., description="Transaction status")
    created_at: datetime = Field(..., description="Transaction creation timestamp")
    app_name: str | None = Field(None, description="Application name")
    app_ep_path: str | None = Field(None, description="Application endpoint path")


class BalanceResponse(BaseModel):
    """Response model for account balance."""

    balance: float = Field(..., description="Current account balance")
    currency: str = Field(default="USD", description="Currency unit")
    recent_transactions: list[TransactionResponse] = Field(
        default_factory=list, description="Recent transactions (last 3)"
    )
    wallet_configured: bool = Field(
        default=False, description="Whether an MPP wallet is configured"
    )


class WalletResponse(BaseModel):
    """Response model for wallet info."""

    address: str | None = Field(None, description="Tempo wallet address")
    exists: bool = Field(False, description="Whether a wallet is configured")


class CreateWalletResponse(BaseModel):
    """Response after creating a new wallet."""

    address: str = Field(..., description="Generated wallet address")


class ImportWalletRequest(BaseModel):
    """Request to import an existing wallet."""

    private_key: str = Field(..., description="Wallet private key (hex string)")


class UpdateWalletAddressRequest(BaseModel):
    """Request to manually set wallet address (without private key)."""

    wallet_address: str = Field(..., description="Ethereum-format wallet address")

    @field_validator("wallet_address")
    @classmethod
    def validate_ethereum_address(cls, v: str) -> str:
        if not re.match(r"^0x[0-9a-fA-F]{40}$", v):
            raise ValueError(
                "Invalid Ethereum address format. Must be 0x followed by 40 hex characters."
            )
        return v
