"""add instrument to benchmark_targets

Per-endpoint override of the connection's instrument settings (arms, blocks,
judges, subject models, thresholds), like ``probe``.

Revision ID: f8bb6df81871
Revises: 427f6bfcda9e
Create Date: 2026-09-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8bb6df81871"
down_revision: str | None = "427f6bfcda9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("benchmark_targets") as batch_op:
        batch_op.add_column(
            sa.Column("instrument", sa.JSON(none_as_null=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("benchmark_targets") as batch_op:
        batch_op.drop_column("instrument")
