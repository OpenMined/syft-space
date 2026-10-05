"""run exclusions and cached run aggregates

``run_exclusions``: questions the owner left out of one run's figures.
``run_aggregates``: the cached per-run figures; a missing row means
"recompute". Both go with their job when it is deleted.

Revision ID: 0b6e8d4f2a19
Revises: f3a9c2d81b47
Create Date: 2026-10-03 10:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0b6e8d4f2a19"
down_revision: str | Sequence[str] | None = "f3a9c2d81b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_exclusions",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("qa_id", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["qa_id"], ["qa_pairs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "qa_id"),
    )
    op.create_table(
        "run_aggregates",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("run_aggregates")
    op.drop_table("run_exclusions")
