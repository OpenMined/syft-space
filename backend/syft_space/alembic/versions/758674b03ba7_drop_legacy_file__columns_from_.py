"""drop legacy file_* columns from ingestion_jobs

Revision ID: 758674b03ba7
Revises: e95f227b8167
Create Date: 2026-06-05 17:05:10.229827

Completes the source-agnostic ``ingestion_jobs`` re-key. The file-shaped
columns (``file_path`` / ``file_name`` / ``file_size`` /
``file_mtime_ns``) and the inline ``(dataset_id, file_path)`` UNIQUE
constraint are removed; ``external_id`` and ``fingerprint`` take their
place and become NOT NULL. The new uniqueness invariant is
``(dataset_id, external_id)`` enforced via a UNIQUE INDEX (SQLite
can't ALTER TABLE ADD CONSTRAINT).

DB engine: SQLite.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "758674b03ba7"
down_revision: str | None = "e95f227b8167"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The companion non-unique index is dropped first; batch mode below
    # recreates the table without the legacy columns, which also clears
    # the inline UNIQUE (dataset_id, file_path) constraint.
    op.drop_index("idx_ingestion_job_dataset_external", table_name="ingestion_jobs")

    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.drop_column("file_path")
        batch_op.drop_column("file_name")
        batch_op.drop_column("file_size")
        batch_op.drop_column("file_mtime_ns")
        batch_op.alter_column(
            "external_id",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column(
            "fingerprint",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )

    op.create_index(
        "uq_ingestion_job_dataset_external",
        "ingestion_jobs",
        ["dataset_id", "external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ingestion_job_dataset_external", table_name="ingestion_jobs")

    # Re-add the legacy columns nullable so backfill can populate before
    # batch mode recreates the table with NOT NULL + inline UNIQUE.
    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.add_column(
            sa.Column("file_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("file_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(sa.Column("file_size", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("file_mtime_ns", sa.Integer(), nullable=True))

    # Best-effort backfill: copy external_id into file_path / file_name; the
    # original size/mtime are unrecoverable, so zeros stand in.
    op.execute(
        """
        UPDATE ingestion_jobs
        SET file_path = external_id,
            file_name = external_id,
            file_size = 0,
            file_mtime_ns = 0
        WHERE file_path IS NULL
        """
    )

    with op.batch_alter_table(
        "ingestion_jobs",
        table_args=[
            sa.UniqueConstraint(
                "dataset_id", "file_path", name="uq_ingestion_job_dataset_file"
            )
        ],
    ) as batch_op:
        batch_op.alter_column(
            "file_path",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column(
            "file_name",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )
        batch_op.alter_column("file_size", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column(
            "file_mtime_ns", existing_type=sa.Integer(), nullable=False
        )
        batch_op.alter_column(
            "external_id",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        )
        batch_op.alter_column(
            "fingerprint",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        )

    op.create_index(
        "idx_ingestion_job_dataset_external",
        "ingestion_jobs",
        ["dataset_id", "external_id"],
        unique=False,
    )
