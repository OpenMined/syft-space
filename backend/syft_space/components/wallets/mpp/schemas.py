"""MPP-specific wallet schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CreateMppWalletRequest(BaseModel):
    """Request to generate a new MPP wallet keypair."""

    name: str | None = Field(None, description="Optional wallet label")


class ImportMppWalletRequest(BaseModel):
    """Request to import an MPP wallet from private key."""

    private_key: str = Field(..., description="Wallet private key (hex string)")
    name: str | None = Field(None, description="Optional wallet label")


class UpdateMppWalletAddressRequest(BaseModel):
    """Request to manually update MPP wallet address."""

    wallet_address: str = Field(..., description="Ethereum-format wallet address")

    @field_validator("wallet_address")
    @classmethod
    def validate_ethereum_address(cls, v: str) -> str:
        if not re.match(r"^0x[0-9a-fA-F]{40}$", v):
            raise ValueError(
                "Invalid Ethereum address format. Must be 0x followed by 40 hex characters."
            )
        return v


# Temporary — moves to payments component later
class TransactionResponse(BaseModel):
    """Response model for an on-chain transaction."""

    id: str = Field(..., description="Transaction ID")
    sender_email: str = Field(..., description="Sender address")
    recipient_email: str = Field(..., description="Recipient address")
    amount: float = Field(..., description="Transaction amount")
    status: str = Field(..., description="Transaction status")
    created_at: datetime = Field(..., description="Transaction timestamp")
    app_name: str | None = Field(None, description="Application name")
    app_ep_path: str | None = Field(None, description="Application endpoint path")


class MppBalanceResponse(BaseModel):
    """Response model for MPP wallet balance.

    Temporary — moves to payments component later.
    """

    balance: float = Field(..., description="Current wallet balance (pathUSD)")
    currency: str = Field(default="USD", description="Currency unit")
    recent_transactions: list[TransactionResponse] = Field(
        default_factory=list, description="Recent transactions"
    )
    wallet_configured: bool = Field(
        default=False, description="Whether wallet has credentials"
    )
