"""questions remember the launch that built them

``qa_pairs.job_id``: which launch built the pair, including pairs it built and
then rejected. ``cohort`` cannot say: an incremental launch adds to the pool
already there. NULL — a pair no launch can be named for, as ``runs.job_id``
for a run opened outside the queue.

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
