"""what was actually served

Three columns on ``runs``: what was on the other end of the wire.

``runs.model`` holds the identifier this service uses, which is the right thing
to store and not enough to reproduce a run. The provider is told its own name
for the model, and behind that name stands a dated build the vendor replaces
without renaming anything; six months on, two rows under one model name can be
two different sets of weights.

**Columns rather than keys in ``runs.params``.** That snapshot is compared for
exact equality to decide whether yesterday's answers count as done, and a build
moves on its own — inside it, every vendor refresh would make the whole table
stop matching and the next pass would pay to ask again what it knows. This is
evidence about a run, not a condition for comparing two.

Old rows keep an empty string: nothing is known about what served them.

Revision ID: e4f0b93c7d15
Revises: d2a7c1e4b830
Create Date: 2026-09-20 15:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4f0b93c7d15"
down_revision: str | Sequence[str] | None = "d2a7c1e4b830"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column(
            "model_sent_as",
            sa.String(length=120),
            nullable=False,
            server_default="",
            comment="The name the provider was actually given, when it differs "
            "from the identifier this service uses",
        ),
    )
    op.add_column(
        "runs",
        sa.Column(
            "model_provider",
            sa.String(length=40),
            nullable=False,
            server_default="",
            comment="Whose API answered: openrouter, anthropic, ollama",
        ),
    )
    op.add_column(
        "runs",
        sa.Column(
            "model_build",
            sa.String(length=120),
            nullable=False,
            server_default="",
            comment="The dated build behind the name on the day of the run. A "
            "vendor refreshes what a name serves; without this, two runs under "
            "one name look comparable when they are not",
        ),
    )


def downgrade() -> None:
    op.drop_column("runs", "model_build")
    op.drop_column("runs", "model_provider")
    op.drop_column("runs", "model_sent_as")
