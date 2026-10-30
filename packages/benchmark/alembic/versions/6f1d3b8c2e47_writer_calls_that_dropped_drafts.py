"""writer calls that dropped drafts

``writer_calls``: a job's writer calls that threw drafts away or failed, per
kind, with the drafts and why. Deleted with their job by ``discard_run``.

Revision ID: 6f1d3b8c2e47
Revises: a4d7e2c9f150
Create Date: 2026-10-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "6f1d3b8c2e47"
down_revision: str | Sequence[str] | None = "a4d7e2c9f150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "writer_calls",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("call", sa.String(length=64), nullable=False),
        sa.Column("generator", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("document_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("passage", sa.Text(), nullable=False, server_default=""),
        sa.Column("system", sa.Text(), nullable=False, server_default=""),
        sa.Column("system_digest", sa.String(length=64), nullable=False),
        sa.Column("user", sa.Text(), nullable=False, server_default=""),
        sa.Column("reply", sa.Text(), nullable=False, server_default=""),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_s", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "dropped",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "writer_calls_job", "writer_calls", ["job_id", "generator", "created_at"]
    )
    op.create_index("writer_calls_system", "writer_calls", ["job_id", "system_digest"])


def downgrade() -> None:
    op.drop_index("writer_calls_system", table_name="writer_calls")
    op.drop_index("writer_calls_job", table_name="writer_calls")
    op.drop_table("writer_calls")
