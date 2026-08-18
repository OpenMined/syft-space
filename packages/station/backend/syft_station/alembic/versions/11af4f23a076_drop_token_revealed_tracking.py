"""drop token revealed tracking

Revision ID: 11af4f23a076
Revises: acc87bc50678
Create Date: 2026-07-23 16:06:22.790625

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "11af4f23a076"
down_revision: str | None = "acc87bc50678"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The one-time-reveal model is retired: the admin key is served as an
    # authToken URL instead, so "revealed" no longer means anything.
    op.drop_column("space_tokens", "revealed_at")


def downgrade() -> None:
    op.add_column(
        "space_tokens", sa.Column("revealed_at", sa.DATETIME(), nullable=True)
    )
