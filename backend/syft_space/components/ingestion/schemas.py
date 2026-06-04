"""Ingestion API schemas for request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IngestionJobResponse(BaseModel):
    """Response model for a single ingestion job."""

    id: UUID = Field(..., description="Job UUID")
    external_id: str | None = Field(
        None, description="Source-unique identifier (path, post id, guid, ...)"
    )
    fingerprint: str | None = Field(
        None, description="Source-defined change-detection token (opaque)"
    )
    file_path: str = Field(..., description="Absolute file path")
    file_name: str = Field(..., description="File name")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Job status")
    error_message: str | None = Field(None, description="Error message if failed")
    retry_count: int = Field(..., description="Number of retry attempts")
    created_at: datetime = Field(..., description="When job was created")
    started_at: datetime | None = Field(None, description="When processing started")
    completed_at: datetime | None = Field(None, description="When processing finished")

    class Config:
        """Pydantic config."""

        from_attributes = True


class IngestionStatusResponse(BaseModel):
    """Response model for ingestion status overview."""

    dataset_id: UUID = Field(..., description="Dataset UUID")
    dataset_name: str = Field(..., description="Dataset name")
    is_watching: bool = Field(..., description="Whether watcher is active")
    total_jobs: int = Field(..., description="Total number of jobs")
    pending: int = Field(..., description="Pending jobs count")
    in_progress: int = Field(..., description="In-progress jobs count")
    completed: int = Field(..., description="Completed jobs count")
    failed: int = Field(..., description="Failed jobs count")
    cancelled: int = Field(..., description="Cancelled jobs count")


class IngestionJobListResponse(BaseModel):
    """Response model for paginated job list."""

    jobs: list[IngestionJobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total count matching filters")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset")


class StartIngestionResponse(BaseModel):
    """Response model for starting ingestion."""

    message: str = Field(..., description="Result message")
    jobs_created: int = Field(..., description="Number of jobs created")
    is_watching: bool = Field(..., description="Whether watcher is now active")


class StopIngestionResponse(BaseModel):
    """Response model for stopping ingestion."""

    message: str = Field(..., description="Result message")
    jobs_cancelled: int = Field(..., description="Number of jobs cancelled")


class RetryIngestionResponse(BaseModel):
    """Response model for retry action."""

    message: str = Field(..., description="Result message")
    jobs_reset: int = Field(..., description="Number of jobs reset to pending")
