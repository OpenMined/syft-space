"""Source interfaces and domain models.

A source type contributes three classes:

* ``BaseBrowser`` — picker-time capability to list one level of items.
* ``BaseSource`` — ingest-time capability: list, fetch, fingerprint, watch.
* ``BaseSourceProvider`` — describes the source type for the registry:
  name, icon, schemas, validators, and the two factories that build
  ``BaseBrowser`` / ``BaseSource`` instances from a configuration dict.

Sources are orthogonal to vector stores: a single source can feed any
vector store, and a single vector store can be fed by any source.
Bindings between the two live in ``dataset_types/``.
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


class BaseBrowser(Protocol):
    """Picker-time view of a source: list items one level at a time.

    Built by ``BaseSourceProvider.for_browse``. Knows only how to
    discover items (typically using connection / credential fields);
    cannot fetch, fingerprint, or watch.
    """

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        """Discover items at the given level.

        Args:
            parent_id: For hierarchical sources, descend into the given parent.
                ``None`` returns the top-level items.
        """
        ...


class BaseSource(Protocol):
    """Ingest-time view of a source: discover, fetch, and watch for changes.

    Built by ``BaseSourceProvider.for_ingest`` from the full dataset
    configuration. Owns discovery, change detection, and fetching;
    does not know about vector stores or persistence.
    """

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        """Discover items at the given level."""
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

    def fingerprint(self, external_id: str) -> str:
        """Opaque change-detection token for the given item.

        Sources control the format (JSON blob, hash, etag, ...). The
        manager treats this as an opaque string and compares for equality.

        Args:
            external_id: Item identifier.
        """
        ...

    def change_stream(self) -> AsyncIterator[SourceChangeEvent]:
        """Async iterator of change events for this source.

        Sources own their own watching/polling strategy. The ingestion
        manager consumes this stream to keep the dataset in sync.
        """
        ...


class BaseSourceProvider(Protocol):
    """Description of a source type for the registry.

    One Provider per source type. Holds presentational metadata, the
    browse / dataset configuration schemas and their validators, and
    the two factories that build a ``BaseBrowser`` or a ``BaseSource``
    from a configuration dict. The picker calls ``for_browse``;
    ingestion calls ``for_ingest``.
    """

    NAME: str

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
    def enabled(cls) -> bool:
        """Check if this source is enabled."""
        ...

    @classmethod
    def browse_schema(cls) -> dict[str, Any]:
        """JSON schema for the browse-time configuration.

        The browse config is the subset of fields needed to connect or
        discover items (credentials, connection knobs).
        """
        ...

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """JSON schema for the full dataset configuration.

        Must extend ``browse_schema``: every browse field is also a
        dataset field, plus the ingestion-time additions.
        """
        ...

    @classmethod
    async def validate_browse_config(cls, configuration: dict[str, Any]) -> None:
        """Validate a browse-time configuration payload.

        Raises:
            ValueError: If the payload doesn't match ``browse_schema``.
        """
        ...

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the full dataset configuration for the source.

        Args:
            configuration: Dataset-shaped payload (browse fields + ingestion fields).

        Raises:
            ValueError: If the payload doesn't match ``configuration_schema``.
        """
        ...

    @classmethod
    def for_browse(cls, configuration: dict[str, Any]) -> BaseBrowser:
        """Build a browser for the picker from the browse configuration.

        Args:
            configuration: Browse-shaped payload (connection / credentials).
        """
        ...

    @classmethod
    def for_ingest(cls, configuration: dict[str, Any]) -> BaseSource:
        """Build a source for ingestion from the full dataset configuration.

        Args:
            configuration: Dataset-shaped payload (browse fields + ingest fields).
        """
        ...
