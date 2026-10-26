"""drop console_url from benchmark_connections

The Space no longer links to the benchmark's standalone console.
Downgrade re-adds the column empty.

Revision ID: c3e8a1d5f720
Revises: b7d2e4f19a60
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8a1d5f720"
down_revision: str | None = "b7d2e4f19a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("benchmark_connections") as batch_op:
        batch_op.drop_column("console_url")


def downgrade() -> None:
    with op.batch_alter_table("benchmark_connections") as batch_op:
        batch_op.add_column(
            sa.Column("console_url", sa.String(), nullable=False, server_default=""),
        )
