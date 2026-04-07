"""Add invoices, bundle_usage tables and archived column on endpoints.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create invoices table
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("checkout_url", sa.String(), nullable=False),
        sa.Column("tier_name", sa.String(), nullable=False),
        sa.Column("tier_units", sa.Integer(), nullable=False),
        sa.Column("unit_type", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("webhook_payload", sa.JSON(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_invoice_external_id", "invoices", ["external_id"], unique=True)
    op.create_index("idx_invoice_tenant_user", "invoices", ["tenant_id", "user_email"])
    op.create_index("idx_invoice_status", "invoices", ["status"])

    # 2. Create bundle_usage table
    op.create_table(
        "bundle_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("unit_type", sa.String(), nullable=False),
        sa.Column("remaining_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_purchased", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "endpoint_id",
            "user_email",
            "unit_type",
            name="uq_bundle_usage_user_endpoint_type",
        ),
    )

    # 3. Add archived column to endpoints (SQLite-safe via batch)
    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.add_column(
            sa.Column("archived", sa.Boolean(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    # Remove archived column
    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.drop_column("archived")

    # Drop tables
    op.drop_table("bundle_usage")
    op.drop_index("idx_invoice_status", table_name="invoices")
    op.drop_index("idx_invoice_tenant_user", table_name="invoices")
    op.drop_index("idx_invoice_external_id", table_name="invoices")
    op.drop_table("invoices")
