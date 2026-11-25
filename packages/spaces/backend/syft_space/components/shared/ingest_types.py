"""Ingestion pipeline domain types.

Sources produce ``IngestFile`` instances; ingestable vector stores
consume ``IngestRequest`` (a batch of files) and ``IngestContext``
(dataset identity for the request).
"""

from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from syft_space.components.shared.cancellation import CancelToken
from syft_space.components.shared.domain_types import Context


class IngestCancelled(Exception):
    """An ingest stopped because its cancel token was set."""


class IngestContext(Context):
    """Context for ingestion requests."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataset_id: UUID = Field(..., description="Unique identifier for the dataset")
    cancel: CancelToken = Field(
        default_factory=CancelToken,
        description="Set to stop this ingest while it runs",
    )


class IngestFile(BaseModel):
    """Framework-agnostic file wrapper for ingestion."""

    external_id: str = Field(
        ...,
        description=(
            "Source-unique id of the item. The document id stored in the "
            "vector store derives from it, so re-ingesting replaces the "
            "previous version instead of adding a second copy."
        ),
    )
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
