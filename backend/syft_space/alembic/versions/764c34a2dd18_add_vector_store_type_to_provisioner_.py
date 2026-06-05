"""add vector_store_type to provisioner_states

Revision ID: 764c34a2dd18
Revises: d9b3cb044bc7
Create Date: 2026-06-04 19:17:59.876924

Re-key ``provisioner_states`` from binding name (``dtype``) to vector
store name (``vector_store_type``) so the row's unit of sharing matches
what's actually provisioned: one running chroma subprocess can be
referenced by any number of bindings that compose ``chromadb_local``.

This migration is additive — both columns + both guards co-exist
during the dual-write transition. A follow-up migration drops the
legacy ``dtype`` column once the code stops writing it.

Backfill mapping is hard-coded against the one binding live today
(``local_file`` → ``chromadb_local``); future bindings will populate
``vector_store_type`` directly via the new write path.

DB engine: SQLite.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "764c34a2dd18"
down_revision: str | None = "d9b3cb044bc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provisioner_states",
        sa.Column(
            "vector_store_type",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
    )

    # Backfill: every existing row uses the local_file binding, which
    # binds the chromadb_local vector store.
    op.execute(
        """
        UPDATE provisioner_states
        SET vector_store_type = 'chromadb_local'
        WHERE dtype = 'local_file'
        """
    )

    # SQLite doesn't support ALTER TABLE ADD CONSTRAINT; a UNIQUE INDEX
    # is functionally equivalent for enforcement and is added in-place
    # via plain CREATE INDEX. The entity-level UniqueConstraint
    # declaration takes effect when the table is recreated from scratch
    # (e.g. for tests).
    op.create_index(
        "uq_provisioner_vector_store_type",
        "provisioner_states",
        ["vector_store_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_provisioner_vector_store_type",
        table_name="provisioner_states",
    )
    op.drop_column("provisioner_states", "vector_store_type")
