"""one writer_calls row per (job_id, call)

A pair's writer call is looked up in its job's log by call id, and a call is
logged once.

Revision ID: 7c3e5a9d1b62
Revises: 2e7b9c4f1a83
Create Date: 2026-10-28 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "7c3e5a9d1b62"
down_revision: str | Sequence[str] | None = "2e7b9c4f1a83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "writer_calls_call", "writer_calls", ["job_id", "call"], unique=True
    )


def downgrade() -> None:
    op.drop_index("writer_calls_call", table_name="writer_calls")
