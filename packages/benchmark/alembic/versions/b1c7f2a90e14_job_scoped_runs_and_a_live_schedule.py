"""job-scoped runs and a live schedule

Two changes, and they are one change: the service starts measuring by itself,
and what it measured becomes findable afterwards.

``runs.job_id`` ties a run to the launch it was born of. Until now a job and
its runs shared a target and a span of time and nothing else, so "the report of
this measurement" and "the audit of this measurement" could only be
approximated by timestamps -- which cannot tell a nightly run from one somebody
started by hand in the same hour. Nullable, because a run started from the
console belongs to no job and never will: backfilling those would mean
inventing launches that never happened. No foreign key, for the reason ``jobs``
has none on ``targets`` -- the history of what was measured must not be carried
off by a cascade from a row somebody tidied up.

``targets.next_run_at`` is what makes the stored schedule fire. It holds the
moment rather than recomputing it, so that a 24h schedule fires once in the
hour it is due in rather than on every tick of that hour, and so that saving a
schedule for the first time does not answer the owner with hours of paid work.

The comment on ``schedule_at`` changes with it: the hour is UTC now, and says
so. A container does not know the owner's night, and a service that guessed at
it from its own clock would shift every schedule the day the host moved.

Revision ID: b1c7f2a90e14
Revises: fbf33c5dff4d
Create Date: 2026-09-17 09:12:44.113028

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c7f2a90e14"
down_revision: str | Sequence[str] | None = "fbf33c5dff4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("job_id", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_runs_job_id"), "runs", ["job_id"], unique=False)

    op.add_column(
        "targets",
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "targets",
        "schedule_at",
        existing_type=sa.String(length=5),
        existing_nullable=False,
        existing_server_default=sa.text("''::character varying"),
        comment="The launch time HH:MM in UTC, if set",
        existing_comment="The launch time HH:MM, if set",
    )


def downgrade() -> None:
    op.alter_column(
        "targets",
        "schedule_at",
        existing_type=sa.String(length=5),
        existing_nullable=False,
        existing_server_default=sa.text("''::character varying"),
        comment="The launch time HH:MM, if set",
        existing_comment="The launch time HH:MM in UTC, if set",
    )
    op.drop_column("targets", "next_run_at")

    op.drop_index(op.f("ix_runs_job_id"), table_name="runs")
    op.drop_column("runs", "job_id")
