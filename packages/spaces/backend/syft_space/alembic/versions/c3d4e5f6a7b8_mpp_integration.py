"""MPP integration: replace accounting with wallet fields, add mpp_secret_key.

- Add wallet_address and wallet_private_key to marketplaces
- Drop accounting_url, accounting_email, accounting_password from marketplaces
- Add mpp_secret_key to settings (auto-generated on first use)

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
    # Add MPP wallet fields to marketplaces
    op.add_column(
        "marketplaces",
        sa.Column("wallet_address", sa.String(), nullable=True),
    )
    op.add_column(
        "marketplaces",
        sa.Column("wallet_private_key", sa.String(), nullable=True),
    )

    # Drop old accounting fields from marketplaces
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.drop_column("accounting_url")
        batch_op.drop_column("accounting_email")
        batch_op.drop_column("accounting_password")

    # Add MPP secret key to settings
    op.add_column(
        "settings",
        sa.Column("mpp_secret_key", sa.String(), nullable=True),
    )


def downgrade() -> None:
    # Remove mpp_secret_key from settings
    op.drop_column("settings", "mpp_secret_key")

    # Re-add accounting fields to marketplaces
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.add_column(
            sa.Column("accounting_url", sa.String(), nullable=False, server_default=""),
        )
        batch_op.add_column(
            sa.Column(
                "accounting_email", sa.String(), nullable=False, server_default=""
            ),
        )
        batch_op.add_column(
            sa.Column(
                "accounting_password",
                sa.String(),
                nullable=False,
                server_default="",
            ),
        )

    # Drop wallet fields from marketplaces
    op.drop_column("marketplaces", "wallet_private_key")
    op.drop_column("marketplaces", "wallet_address")
