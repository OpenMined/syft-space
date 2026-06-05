"""No-op source — for datasets whose vector store is fed externally.

Used by bindings (e.g. ``RemoteWeaviateDatasetType``) where the vector
store is already populated outside this process. ``NoOpSource``
satisfies the ``BaseSource`` protocol by reporting nothing to ingest
and producing no change events; calls that imply a fetch raise.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.sources.interfaces import (
    SourceChangeEvent,
    SourceItem,
)


class NoOpSource:
    """No-op source. Lists nothing, fetches nothing, emits no events."""

    NAME = "noop"

    def __init__(self, config: dict[str, Any]) -> None:
        self.raw_config = config

    @classmethod
    def name(cls) -> str:
        """Get the name of the source."""
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the source."""
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        """Get the description of the source."""
        return "No-op source — for datasets whose vector store is fed externally."

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the source."""
        return "🚫"

    @classmethod
    def enabled(cls) -> bool:
        """Always enabled — no optional dependencies."""
        return True

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """No configurable fields."""
        return {"type": "object", "properties": {}}

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """No-op — any configuration is accepted (and ignored)."""
        return None

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        """Always empty — nothing to ingest."""
        return []

    def fetch(self, external_id: str) -> AbstractAsyncContextManager[IngestFile]:
        """No-op source has nothing to fetch."""
        raise NotImplementedError(f"{self.NAME!r} source has no fetchable items")

    def fingerprint(self, external_id: str) -> str:
        """No-op source has no fingerprintable items."""
        raise NotImplementedError(f"{self.NAME!r} source has no fingerprintable items")

    def change_stream(self) -> AsyncIterator[SourceChangeEvent]:
        """Return an async iterator that yields nothing.

        The ingestion manager iterates ``change_stream()`` and only
        spawns work for datasets whose source has something to report;
        for no-op sources this completes immediately.
        """
        return self._change_stream_impl()

    async def _change_stream_impl(self) -> AsyncIterator[SourceChangeEvent]:
        if False:  # pragma: no cover
            yield  # type: ignore[unreachable]
