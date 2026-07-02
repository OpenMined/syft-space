"""Local filesystem source implementation."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path as SyncPath
from typing import Any

from anyio import Path as AsyncPath
from pydantic import BaseModel, Field, ValidationError

from syft_space.components.ingestion.utils import rglob_visible
from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.interfaces import (
    SourceChangeEvent,
    SourceItem,
    SourcePage,
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


class LocalFileBrowseConfig(BaseModel):
    """Picker-time configuration for the local filesystem source.

    Holds only the fields needed to enumerate the user's home
    directory. Ingest-time fields are added by
    ``LocalFileDatasetConfig`` below.
    """

    show_hidden: bool = Field(
        default=False,
        alias="showHidden",
        description="Whether the picker includes dotfiles. Ingestion ignores hidden paths regardless.",
    )

    model_config = {"populate_by_name": True}


class LocalFileDatasetConfig(LocalFileBrowseConfig):
    """Full dataset configuration for the local filesystem source.

    Extends the browse configuration with the paths to watch and the
    file extensions to admit. The dataset row stores this shape.
    """

    file_paths: list[FilePathItem] = Field(
        ...,
        alias="filePaths",
        description="File or directory paths to watch for ingestion",
    )
    allowed_extensions: list[str] = Field(
        default_factory=lambda: list(DEFAULT_ALLOWED_EXTENSIONS),
        alias="allowedExtensions",
        description="File extensions to ingest, including the leading dot",
    )


class LocalFileBrowser:
    """Picker-time access to the local filesystem.

    Built by ``LocalFileProvider.for_browse``. Exposes a single
    ``list_items`` that returns one level of directory contents under
    the user's home directory.
    """

    def __init__(self, config: LocalFileBrowseConfig) -> None:
        self.config = config

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        """List one level of directory contents under the user's home.

        ``parent_id=None`` lists the home directory; otherwise
        ``parent_id`` is a directory path that must resolve under the
        home directory. Dotfiles are included only when ``show_hidden``
        is set. Folders come first, then files, each group sorted
        alphabetically.

        Returns the whole level in one page (``next_cursor=None``); the
        ``cursor`` argument is accepted for protocol conformance but
        unused. Offset-chunking pathological directories is a future
        follow-up.
        """
        home = SyncPath.home()
        try:
            resolved = (
                home
                if parent_id is None
                else SyncPath(parent_id).expanduser().resolve()
            )
        except OSError as e:
            raise ValueError(f"Invalid path: {parent_id!r}") from e

        try:
            resolved.relative_to(home)
        except ValueError as e:
            raise ValueError("Path must be within home directory") from e

        target = AsyncPath(resolved)
        if not await target.exists():
            raise FileNotFoundError(str(target))
        if not await target.is_dir():
            raise NotADirectoryError(str(target))

        items: list[SourceItem] = []
        async for entry in target.iterdir():
            if not self.config.show_hidden and entry.name.startswith("."):
                continue
            try:
                stat = await entry.stat()
                is_dir = await entry.is_dir()
            except (PermissionError, OSError):
                continue
            extension = (
                entry.suffix.lstrip(".") if (not is_dir and entry.suffix) else None
            )
            items.append(
                SourceItem(
                    external_id=str(entry),
                    display_name=entry.name,
                    parent_id=str(target),
                    is_container=is_dir,
                    is_leaf=not is_dir,
                    size_bytes=None if is_dir else stat.st_size,
                    metadata={
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "extension": extension,
                    },
                )
            )

        items.sort(key=lambda i: (not i.is_container, i.display_name.lower()))
        return SourcePage(items=items, next_cursor=None)


class LocalFileSource:
    """Ingest-time access to the local filesystem.

    Built by ``LocalFileProvider.for_ingest`` from a validated dataset
    configuration. Provides discovery, fetching, fingerprinting, and a
    change stream backed by the shared filesystem watcher.
    """

    def __init__(self, config: LocalFileDatasetConfig) -> None:
        self.config = config
        self._allowed_extensions: set[str] = set(config.allowed_extensions)

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        """List directory contents using the picker's home-rooted walk.

        Delegates to a transient ``LocalFileBrowser`` so the directory
        listing rules stay defined in one place. The browse config is
        derived from this source's ``show_hidden``.
        """
        browser = LocalFileBrowser(
            LocalFileBrowseConfig.model_validate(
                {"show_hidden": self.config.show_hidden}
            )
        )
        return await browser.list_items(parent_id, cursor)

    def allowed_extensions(self) -> set[str]:
        """Allowed file extensions (including the leading dot)."""
        return self._allowed_extensions

    async def _enumerate_paths(self, paths: list[str]) -> list[SourceItem]:
        """Walk every ingestable file under the given paths (dirs expanded).

        Used by ``change_stream`` to seed the ingestion manager with
        ``created`` events for files already on disk. A directory pick
        (branch) is expanded to its files; a file pick (leaf) is emitted
        directly.
        """
        items: list[SourceItem] = []
        for raw in paths:
            root = AsyncPath(raw)
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
            metadata={"source": LocalFileProvider.NAME, "absolute_path": str(path)},
        )

    def fingerprint(self, external_id: str) -> str:
        """Return a ``{size, mtime_ns}`` token used for change detection.

        Serialized without separator whitespace so it round-trips
        byte-equal through SQLite's ``json_object()``, which the
        fingerprint backfill migration relies on.
        """
        stat = SyncPath(external_id).stat()
        return json.dumps(
            {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
            separators=(",", ":"),
        )

    def change_stream(
        self, selected_ids: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        """Yield filesystem change events for the given picks.

        The manager supplies the dataset's pick ids read from the selection
        table; classification is live and local — a directory pick is watched
        and expanded to its files, a file pick is watched and emitted
        directly. The watchdog subscription is opened before the initial scan
        so events that fire during the scan are buffered; the scan emits
        ``created`` for files already on disk, then the watchdog stream
        (create/update/delete) takes over.
        """
        return self._change_stream_impl(selected_ids)

    async def _change_stream_impl(
        self, paths: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        watcher = get_local_file_watcher()
        sub_iter = await watcher.subscribe(paths, self._allowed_extensions)
        try:
            for item in await self._enumerate_paths(paths):
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


class LocalFileProvider:
    """Description of the local filesystem source for the registry.

    Holds metadata, the browse and dataset configuration schemas, and
    the factories that build a ``LocalFileBrowser`` or
    ``LocalFileSource`` from a raw configuration dict.
    """

    NAME = "local_file"

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
    def browse_schema(cls) -> dict[str, Any]:
        """Return JSON schema for the browse-time configuration."""
        return LocalFileBrowseConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return JSON schema for the full dataset configuration."""
        return LocalFileDatasetConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def extract_selected_items(
        cls, configuration: dict[str, Any]
    ) -> list[tuple[str, str | None]]:
        """Return ``(path, description)`` picks from the source configuration."""
        config = LocalFileDatasetConfig.model_validate(configuration)
        return [(item.path, item.description) for item in config.file_paths]

    @classmethod
    def selection_covers(cls, item_id: str, external_id: str) -> bool:
        """A path pick covers itself and, for directories, everything under it."""
        if external_id == item_id:
            return True
        return external_id.startswith(item_id.rstrip(os.sep) + os.sep)

    @classmethod
    async def validate_browse_config(cls, configuration: dict[str, Any]) -> None:
        """Validate a picker-time payload against ``LocalFileBrowseConfig``.

        Raises:
            ValueError: If the payload is malformed.
        """
        try:
            LocalFileBrowseConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid browse configuration: {e}") from e

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate a full dataset configuration and the paths it points to.

        Raises:
            ValueError: If the payload is malformed or any configured
                ``file_paths`` entry does not exist on disk.
        """
        try:
            config = LocalFileDatasetConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        for file_path_item in config.file_paths:
            path = AsyncPath(file_path_item.path)
            if not await path.exists():
                raise ValueError(f"file_paths does not exist: {file_path_item.path}")

    @classmethod
    def for_browse(cls, configuration: dict[str, Any]) -> LocalFileBrowser:
        """Build a browser from a raw browse configuration dict."""
        return LocalFileBrowser(LocalFileBrowseConfig.model_validate(configuration))

    @classmethod
    def for_ingest(cls, configuration: dict[str, Any]) -> LocalFileSource:
        """Build a source from a raw dataset configuration dict."""
        return LocalFileSource(LocalFileDatasetConfig.model_validate(configuration))
