"""Replace accounting fields with wallet fields on marketplaces table.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new MPP wallet fields
    op.add_column(
        "marketplaces",
        sa.Column("wallet_address", sa.String(), nullable=True),
    )
    op.add_column(
        "marketplaces",
        sa.Column("wallet_private_key", sa.String(), nullable=True),
    )

    # Drop old accounting fields
    # Note: SQLite < 3.35.0 doesn't support DROP COLUMN.
    # Use batch mode for broad compatibility.
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.drop_column("accounting_url")
        batch_op.drop_column("accounting_email")
        batch_op.drop_column("accounting_password")


def downgrade() -> None:
    # Re-add accounting fields
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.add_column(
            sa.Column("accounting_url", sa.String(), nullable=False, server_default=""),
        )
        batch_op.add_column(
            sa.Column("accounting_email", sa.String(), nullable=False, server_default=""),
        )
        batch_op.add_column(
            sa.Column("accounting_password", sa.String(), nullable=False, server_default=""),
        )

    # Drop wallet fields
    op.drop_column("marketplaces", "wallet_private_key")
    op.drop_column("marketplaces", "wallet_address")
