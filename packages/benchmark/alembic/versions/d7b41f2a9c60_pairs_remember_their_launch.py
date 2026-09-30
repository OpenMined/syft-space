"""questions remember the launch that built them

A pair has always known which pool it belongs to (``cohort``) and when it was
written, and that was enough while the only question asked of it was "is it in
the measurement now". It is not enough for the question the run's own page
asks: **what did THIS launch generate** — including what it generated and then
threw away.

``cohort`` cannot answer that. A pool is built afresh only when the dataset
mode says so; an incremental launch adds to the pool that is already there, so
two launches a day apart share one cohort and their questions are
indistinguishable by it.

NULL is not a gap: every pair written before this column existed belongs to no
launch anyone can name, and a page that scopes to a launch simply has nothing
to show for it. That is the honest answer, and it is the same one
``runs.job_id`` gives for a run opened outside the queue.

Revision ID: d7b41f2a9c60
Revises: c8a4f19bde27
Create Date: 2026-09-30 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7b41f2a9c60"
down_revision: str | Sequence[str] | None = "c8a4f19bde27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "qa_pairs",
        sa.Column(
            "job_id",
            sa.String(length=64),
            nullable=True,
            comment="The launch that generated this pair; NULL — none it can name",
        ),
    )
    # Every read of it is "this launch's questions", and the status band is
    # always part of that question — rejected ones are shown beside the rest.
    op.create_index("qa_pairs_job", "qa_pairs", ["space", "job_id", "status"])


def downgrade() -> None:
    op.drop_index("qa_pairs_job", table_name="qa_pairs")
    op.drop_column("qa_pairs", "job_id")
