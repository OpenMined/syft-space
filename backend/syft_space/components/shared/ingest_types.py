"""Ingestion pipeline domain types.

Sources produce ``IngestFile`` instances; ingestable vector stores
consume ``IngestRequest`` (a batch of files) and ``IngestContext``
(dataset identity for the request).
"""

from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from syft_space.components.shared.domain_types import Context


class IngestContext(Context):
    """Context for ingestion requests."""

    dataset_id: UUID = Field(..., description="Unique identifier for the dataset")


class IngestFile(BaseModel):
    """Framework-agnostic file wrapper for ingestion."""

    path: Path = Field(..., description="Local readable path")
    filename: str = Field(..., description="Display filename")
    file_size: int | None = Field(default=None, description="Size in bytes")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata"
    )


class IngestRequest(BaseModel):
    """Domain contract for data ingestion."""

    files: list[IngestFile] = Field(
        default_factory=list, description="List of files to ingest"
    )
