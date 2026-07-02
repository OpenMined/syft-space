"""No-op source — for datasets whose vector store is fed externally.

Used by bindings such as ``RemoteWeaviateDatasetType`` where the
vector store is populated outside this process. ``NoOpSource`` lists
nothing and emits no change events, so the ingestion manager has no
work to spawn; ``fetch`` and ``fingerprint`` raise because nothing in
this binding should ever ask for them. ``NoOpBrowser`` is the picker-
side counterpart and also lists nothing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.sources.interfaces import (
    SourceChangeEvent,
    SourcePage,
)


class NoOpBrowser:
    """Picker-side no-op. ``list_items`` always returns an empty page."""

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        return SourcePage(items=[], next_cursor=None)


class NoOpSource:
    """Ingest-side no-op. Lists nothing and emits no change events."""

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        return SourcePage(items=[], next_cursor=None)

    def fetch(self, external_id: str) -> AbstractAsyncContextManager[IngestFile]:
        """Always raises — the no-op source has nothing to fetch."""
        raise NotImplementedError(
            f"{NoOpProvider.NAME!r} source has no fetchable items"
        )

    def fingerprint(self, external_id: str) -> str:
        """Always raises — the no-op source has no fingerprintable items."""
        raise NotImplementedError(
            f"{NoOpProvider.NAME!r} source has no fingerprintable items"
        )

    def change_stream(
        self, selected_ids: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        """Return an async iterator that yields nothing and completes."""
        return self._change_stream_impl()

    async def _change_stream_impl(self) -> AsyncIterator[SourceChangeEvent]:
        if False:  # pragma: no cover
            yield  # type: ignore[unreachable]


class NoOpProvider:
    """Description of the no-op source for the registry.

    ``IS_NOOP`` is read by the ingestion manager so it can skip
    spawning an empty per-dataset task for bindings that don't ingest
    from this process.
    """

    NAME = "noop"
    IS_NOOP = True

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
    def browse_schema(cls) -> dict[str, Any]:
        """No browse-time configuration — nothing to connect to."""
        return {"type": "object", "properties": {}}

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """No configurable fields."""
        return {"type": "object", "properties": {}}

    @classmethod
    def extract_selected_items(
        cls, configuration: dict[str, Any]
    ) -> list[tuple[str, str | None]]:
        """No selection concept — always empty."""
        return []

    @classmethod
    def selection_covers(cls, item_id: str, external_id: str) -> bool:
        """No selection concept — nothing is ever covered."""
        return False

    @classmethod
    async def validate_browse_config(cls, configuration: dict[str, Any]) -> None:
        """No-op — any payload is accepted."""
        return None

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """No-op — any configuration is accepted (and ignored)."""
        return None

    @classmethod
    def for_browse(cls, configuration: dict[str, Any]) -> NoOpBrowser:
        """Build a browser. The configuration is ignored."""
        return NoOpBrowser()

    @classmethod
    def for_ingest(cls, configuration: dict[str, Any]) -> NoOpSource:
        """Build a source. The configuration is ignored."""
        return NoOpSource()
