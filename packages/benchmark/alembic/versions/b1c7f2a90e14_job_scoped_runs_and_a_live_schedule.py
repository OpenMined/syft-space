"""job-scoped runs and a live schedule

``runs.job_id`` ties a run to the launch it belongs to, so the report and the
audit of one measurement can be scoped to it. Nullable: a run started from the
console belongs to no job. No foreign key, for the reason ``jobs`` has none on
``targets``: a cascade must not carry off the history of what was measured.

``targets.next_run_at`` is the moment the stored schedule fires next, stored so
that a 24h schedule fires once rather than on every tick of its hour, and a
newly saved schedule does not fire at once. ``schedule_at`` is documented as
UTC.

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
