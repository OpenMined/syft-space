"""job kind for phase-scoped runs

``jobs.phase`` already says where a job is right now (generate, evaluate,
...), but nothing said what job it *is*. Every job used to be the same
operation — generate, then evaluate with judging folded in, then a card, then
an optional publish — so there was nothing to name.

Filtering and judging can now be launched on their own, over pairs or
verdicts that are already stored rather than over a fresh ``measure()`` call,
and a job has to declare which of those it is up front: ``execute()`` picks a
function by ``kind`` before there is any phase to look at yet. Everything
``/targets/{key}/runs`` creates — a full measurement, a lone generate, a lone
evaluate, or either console-facing group built from the same flags — stays
one kind, ``pipeline``: all of it is one call to ``measure()`` with a
different combination of booleans, not a different operation.

``jobs.kind`` defaults to, and every existing row becomes, ``pipeline`` — the
original, uninterrupted run every job used to be. Nothing about what those
rows mean changes.

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
