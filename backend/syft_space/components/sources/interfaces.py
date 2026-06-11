"""Source interfaces and domain models.

A ``BaseSource`` represents a data origin (local files, WordPress, RSS, S3, ...).
Sources are orthogonal to vector stores: a single source can feed any vector
store, and a single vector store can be fed by any source. Bindings between
the two live in ``dataset_types/``.
"""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from syft_space.components.shared.ingest_types import IngestFile


class SourceItem(BaseModel):
    """An item discoverable from a source.

    Surfaced in browse/select UX. ``is_container`` indicates the item holds
    other items (e.g. a folder); ``is_leaf`` indicates it can be ingested
    directly. The two are not mutually exclusive — a container may also be
    ingestable depending on the source.
    """

    external_id: str = Field(
        ..., description="Source-unique identifier (path, post id, RSS guid, ...)"
    )
    display_name: str = Field(..., description="Human-readable label")
    parent_id: str | None = Field(
        default=None, description="Parent container id for hierarchical sources"
    )
    is_container: bool = Field(
        default=False,
        description="True if this contains other items (e.g. a folder)",
    )
    is_leaf: bool = Field(
        default=True, description="True if this can be ingested directly"
    )
    size_bytes: int | None = Field(default=None, description="Optional size hint")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Source-defined metadata"
    )


class SourceChangeEvent(BaseModel):
    """A change emitted by a source's ``change_stream``."""

    event_type: Literal["created", "updated", "deleted"]
    external_id: str
    fingerprint: str | None = Field(default=None, description="Null for delete events")
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseSource(Protocol):
    """Base source interface.

    All concrete data sources must implement this protocol. Sources own
    discovery, change detection, and fetching of their items; they do not
    know about vector stores or persistence.
    """

    NAME: str

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the source with configuration.

        Args:
            config: Configuration dictionary for this source.
        """
        ...

    @classmethod
    def name(cls) -> str:
        """Get the name of the source."""
        ...

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the source."""
        ...

    @classmethod
    def description(cls) -> str:
        """Get the description of the source."""
        ...

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the source."""
        ...

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this source.

        Returns:
            Dictionary describing the configuration schema.
        """
        ...

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the source.

        Args:
            configuration: Configuration dictionary to validate.

        Raises:
            ValidationError: If configuration is invalid.
        """
        ...

    @classmethod
    def enabled(cls) -> bool:
        """Check if this source is enabled."""
        ...

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        """Discover items in this source.

        Args:
            parent_id: For hierarchical sources, descend into the given parent.
                ``None`` returns the top-level items.

        Returns:
            List of items at the requested level.
        """
        ...

    def fetch(self, external_id: str) -> AbstractAsyncContextManager[IngestFile]:
        """Produce an ``IngestFile`` for the given item.

        Returns an async context manager so each source can own any
        materialization/cleanup its fetch needs (no-op for sources whose
        items already live on disk).

        Args:
            external_id: Source-unique identifier of the item to fetch.
        """
        ...

    def change_stream(self) -> AsyncIterator[SourceChangeEvent]:
        """Async iterator of change events for this source.

        Sources own their own watching/polling strategy. The ingestion
        manager consumes this stream to keep the dataset in sync.
        """
        ...

    def fingerprint(self, external_id: str) -> str:
        """Opaque change-detection token for the given item.

        Sources control the format (JSON blob, hash, etag, ...). The
        manager treats this as an opaque string and compares for equality.

        Args:
            external_id: Item identifier.
        """
        ...
