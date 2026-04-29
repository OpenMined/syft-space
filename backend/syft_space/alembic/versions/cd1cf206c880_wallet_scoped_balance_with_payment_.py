"""wallet-scoped balance with payment ledger

Revision ID: cd1cf206c880
Revises: d4e5f6a7b8c9
Create Date: 2026-04-28 14:32:49.700321

Reshapes the prepaid-balance model from per-(user, endpoint) to per-(tenant,
wallet, user) and adds an append-only ledger.

- Drops `bundle_usage` (endpoint-scoped balance).
- Adds `user_balance` (wallet-scoped, single `balance` column).
- Adds `ledger_entry` (append-only ledger; debit / cancelled).
- Adds `invoices.wallet_id` (FK → wallets, SET NULL on delete).
- Adds `wallets.currency` (required) and `wallets.country` (optional).
- Adds UNIQUE(tenant_id, wallet_type, currency) on wallets.

Note: the original autogen flagged spurious VARCHAR↔Uuid type changes on
columns that haven't actually changed in this PR. Those were introduced by
SQLAlchemy/SQLModel inferring different SA types over time; pruning them
keeps the migration to its actual intent.
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
    # ── New tables ─────────────────────────────────────────────────
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

    # ── Drop the old endpoint-scoped balance table ─────────────────
    op.drop_table("bundle_usage")

    # ── Invoices: wallet_id FK ─────────────────────────────────────
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(sa.Column("wallet_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_invoices_wallet",
            "wallets",
            ["wallet_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("idx_invoice_wallet", ["wallet_id"])

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

    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_index("idx_invoice_wallet")
        batch_op.drop_constraint("fk_invoices_wallet", type_="foreignkey")
        batch_op.drop_column("wallet_id")

    op.create_table(
        "bundle_usage",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("user_email", sa.VARCHAR(), nullable=False),
        sa.Column("remaining_balance", sa.FLOAT(), nullable=False),
        sa.Column("total_deposited", sa.FLOAT(), nullable=False),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.Column("updated_at", sa.DATETIME(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "endpoint_id",
            "user_email",
            name="uq_bundle_usage_user_endpoint",
        ),
    )

    op.drop_index("ix_ledger_entry_transaction_id", table_name="ledger_entry")
    op.drop_index("ix_ledger_entry_id", table_name="ledger_entry")
    op.drop_index("idx_ledger_entry_user_time", table_name="ledger_entry")
    op.drop_index("idx_ledger_entry_endpoint", table_name="ledger_entry")
    op.drop_index("idx_ledger_entry_correlation", table_name="ledger_entry")
    op.drop_table("ledger_entry")

    op.drop_index("ix_user_balance_id", table_name="user_balance")
    op.drop_table("user_balance")
