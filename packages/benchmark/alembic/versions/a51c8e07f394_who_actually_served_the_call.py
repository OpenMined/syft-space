"""who actually served the call

``results.served_by`` and ``results.judge_served_by``: the upstream a router
picked for the answer and for the verdict. Per answer, because a router picks
per request, and upstreams of one name differ in quantisation and limits.
Recorded, not pinned — a pinned host that is down takes a run with it. Existing
rows get an empty string.

Revision ID: a51c8e07f394
Revises: e4f0b93c7d15
Create Date: 2026-09-20 16:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a51c8e07f394"
down_revision: str | Sequence[str] | None = "e4f0b93c7d15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "results",
        sa.Column(
            "served_by",
            sa.String(length=64),
            nullable=False,
            server_default="",
            comment="The upstream that served the answer, when the provider is "
            "a router rather than the model's owner",
        ),
    )
    op.add_column(
        "results",
        sa.Column(
            "judge_served_by",
            sa.String(length=64),
            nullable=False,
            server_default="",
            comment="The upstream that served the verdict. Kept apart from the "
            "answer's: when a number moves, it is the first thing to rule out",
        ),
    )


def downgrade() -> None:
    op.drop_column("results", "judge_served_by")
    op.drop_column("results", "served_by")
