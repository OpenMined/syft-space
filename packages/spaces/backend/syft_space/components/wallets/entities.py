"""Wallet database entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import (
    JSON,
    Column,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
    UniqueConstraint,
)

if TYPE_CHECKING:
    from syft_space.components.tenants.entities import Tenant


class Wallet(SQLModel, table=True):
    """Wallet entity storing credentials for payment providers.

    Supports two categories:
    - mpp: Blockchain/token wallets (e.g., Tempo/MPP)
    - gateway: Payment gateway wallets (e.g., Xendit, Stripe, Razorpay)

    The `configuration` JSON blob is validated by a type-specific Pydantic
    config class (see wallet_configs.py). `currency` and `country` are
    surfaced as columns so they can be queried and uniqueness-constrained.

    Currency is locked once any UserBalance or LedgerEntry row exists
    for this wallet — see WalletHandler.update_*.
    """

    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "wallet_type",
            "currency",
            name="uq_wallet_tenant_type_currency",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    wallet_type: str = Field(
        ..., description="Wallet type identifier (e.g., 'mpp', 'xendit', 'stripe')"
    )
    name: str = Field(..., description="User-facing wallet label")
    currency: str = Field(..., description="Wallet currency code (e.g., 'IDR', 'USD')")
    country: str | None = Field(
        default=None,
        description="Country code (e.g., 'ID'); optional — region-specific providers only",
    )
    configuration: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Type-specific credentials and config (validated by config class)",
    )
    is_active: bool = Field(default=True, description="Whether wallet is active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="wallets")
