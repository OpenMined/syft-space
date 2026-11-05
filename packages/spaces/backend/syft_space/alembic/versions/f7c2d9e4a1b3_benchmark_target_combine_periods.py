"""benchmark target combine periods

``benchmark_targets.combine_periods``: the periods the benchmark combines an
endpoint's runs over. Added in place; the downgrade rebuilds the table, which
nothing references.

Revision ID: f7c2d9e4a1b3
Revises: e4a9c6b2d813
Create Date: 2026-11-04 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7c2d9e4a1b3"
down_revision: str | None = "e4a9c6b2d813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "benchmark_targets",
        sa.Column("combine_periods", sa.JSON(none_as_null=True), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("benchmark_targets") as batch_op:
        batch_op.drop_column("combine_periods")
