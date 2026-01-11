"""add ingestion_jobs and marketplaces

Revision ID: b80a47b5e5b7
Revises: 640a7f9a94e1
Create Date: 2026-01-11 23:06:06.016015

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b80a47b5e5b7"
down_revision: str | None = "640a7f9a94e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create marketplaces table
    op.create_table(
        "marketplaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("accounting_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "accounting_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "accounting_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_marketplaces_id"), "marketplaces", ["id"], unique=False)

    # Create ingestion_jobs table
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("file_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("file_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_mtime_ns", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_id", "file_path", name="uq_ingestion_job_dataset_file"
        ),
    )
    op.create_index(
        op.f("ix_ingestion_jobs_id"), "ingestion_jobs", ["id"], unique=False
    )
    op.create_index(
        "idx_ingestion_job_tenant_status",
        "ingestion_jobs",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_ingestion_job_dataset_id", "ingestion_jobs", ["dataset_id"], unique=False
    )


def downgrade() -> None:
    # Drop ingestion_jobs
    op.drop_index("idx_ingestion_job_dataset_id", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_job_tenant_status", table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_id"), table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")

    # Drop marketplaces
    op.drop_index(op.f("ix_marketplaces_id"), table_name="marketplaces")
    op.drop_table("marketplaces")
