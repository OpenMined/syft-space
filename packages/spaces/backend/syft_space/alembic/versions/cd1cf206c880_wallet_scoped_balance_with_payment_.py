"""wallet-scoped balance with payment ledger

Revision ID: cd1cf206c880
Revises: d4e5f6a7b8c9
Create Date: 2026-04-28 14:32:49.700321

Introduces the wallet-scoped prepaid model in one shot:

- Creates `invoices` (carries wallet_id from day one).
- Creates `user_balance` (per (tenant, wallet, user) materialized aggregate).
- Creates `ledger_entry` (append-only debit / cancelled ledger).
- Adds `endpoints.archived` flag (was previously in a separate migration that
  this one supersedes).
- Adds `wallets.currency` (required) and `wallets.country` (optional), plus
  UNIQUE(tenant_id, wallet_type, currency).

Replaces an earlier draft pair (invoices + bundle_usage, then a follow-up to
reshape) — collapsed into this single migration since neither was released.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd1cf206c880"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Invoices ───────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        sa.Column("user_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("checkout_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("bundle_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("webhook_payload", sa.JSON(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name="fk_invoices_wallet",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invoices_id", "invoices", ["id"], unique=False)
    op.create_index("idx_invoice_external_id", "invoices", ["external_id"], unique=True)
    op.create_index("idx_invoice_tenant_user", "invoices", ["tenant_id", "user_email"])
    op.create_index("idx_invoice_status", "invoices", ["status"])
    op.create_index("idx_invoice_wallet", "invoices", ["wallet_id"])

    # ── User balance (materialized aggregate) ──────────────────────
    op.create_table(
        "user_balance",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("user_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("balance", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "wallet_id",
            "user_email",
            name="uq_user_balance_user_wallet",
        ),
    )
    op.create_index("ix_user_balance_id", "user_balance", ["id"], unique=False)

    # ── Ledger entries (append-only debits / cancelled) ────────────
    op.create_table(
        "ledger_entry",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=True),
        sa.Column("user_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "transaction_id", "type", name="uq_ledger_entry_correlation_type"
        ),
    )
    op.create_index("idx_ledger_entry_correlation", "ledger_entry", ["transaction_id"])
    op.create_index(
        "idx_ledger_entry_endpoint",
        "ledger_entry",
        ["endpoint_id", "created_at"],
    )
    op.create_index(
        "idx_ledger_entry_user_time",
        "ledger_entry",
        ["tenant_id", "wallet_id", "user_email", "created_at"],
    )
    op.create_index("ix_ledger_entry_id", "ledger_entry", ["id"])
    op.create_index(
        "ix_ledger_entry_transaction_id",
        "ledger_entry",
        ["transaction_id"],
    )

    # ── Endpoints: archived flag (formerly part of beb8d008c9c8) ──
    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.add_column(
            sa.Column("archived", sa.Boolean(), nullable=False, server_default="0")
        )

    # ── Wallets: currency / country / uniqueness ───────────────────
    with op.batch_alter_table("wallets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "currency",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="USD",
            )
        )
        batch_op.add_column(
            sa.Column("country", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_wallet_tenant_type_currency",
            ["tenant_id", "wallet_type", "currency"],
        )

    # Drop the server_default once existing rows are populated; new rows
    # always specify currency at the application layer.
    with op.batch_alter_table("wallets") as batch_op:
        batch_op.alter_column("currency", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("wallets") as batch_op:
        batch_op.drop_constraint("uq_wallet_tenant_type_currency", type_="unique")
        batch_op.drop_column("country")
        batch_op.drop_column("currency")

    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.drop_column("archived")

    op.drop_index("ix_ledger_entry_transaction_id", table_name="ledger_entry")
    op.drop_index("ix_ledger_entry_id", table_name="ledger_entry")
    op.drop_index("idx_ledger_entry_user_time", table_name="ledger_entry")
    op.drop_index("idx_ledger_entry_endpoint", table_name="ledger_entry")
    op.drop_index("idx_ledger_entry_correlation", table_name="ledger_entry")
    op.drop_table("ledger_entry")

    op.drop_index("ix_user_balance_id", table_name="user_balance")
    op.drop_table("user_balance")

    op.drop_index("idx_invoice_wallet", table_name="invoices")
    op.drop_index("idx_invoice_status", table_name="invoices")
    op.drop_index("idx_invoice_tenant_user", table_name="invoices")
    op.drop_index("idx_invoice_external_id", table_name="invoices")
    op.drop_index("ix_invoices_id", table_name="invoices")
    op.drop_table("invoices")
