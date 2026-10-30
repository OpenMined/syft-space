"""job kind for phase-scoped runs

``jobs.kind`` says what operation a job is, as opposed to ``phase``, where it
is: ``pipeline`` (one ``measure()`` call, whatever its flags), or ``filter`` /
``judge`` over already-stored pairs or verdicts. ``execute()`` picks a function
by it. Existing rows become ``pipeline``.

Revision ID: c8a4f19bde27
Revises: a51c8e07f394
Create Date: 2026-09-24 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8a4f19bde27"
down_revision: str | Sequence[str] | None = "a51c8e07f394"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "kind",
            sa.String(length=20),
            nullable=False,
            server_default="pipeline",
            comment="What operation this job is: pipeline (measure(), any "
            "combination of generate/filter/evaluate), filter, or judge",
        ),
    )
    op.create_index(op.f("ix_jobs_kind"), "jobs", ["kind"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_kind"), table_name="jobs")
    op.drop_column("jobs", "kind")
