"""add settings table

Revision ID: e18675e6eecb
Revises: 9b73c6b77fa4
Create Date: 2026-01-13 12:39:41.971893

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401 - Added for SQLModel support
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e18675e6eecb"
down_revision: str | None = "9b73c6b77fa4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_url", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("settings")
