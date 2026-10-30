"""drop instrument and probe from benchmark_connections

Measurement settings live on the target only; the connection says where the
benchmark is and how it reaches this Space. Downgrade re-adds both columns
empty.

Revision ID: d7f2b9c4e351
Revises: c3e8a1d5f720
Create Date: 2026-10-29 12:00:00.000000

"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f2b9c4e351"
down_revision: str | None = "c3e8a1d5f720"
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
            batch_op.drop_column("instrument")
            batch_op.drop_column("probe")


def downgrade() -> None:
    with op.batch_alter_table("benchmark_connections") as batch_op:
        batch_op.add_column(
            sa.Column("instrument", sa.JSON(none_as_null=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("probe", sa.JSON(none_as_null=True), nullable=True)
        )
