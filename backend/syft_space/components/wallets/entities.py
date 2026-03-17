"""Wallet database entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from syft_space.components.tenants.entities import Tenant


class Wallet(SQLModel, table=True):
    """Wallet entity for storing payment provider credentials.

    Each tenant can have one wallet per provider type (e.g., one Xendit wallet).
    Credentials are stored as a JSON blob to support different providers.
    """

    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "wallet_type", name="uq_wallet_tenant_type"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    wallet_type: str = Field(..., description="Payment provider type (e.g., 'xendit')")
    credentials: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Provider credentials (e.g., api_key, callback_token)",
    )
    is_active: bool = Field(default=True, description="Whether the wallet is active")
    webhook_url: str | None = Field(
        default=None,
        description="Generated webhook URL for this wallet",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="wallets")
