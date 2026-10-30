"""drop benchmark_connections.fields and benchmark_targets.synced_at

Nothing reads the cached settings schema or the last push time. Downgrade
re-adds both columns empty.

Revision ID: e4a9c6b2d813
Revises: d7f2b9c4e351
Create Date: 2026-10-30 12:00:00.000000

"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4a9c6b2d813"
down_revision: str | None = "d7f2b9c4e351"
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
            batch_op.drop_column("fields")
    with op.batch_alter_table("benchmark_targets") as batch_op:
        batch_op.drop_column("synced_at")


def downgrade() -> None:
    with op.batch_alter_table("benchmark_targets") as batch_op:
        batch_op.add_column(sa.Column("synced_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("benchmark_connections") as batch_op:
        batch_op.add_column(
            sa.Column("fields", sa.JSON(none_as_null=True), nullable=True)
        )
