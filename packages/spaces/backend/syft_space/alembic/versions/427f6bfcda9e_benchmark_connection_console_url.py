"""add console_url to benchmark_connections

``console_url`` is the benchmark address for the browser, when it differs
from ``url`` (e.g. a Docker-internal hostname). Empty falls back to ``url``.

Revision ID: 427f6bfcda9e
Revises: f612f5b93dbc
Create Date: 2026-09-27 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "427f6bfcda9e"
down_revision: str | None = "f612f5b93dbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("benchmark_connections") as batch_op:
        batch_op.add_column(
            sa.Column("console_url", sa.String(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    with op.batch_alter_table("benchmark_connections") as batch_op:
        batch_op.drop_column("console_url")
