"""add instrument to benchmark_targets

``probe`` already lets one endpoint override the connection's dataset and
retrieval settings; ``instrument`` does the same for arms, blocks, judges,
subject models and thresholds. Unset fields fall back to the connection's own
instrument, and those to the benchmark's built-in defaults — the same
three-layer merge `probe` already goes through on the benchmark side
(`compose.py:settings_for`, which already reads `Target.instrument` and gives
it more authority than the connection's).

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
