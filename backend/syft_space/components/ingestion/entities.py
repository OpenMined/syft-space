"""Ingestion job database entities."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Column, Field, ForeignKey, SQLModel


class IngestionJobStatus(str, Enum):
    """Status for individual file ingestion jobs."""

    PENDING = "pending"  # File discovered, waiting to be processed
    IN_PROGRESS = "in_progress"  # Currently being ingested
    COMPLETED = "completed"  # Successfully ingested
    FAILED = "failed"  # Ingestion failed (can retry)
    CANCELLED = "cancelled"  # Job cancelled (e.g., file deleted, dataset deleted)


class IngestionJob(SQLModel, table=True):
    """Tracks individual item ingestion status for a dataset.

    Each job represents one source item's ingestion state. Jobs are created when:
    - Dataset ingestion is started (initial scan of existing items)
    - Source change_stream emits a created/updated event

    The opaque ``fingerprint`` string (source-defined) is compared for
    equality to decide whether re-ingestion is needed.
    """

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        # Deprecated uniqueness on (dataset_id, file_path). Will be
        # replaced by (dataset_id, external_id) once the legacy file_*
        # columns are dropped.
        UniqueConstraint(
            "dataset_id", "file_path", name="uq_ingestion_job_dataset_file"
        ),
        # Index for efficient tenant-scoped queries
        Index("idx_ingestion_job_tenant_status", "tenant_id", "status"),
        # Index for dataset lookups
        Index("idx_ingestion_job_dataset_id", "dataset_id"),
        # Source-agnostic lookup path. Non-unique during the dual-write
        # transition; promoted to UNIQUE once file_path is dropped.
        Index("idx_ingestion_job_dataset_external", "dataset_id", "external_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    # Tenant awareness for multi-tenant queries
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )

    # Dataset reference
    dataset_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("datasets.id", ondelete="CASCADE")),
        description="Dataset this job belongs to",
    )

    # Source-agnostic identifiers.
    # ``external_id`` is the source-unique opaque key (filesystem path,
    # WP post id, RSS guid, S3 key, ...). ``fingerprint`` is the
    # source-controlled change-detection token compared as an opaque
    # string. Both are nullable during the dual-write transition; they
    # will become NOT NULL once the legacy file_* columns are dropped.
    external_id: str | None = Field(
        default=None,
        index=True,
        description="Source-unique identifier (path, post id, guid, ...)",
    )
    fingerprint: str | None = Field(
        default=None,
        description="Source-defined change-detection token (opaque)",
    )

    # Deprecated file_*-specific columns. Populated by dual-write
    # alongside external_id/fingerprint until they're dropped.
    file_path: str = Field(..., description="Absolute path to the file")
    file_name: str = Field(..., description="File name (basename)")
    file_size: int = Field(..., description="File size in bytes")
    file_mtime_ns: int = Field(..., description="File modification time in nanoseconds")

    # Status tracking
    status: str = Field(
        default=IngestionJobStatus.PENDING.value,
        description="Current job status",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if status is FAILED",
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = Field(
        default=None,
        description="When processing started",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When processing completed (success or failure)",
    )
