"""who actually served the call

Two columns on ``results``, because a provider is not always the model's owner.
A router puts many upstreams behind one name — the same weights at fp4 and at
bf16, context windows from 64k to a million, output ceilings from 32k to 236k —
and picks between them per request. All three differences change what a model
answers, so without these columns a run served in fp4 and one served in bf16
are two numbers under one model name.

**Per answer, not per run.** The choice is made per request, so one run can be
served by four upstreams; an aggregate would say it was mixed without saying
which answers came from where.

The judge's upstream is a column of its own: the number is a judge's verdict, so
"answerer or grader" is the first question when it moves.

**Recorded, not pinned** — a pinned host that is down takes a run with it. Old
rows keep an empty string: nothing is known about what served them.

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
