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
        UniqueConstraint(
            "dataset_id", "external_id", name="uq_ingestion_job_dataset_external"
        ),
        Index("idx_ingestion_job_tenant_status", "tenant_id", "status"),
        Index("idx_ingestion_job_dataset_id", "dataset_id"),
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

    # Source-agnostic identifiers. ``external_id`` is the source-unique
    # opaque key (filesystem path, WP post id, RSS guid, S3 key, ...).
    # ``fingerprint`` is the source-controlled change-detection token
    # compared as an opaque string.
    external_id: str = Field(
        ...,
        index=True,
        description="Source-unique identifier (path, post id, guid, ...)",
    )
    fingerprint: str = Field(
        ..., description="Source-defined change-detection token (opaque)"
    )

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
