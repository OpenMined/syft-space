"""credits schema

Revision ID: a296941268de
Revises: 90a7ee9e38d9
Create Date: 2026-07-23 13:00:59.038581

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # Added for SQLModel support
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a296941268de"
down_revision: str | None = "90a7ee9e38d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "client_reference", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("checkout_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "provider_session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("bundle_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("webhook_payload", sa.JSON(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_invoice_client_reference", "invoices", ["client_reference"], unique=True
    )
    op.create_index("idx_invoice_status", "invoices", ["status"], unique=False)
    op.create_index("idx_invoice_user", "invoices", ["user_email"], unique=False)
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("charge_unit", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("charge_quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transaction_id", "type", name="uq_ledger_entry_transaction_type"
        ),
    )
    op.create_index(
        "idx_ledger_entry_space_time",
        "ledger_entries",
        ["space_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_ledger_entry_user_time",
        "ledger_entries",
        ["user_email", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ledger_entries_transaction_id"),
        "ledger_entries",
        ["transaction_id"],
        unique=False,
    )
    op.create_table(
        "space_credit_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_space_credit_token_hash",
        "space_credit_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_space_credit_tokens_space_id"),
        "space_credit_tokens",
        ["space_id"],
        unique=False,
    )
    op.create_table(
        "user_balances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("balance", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_email", name="uq_user_balance_email"),
    )
    op.create_index(
        op.f("ix_user_balances_user_email"),
        "user_balances",
        ["user_email"],
        unique=False,
    )
    op.create_table(
        "wallets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("credentials", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("wallets")
    op.drop_index(op.f("ix_user_balances_user_email"), table_name="user_balances")
    op.drop_table("user_balances")
    op.drop_index(
        op.f("ix_space_credit_tokens_space_id"), table_name="space_credit_tokens"
    )
    op.drop_index("idx_space_credit_token_hash", table_name="space_credit_tokens")
    op.drop_table("space_credit_tokens")
    op.drop_index(op.f("ix_ledger_entries_transaction_id"), table_name="ledger_entries")
    op.drop_index("idx_ledger_entry_user_time", table_name="ledger_entries")
    op.drop_index("idx_ledger_entry_space_time", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("idx_invoice_user", table_name="invoices")
    op.drop_index("idx_invoice_status", table_name="invoices")
    op.drop_index("idx_invoice_client_reference", table_name="invoices")
    op.drop_table("invoices")
