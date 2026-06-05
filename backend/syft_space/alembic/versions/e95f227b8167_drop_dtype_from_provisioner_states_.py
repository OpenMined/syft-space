"""drop dtype from provisioner_states; vector_store_type NOT NULL

Revision ID: e95f227b8167
Revises: 764c34a2dd18
Create Date: 2026-06-05 12:03:05.517959

Completes the re-key started in 764c34a2dd18: the legacy ``dtype``
column + its uniqueness guards are dropped, and ``vector_store_type``
is promoted to NOT NULL now that the dual-write phase is over.

All three changes (column drop + NOT NULL promotion + dropping the
inline ``uq_provisioner_dtype`` UNIQUE constraint) ride on a single
batch_alter_table — SQLite can't ALTER any of them in place, and
batch mode recreates the table cleanly without referencing the
soon-deleted ``dtype`` column. The companion non-unique
``idx_provisioner_dtype`` is dropped first via plain DROP INDEX.

DB engine: SQLite.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e95f227b8167"
down_revision: str | None = "764c34a2dd18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the companion non-unique index before dropping the column;
    # batch_alter_table below recreates the table without ``dtype``,
    # which also clears the inline ``uq_provisioner_dtype`` UNIQUE.
    op.drop_index("idx_provisioner_dtype", table_name="provisioner_states")

    with op.batch_alter_table("provisioner_states") as batch_op:
        batch_op.drop_column("dtype")
        batch_op.alter_column(
            "vector_store_type",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )


def downgrade() -> None:
    # Re-add the column nullable so the backfill can populate before
    # batch mode recreates the table with the legacy constraints.
    with op.batch_alter_table("provisioner_states") as batch_op:
        batch_op.add_column(
            sa.Column(
                "dtype",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            )
        )

    # Best-effort backfill so the legacy column reaches a usable shape.
    # Mirrors the original mapping from 764c34a2dd18.
    op.execute(
        """
        UPDATE provisioner_states
        SET dtype = 'local_file'
        WHERE vector_store_type = 'chromadb_local'
        """
    )

    # Re-impose the legacy NOT NULL + inline UNIQUE on dtype and relax
    # vector_store_type to nullable to match the pre-upgrade shape.
    with op.batch_alter_table(
        "provisioner_states",
        table_args=[sa.UniqueConstraint("dtype", name="uq_provisioner_dtype")],
    ) as batch_op:
        batch_op.alter_column(
            "dtype",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column(
            "vector_store_type",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        )

    op.create_index(
        "idx_provisioner_dtype",
        "provisioner_states",
        ["dtype"],
        unique=False,
    )
