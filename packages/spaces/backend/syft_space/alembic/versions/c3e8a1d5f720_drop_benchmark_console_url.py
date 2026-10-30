"""drop console_url from benchmark_connections

The Space does not link to the benchmark's standalone console.
Downgrade re-adds the column empty.

Revision ID: c3e8a1d5f720
Revises: b7d2e4f19a60
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8a1d5f720"
down_revision: str | None = "b7d2e4f19a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


@contextmanager
def _keeping_target_connections() -> Iterator[None]:
    """Keep benchmark_targets.connection_id across a rebuild of benchmark_connections.

    SQLite's batch mode rebuilds the table and drops the old one. The Space runs
    migrations with foreign keys on, so that drop fires ON DELETE SET NULL on
    every target. The links are read before and written back after.
    """
    bind = op.get_bind()
    links = bind.execute(
        sa.text(
            "SELECT id, connection_id FROM benchmark_targets "
            "WHERE connection_id IS NOT NULL"
        )
    ).all()
    yield
    if links:
        bind.execute(
            sa.text("UPDATE benchmark_targets SET connection_id = :c WHERE id = :t"),
            [{"t": t, "c": c} for t, c in links],
        )


def upgrade() -> None:
    with _keeping_target_connections():
        with op.batch_alter_table("benchmark_connections") as batch_op:
            batch_op.drop_column("console_url")


def downgrade() -> None:
    with op.batch_alter_table("benchmark_connections") as batch_op:
        batch_op.add_column(
            sa.Column("console_url", sa.String(), nullable=False, server_default=""),
        )
