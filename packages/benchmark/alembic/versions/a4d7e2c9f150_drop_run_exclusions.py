"""drop run_exclusions

Questions are no longer left out of a run's figures by hand.

Revision ID: a4d7e2c9f150
Revises: 8e2c5a1f7b30
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a4d7e2c9f150"
down_revision: str | Sequence[str] | None = "8e2c5a1f7b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("run_exclusions")


def downgrade() -> None:
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
