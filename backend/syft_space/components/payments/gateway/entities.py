"""Payment database entities.

Two-table money-balance model:
- UserBalance: per (tenant, wallet, user) materialized aggregate. Hot path.
- LedgerEntry: per money movement, append-only ledger. Source of truth.

`user_email` is a soft reference to a SyftHub-managed identity. Removed users
leave behind balance + ledger rows that are not auto-cleaned. Future:
SyftHub-authenticated DELETE endpoint (satellite token) to scrub them.

Retention: LedgerEntry rows are kept forever for now. Revisit if query
volume warrants partitioning or archival.
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, ForeignKey, SQLModel


class InvoiceStatus(str, Enum):
    """Invoice lifecycle status."""

    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"  # provider session timed out
    CANCELLED = "cancelled"  # user or admin abandoned the session


class EntryType(str, Enum):
    """LedgerEntry event type — spend ledger only.

    Top-ups (credits) live on Invoice, not here. Balance is reconciled by
    Σ(invoices where status=paid) − Σ(debits) + Σ(cancelled).

    debit: query reserved an amount in pre_hook
    cancelled: post_hook reversed a debit (empty response refund)
    """

    DEBIT = "debit"
    CANCELLED = "cancelled"


class Invoice(SQLModel, table=True):
    """Invoice entity tracking payment lifecycle.

    Created when a user initiates a bundle purchase. Status transitions:
    pending → paid (webhook confirms payment)
    pending → expired (provider timeout)
    pending → failed (payment declined)

    Credit lands on UserBalance keyed by wallet_id. endpoint_id is kept
    as nullable context (where the user clicked "buy") for analytics.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        Index("idx_invoice_external_id", "external_id", unique=True),
        Index("idx_invoice_tenant_user", "tenant_id", "user_email"),
        Index("idx_invoice_status", "status"),
        Index("idx_invoice_wallet", "wallet_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    wallet_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("wallets.id", ondelete="SET NULL"), nullable=True),
        description="Wallet receiving the credit on PAID (NULL if wallet deleted)",
    )
    endpoint_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("endpoints.id", ondelete="SET NULL"), nullable=True
        ),
        description="Originating endpoint context (NULL if endpoint deleted)",
    )
    user_email: str = Field(..., description="Email of the purchasing user")
    provider: str = Field(..., description="Payment provider (e.g., 'xendit')")
    external_id: str = Field(..., description="Provider invoice ID (webhook join key)")
    checkout_url: str = Field(..., description="Provider hosted checkout URL")
    bundle_name: str = Field(..., description="Bundle name at time of purchase")
    amount: float = Field(..., description="Bundle amount in currency")
    currency: str = Field(..., description="Currency code (e.g., 'USD')")
    status: str = Field(
        default=InvoiceStatus.PENDING.value, description="Invoice status"
    )
    webhook_payload: dict | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Raw provider webhook payload",
    )
    paid_at: datetime | None = Field(
        default=None, description="When payment was confirmed"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserBalance(SQLModel, table=True):
    """Materialized money balance per (tenant, wallet, user).

    Hot-path read used by pre_hook to answer "do I have enough?" under
    contention. `balance` is the only mutable field — total deposited and
    total spent are derivable from LedgerEntry.

    CASCADE on wallet_id: when a wallet is force-deleted, balance rows
    drop with it (history survives in ledger_entry via SET NULL).
    """

    __tablename__ = "user_balance"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "wallet_id",
            "user_email",
            name="uq_user_balance_user_wallet",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    wallet_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("wallets.id", ondelete="CASCADE")),
        description="Wallet this balance is denominated in",
    )
    user_email: str = Field(..., description="User email")
    balance: float = Field(default=0.0, description="Current remaining balance")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LedgerEntry(SQLModel, table=True):
    """Append-only spend ledger.

    Two event types:
    - debit: minted by BalanceService.reserve(); transaction_id is the correlation key
    - cancelled: post_hook reversal; shares transaction_id with its debit

    Top-ups are NOT recorded here — they live on Invoice (status=paid is the
    source of truth). This keeps each fact in exactly one place.

    `currency` is denormalized so audit rows survive wallet deletion via
    SET NULL (a deleted wallet's currency would otherwise be unrecoverable).

    Idempotency: UNIQUE(transaction_id, type) prevents double-debit and
    double-cancel for the same correlation id.
    """

    __tablename__ = "ledger_entry"
    __table_args__ = (
        Index(
            "idx_ledger_entry_user_time",
            "tenant_id",
            "wallet_id",
            "user_email",
            "created_at",
        ),
        Index("idx_ledger_entry_correlation", "transaction_id"),
        Index("idx_ledger_entry_endpoint", "endpoint_id", "created_at"),
        UniqueConstraint(
            "transaction_id", "type", name="uq_ledger_entry_correlation_type"
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    wallet_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("wallets.id", ondelete="SET NULL"), nullable=True),
        description="Wallet at time of entry (NULL if wallet later deleted)",
    )
    user_email: str = Field(
        ..., description="User email (soft ref to SyftHub identity)"
    )
    transaction_id: UUID = Field(
        ...,
        index=True,
        description="Correlation key shared between a debit and its cancelled pair.",
    )
    type: str = Field(..., description="Event type: debit | cancelled")
    endpoint_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("endpoints.id", ondelete="SET NULL"), nullable=True
        ),
        description="Endpoint that triggered the debit/cancelled (NULL after endpoint deletion)",
    )
    amount: float = Field(..., description="Amount of this movement (always positive)")
    currency: str = Field(
        ..., description="Currency at time of write (denormalized from wallet)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
