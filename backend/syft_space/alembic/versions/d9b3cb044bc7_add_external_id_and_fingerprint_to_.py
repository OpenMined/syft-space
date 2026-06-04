"""add external_id and fingerprint to ingestion_jobs

Revision ID: d9b3cb044bc7
Revises: b2f4a3c7e108
Create Date: 2026-06-03 12:06:05.429265

Source-agnostic identifiers for ingestion_jobs.

Adds ``external_id`` and ``fingerprint`` columns to ``ingestion_jobs``.
Existing rows are backfilled from the legacy ``file_path`` /
``file_size`` / ``file_mtime_ns`` columns so the new fingerprint string
matches what ``LocalFileSource.fingerprint()`` produces today
(``json({"size": ..., "mtime_ns": ...})``). The legacy columns are
kept while callers transition off them and will be dropped in a
follow-up migration.

DB engine: SQLite. ``json_object()`` is SQLite syntax — if the project
gains a Postgres target, this migration's backfill needs a dialect
branch (``jsonb_build_object``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # Added for SQLModel support
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9b3cb044bc7"
down_revision: str | None = "b2f4a3c7e108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column("fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    # Backfill: external_id from file_path; fingerprint from the
    # LocalFileSource.fingerprint() JSON shape.
    op.execute(
        """
        UPDATE ingestion_jobs
        SET external_id = file_path,
            fingerprint = json_object('size', file_size, 'mtime_ns', file_mtime_ns)
        WHERE external_id IS NULL
        """
    )

    op.create_index(
        op.f("ix_ingestion_jobs_external_id"),
        "ingestion_jobs",
        ["external_id"],
        unique=False,
    )
    # Non-unique during the dual-write transition. A follow-up migration
    # drops the legacy (dataset_id, file_path) unique constraint and
    # promotes this index to UNIQUE.
    op.create_index(
        "idx_ingestion_job_dataset_external",
        "ingestion_jobs",
        ["dataset_id", "external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_ingestion_job_dataset_external", table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_external_id"), table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "fingerprint")
    op.drop_column("ingestion_jobs", "external_id")
