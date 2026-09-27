"""add console_url to benchmark_connections

``url`` is the address THIS backend calls the benchmark's control API by —
on a rig where the two run as separate containers, that is a Docker-internal
hostname, resolvable container-to-container but not from a browser on the
host. The console link handed to the owner's browser was built from `url`
directly and broke wherever the two addresses differ.

``console_url`` is the address a browser should use instead, set only where
it differs from `url`; empty falls back to `url`, so a deployment where the
backend and a browser reach the benchmark the same way needs nothing here.

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
