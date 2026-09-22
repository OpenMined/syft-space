"""store the assembled card on the job

A card was built only as a side effect of publishing it: ``request.publish``
false, or the Space refusing it, meant ``build_card`` was never even called,
and a measurement that ran to completion had nothing to show for itself beyond
a pass count and an error string. The owner could not tell "measured fine, not
sent anywhere" from "measured nothing" without going to the console.

``jobs.card`` holds the card assembled right after measuring, independent of
whether it was ever published — the one place "how did this run go" is
answered from now on. Nullable: a job that never reached a gradable answer, or
one still running, has none yet.

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
