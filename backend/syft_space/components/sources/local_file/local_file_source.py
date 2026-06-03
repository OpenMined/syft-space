"""Local filesystem source implementation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path as SyncPath
from typing import Any

from anyio import Path as AsyncPath
from pydantic import BaseModel, Field, ValidationError

from syft_space.components.dataset_types.interfaces import IngestFile
from syft_space.components.ingestion.utils import rglob_visible
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.interfaces import (
    SourceChangeEvent,
    SourceItem,
)
from syft_space.components.sources.local_file.local_file_watcher import (
    get_local_file_watcher,
)

DEFAULT_ALLOWED_EXTENSIONS = [
    ".pdf",
    ".txt",
    ".html",
    ".xlsx",
    ".docx",
    ".md",
    ".csv",
    ".json",
]


class FilePathItem(BaseModel):
    """A file path item with path and description."""

    path: str = Field(..., description="The file or directory path to watch")
    description: str = Field(..., description="Description of the data at this path")


class LocalFileSourceConfiguration(BaseModel):
    """Configuration for the local filesystem source."""

    file_paths: list[FilePathItem] = Field(
        default_factory=list,
        alias="filePaths",
        description="File or directory paths to watch for ingestion",
    )
    allowed_extensions: list[str] = Field(
        default_factory=lambda: list(DEFAULT_ALLOWED_EXTENSIONS),
        alias="allowedExtensions",
        description="Allowed file extensions for ingestion (including the leading dot)",
    )

    model_config = {"populate_by_name": True}


class LocalFileSource:
    """File-system source: enumerates files under watched paths.

    Change-stream wiring (``watchdog`` observer + event bridge) is deferred to
    the manager-generalization PR; ``change_stream`` raises until then.
    """

    NAME = "local_file"

    def __init__(self, config: dict[str, Any]) -> None:
        self.raw_config = config
        self.config = LocalFileSourceConfiguration.model_validate(config)
        self._allowed_extensions: set[str] = set(self.config.allowed_extensions)

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
        return "Local filesystem source"

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the source."""
        return "📁"

    @classmethod
    def enabled(cls) -> bool:
        """Check if this source is enabled."""
        return True

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return JSON schema for this source's configuration."""
        return LocalFileSourceConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the source.

        Raises:
            ValueError: If configuration is malformed or references a missing path.
        """
        try:
            config = LocalFileSourceConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        for file_path_item in config.file_paths:
            path = AsyncPath(file_path_item.path)
            if not await path.exists():
                raise ValueError(f"file_paths does not exist: {file_path_item.path}")

    def watched_paths(self) -> list[str]:
        """Absolute directory/file paths to monitor."""
        return [item.path for item in self.config.file_paths]

    def allowed_extensions(self) -> set[str]:
        """Allowed file extensions (including the leading dot)."""
        return self._allowed_extensions

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        """Enumerate matching files under watched paths.

        ``parent_id`` is ignored — this source returns the flat set of
        ingestable files rather than a hierarchical browse view.
        """
        items: list[SourceItem] = []
        for fp in self.config.file_paths:
            root = AsyncPath(fp.path)
            if await root.is_file():
                if root.suffix in self._allowed_extensions:
                    items.append(await self._to_source_item(root))
                continue
            if await root.is_dir():
                async for path in rglob_visible(root):
                    if await path.is_file() and path.suffix in self._allowed_extensions:
                        items.append(await self._to_source_item(path))
        return items

    @asynccontextmanager
    async def fetch(self, external_id: str) -> AsyncIterator[IngestFile]:
        """Yield an ``IngestFile`` pointing at the on-disk path."""
        path = SyncPath(external_id)
        stat = path.stat()
        yield IngestFile(
            path=path,
            filename=path.name,
            file_size=stat.st_size,
            metadata={"source": self.NAME, "absolute_path": str(path)},
        )

    def fingerprint(self, external_id: str) -> str:
        """JSON-encoded ``{size, mtime_ns}`` token for change detection."""
        stat = SyncPath(external_id).stat()
        return json.dumps({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns})

    def change_stream(self) -> AsyncIterator[SourceChangeEvent]:
        """Async iterator of filesystem change events.

        Order: the underlying watchdog subscription is opened first (so any
        events occurring during the initial scan are buffered), then the
        initial scan yields ``created`` events for files already on disk,
        then the watchdog event stream takes over.
        """
        return self._change_stream_impl()

    async def _change_stream_impl(self) -> AsyncIterator[SourceChangeEvent]:
        watcher = get_local_file_watcher()
        sub_iter = await watcher.subscribe(
            self.watched_paths(), self._allowed_extensions
        )
        try:
            for item in await self.list_items():
                yield SourceChangeEvent(
                    event_type="created",
                    external_id=item.external_id,
                    fingerprint=self.fingerprint(item.external_id),
                )
            async for event in sub_iter:
                yield event
        finally:
            await sub_iter.aclose()

    async def _to_source_item(self, path: AsyncPath) -> SourceItem:
        stat = await path.stat()
        return SourceItem(
            external_id=str(path),
            display_name=path.name,
            parent_id=str(path.parent) if str(path.parent) != str(path) else None,
            is_container=False,
            is_leaf=True,
            size_bytes=stat.st_size,
            metadata={},
        )
