"""combined runs

``combined_members``: the leaf jobs a combined job (``kind = combined``) is
made of, many-to-many, deleted with either job. ``targets.combine_periods``:
the periods the ticker combines a target's runs over; ``targets.combine_marks``:
per period, the last period it dealt with.

Downgrade drops the table and the columns; combined jobs stay as rows without
members.

Revision ID: c5a8e3f1d7b2
Revises: b7e4d1c9a2f6
Create Date: 2026-11-04 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c5a8e3f1d7b2"
down_revision: str | Sequence[str] | None = "b7e4d1c9a2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KIND_COMMENT_BEFORE = (
    "What operation this job is: pipeline (measure(), any combination of "
    "generate/filter/evaluate), filter, or judge"
)
KIND_COMMENT = (
    "What operation this job is: pipeline (measure(), any combination of "
    "generate/filter/evaluate), filter, judge, or combined"
)


def upgrade() -> None:
    op.create_table(
        "combined_members",
        sa.Column("combined_job_id", sa.String(length=64), nullable=False),
        sa.Column("member_job_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["combined_job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("combined_job_id", "member_job_id"),
    )
    op.create_index(
        op.f("ix_combined_members_member_job_id"),
        "combined_members",
        ["member_job_id"],
        unique=False,
    )
    op.add_column(
        "targets",
        sa.Column(
            "combine_periods",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "targets",
        sa.Column(
            "combine_marks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column(
        "jobs",
        "kind",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        comment=KIND_COMMENT,
        existing_comment=KIND_COMMENT_BEFORE,
    )


def downgrade() -> None:
    op.alter_column(
        "jobs",
        "kind",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        comment=KIND_COMMENT_BEFORE,
        existing_comment=KIND_COMMENT,
    )
    op.drop_column("targets", "combine_marks")
    op.drop_column("targets", "combine_periods")
    op.drop_index(
        op.f("ix_combined_members_member_job_id"), table_name="combined_members"
    )
    op.drop_table("combined_members")
