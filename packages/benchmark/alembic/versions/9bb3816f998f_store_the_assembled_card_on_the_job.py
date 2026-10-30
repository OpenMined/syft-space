"""store the assembled card on the job

``jobs.card`` holds the card assembled right after measuring, whether or not it
was published: the one place "how did this run go" is answered from. Nullable:
a job that never reached a gradable answer, or one still running, has none.

Revision ID: 9bb3816f998f
Revises: c4d81ab6f207
Create Date: 2026-09-18 05:51:48.046075

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9bb3816f998f"
down_revision: str | Sequence[str] | None = "c4d81ab6f207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "card",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="The card assembled after measuring, in the shape the Space "
            "accepts it in — set regardless of whether it was published",
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "card")
