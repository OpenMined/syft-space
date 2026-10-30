"""what was actually served

``runs.model_sent_as``, ``runs.model_provider``, ``runs.model_build``: the name
the provider was given, whose API answered, and the dated build behind the
name. Columns rather than keys in ``runs.params``: that snapshot is compared
for exact equality when resuming, and a build changes on its own. Existing
rows get an empty string.

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
