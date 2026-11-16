"""add filterable_fields to endpoints

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f7
Create Date: 2026-11-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the per-endpoint filter allowlist.

    Nullable: NULL reads as "every field the dataset can filter".
    """
    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.add_column(sa.Column("filterable_fields", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop the filter allowlist from ``endpoints``."""
    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.drop_column("filterable_fields")
