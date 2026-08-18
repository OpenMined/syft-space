"""MPP payment schemas — financial data responses."""

from datetime import datetime

from pydantic import BaseModel, Field


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
    """Response model for MPP wallet balance (on-chain)."""

    balance: float = Field(..., description="Current wallet balance (pathUSD)")
    currency: str = Field(default="USD", description="Currency unit")
    recent_transactions: list[TransactionResponse] = Field(
        default_factory=list, description="Recent transactions"
    )
    wallet_configured: bool = Field(
        default=False, description="Whether wallet has credentials"
    )
