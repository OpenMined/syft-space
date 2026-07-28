"""Credits database entities.

Money model — three tables, each holding one kind of fact:
- Invoice: top-ups. A credit exists iff an invoice reached PAID.
- UserBalance: materialized per-user balance — the hot path for debits.
- LedgerEntry: append-only spend ledger (debits + their reversals).

Balance is always reconcilable as
Σ(invoices where status=paid) − Σ(debits) + Σ(cancelled).

`user_email` is a soft reference to a SyftHub-managed identity; `space_id`
on ledger entries is a soft reference to the spaces registry — both survive
deletion of what they point at (audit rows are kept forever).
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel


class WalletProvider(StrEnum):
    """Payment gateway backing the station wallet."""

    XENDIT = "xendit"
    STRIPE = "stripe"


class InvoiceStatus(StrEnum):
    """Invoice lifecycle status.

    PROCESSING is an in-between state for providers (e.g. Stripe) that
    support delayed payment methods: checkout completed but settlement is
    still in flight. Balance is credited only on PAID. Xendit never uses it.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class EntryType(StrEnum):
    """LedgerEntry event type — spend ledger only.

    debit: a space charged a paid query
    cancelled: the debit was reversed (failed query refund or admin reversal)
    """

    DEBIT = "debit"
    CANCELLED = "cancelled"


class Wallet(SQLModel, table=True):
    """The station's shared payment wallet (gateway credentials).

    A plain table, but v1 policy is ONE wallet per station — enforced in the
    handler, not the schema, so multi-wallet later is a code change only.
    Currency is locked at setup (station currency = wallet currency);
    replacing the wallet must keep the currency in v1.
    """

    __tablename__ = "wallets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider: str = Field(description="Gateway: xendit | stripe")
    currency: str = Field(description="Wallet currency; the station currency")
    credentials: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Provider credentials (API keys, webhook secret)",
    )
    hub_user_id: int | None = Field(
        default=None,
        description="SyftHub user id of the wallet owner — published to the hub "
        "as wallet_owner so it can mint buyer tokens with the right audience",
    )
    hub_pat: str | None = Field(
        default=None,
        description="SyftHub API token (PAT) used to verify buyers' satellite "
        "tokens server-side; minted one-shot from the admin's password",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Invoice(SQLModel, table=True):
    """A credits top-up purchase tracking the provider checkout lifecycle.

    Created PENDING *before* the provider call so a provider session can
    never outlive the local row. `client_reference` (syft-{id}) is our
    outbound token echoed back by provider webhooks — the webhook→invoice
    join key.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        Index("idx_invoice_client_reference", "client_reference", unique=True),
        Index("idx_invoice_user", "user_email"),
        Index("idx_invoice_status", "status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_email: str = Field(description="Purchasing user")
    provider: str = Field(description="Gateway: xendit | stripe")
    client_reference: str = Field(
        description="Outbound token (syft-{id}) echoed back in webhooks"
    )
    checkout_url: str = Field(
        default="", description="Provider hosted checkout URL (set after creation)"
    )
    provider_session_id: str | None = Field(
        default=None,
        description="Provider-side session id (e.g. Stripe cs_…) for reconciliation",
    )
    bundle_name: str = Field(description="Bundle purchased")
    amount: float = Field(description="Top-up amount in the station currency")
    currency: str = Field(description="Currency code at time of purchase")
    status: str = Field(default=InvoiceStatus.PENDING.value)
    webhook_payload: dict | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Raw provider webhook payload that settled this invoice",
    )
    paid_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserBalance(SQLModel, table=True):
    """Materialized credit balance per user email — the debit hot path.

    Keyed by email alone: one station currency (the wallet's), so there is
    never more than one balance per user. `balance` is the only mutable
    field; everything else is derivable from invoices + ledger entries.
    """

    __tablename__ = "user_balances"
    __table_args__ = (UniqueConstraint("user_email", name="uq_user_balance_email"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_email: str = Field(index=True)
    balance: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LedgerEntry(SQLModel, table=True):
    """Append-only spend ledger — one row per money movement.

    Each debit carries full attribution (space × endpoint × user × time) so
    admin analytics are plain GROUP BYs; CANCELLED rows copy the attribution
    from their debit, keeping aggregates join-free (DEBIT − CANCELLED).

    Idempotency: UNIQUE(transaction_id, type). The space generates
    transaction_id, so a replayed debit or a double refund is a constraint
    violation, never a second movement.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id", "type", name="uq_ledger_entry_transaction_type"
        ),
        Index("idx_ledger_entry_space_time", "space_id", "created_at"),
        Index("idx_ledger_entry_user_time", "user_email", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_email: str = Field(description="End user whose balance moved")
    transaction_id: UUID = Field(
        index=True,
        description="Space-generated correlation key; shared by a debit "
        "and its cancelled pair",
    )
    type: str = Field(description="debit | cancelled")
    space_id: UUID = Field(
        description="Space attributed with this movement (soft ref; from the "
        "bearer token on debits, copied onto cancels)"
    )
    endpoint: str = Field(
        default="",
        description="Endpoint slug relayed by the space (audit/analytics context)",
    )
    amount: float = Field(description="Movement amount (always positive)")
    currency: str = Field(description="Currency at time of write")
    charge_unit: str = Field(description="e.g. per_query / per_document")
    charge_quantity: int = Field(description="Units billed in this entry")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Payout(SQLModel, table=True):
    """A recorded payout to a space owner.

    Money moves out-of-band (bank transfer, whatever the admin uses); this
    row is the ledger's acknowledgment. Payable per space is always derived:
    earned (DEBIT − CANCELLED attributed to the space) − Σ(payouts).
    """

    __tablename__ = "payouts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    space_id: UUID = Field(index=True, description="Space paid out (soft ref)")
    amount: float = Field(description="Amount paid, in the station currency")
    note: str = Field(default="", description="Free-text memo (e.g. transfer ref)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpaceCreditToken(SQLModel, table=True):
    """A space's credits service token — and its binding to a wallet.

    The row IS the space↔wallet attachment: minting one attaches the space
    to the wallet (the provisioning wallet picker writes or skips it).
    Only the sha256 hash is stored; the plaintext goes straight into the
    space's k8s Secret. Distinct from the space admin API key (SpaceToken)
    so either can rotate without breaking the other.
    """

    __tablename__ = "space_credit_tokens"
    __table_args__ = (Index("idx_space_credit_token_hash", "token_hash", unique=True),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    space_id: UUID = Field(index=True)
    wallet_id: UUID = Field(description="Wallet this space is attached to")
    token_hash: str = Field(description="sha256 hex of the token; no plaintext")
    revoked_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
