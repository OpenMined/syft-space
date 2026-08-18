"""Shared filesystem watcher for local-file sources.

A single ``watchdog.Observer`` thread services all live ``LocalFileSource``
instances. Per-source subscriptions get their own handler + janus queue;
events flow only to the subscription whose handler fired. The Observer
starts lazily on the first ``subscribe()`` call and stops when the watcher
is shut down — so deployments without local-file datasets pay no thread or
FD cost.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path as SyncPath
from uuid import UUID, uuid4

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from syft_space.components.ingestion.event_bridge import EventBridge
from syft_space.components.sources.interfaces import SourceChangeEvent


class _WatchedPathFilter:
    """Per-subscription filter: which file paths are inside the watched set.

    All paths are resolved to absolute, symlink-free form on construction
    and on lookup — necessary because the OS may report events with a
    path that resolves through a symlink (e.g. macOS ``/var`` →
    ``/private/var``) different from the configured watch path.
    """

    def __init__(
        self, watched_dirs: set[SyncPath], watched_files: set[SyncPath]
    ) -> None:
        self._watched_dirs = {p.resolve() for p in watched_dirs}
        self._watched_files = {p.resolve() for p in watched_files}

    def is_watched(self, file_path: SyncPath) -> bool:
        resolved = file_path.resolve()
        if resolved in self._watched_files:
            return True
        for watched_dir in self._watched_dirs:
            try:
                resolved.relative_to(watched_dir)
                return True
            except ValueError:
                continue
        return False


def _file_fingerprint(stat_result: object) -> str:
    """Serialize byte-identically to ``LocalFileSource.fingerprint``.

    The repository compares fingerprints as opaque strings, so the watcher
    and the source MUST produce the same serialization for the same stat —
    a formatting difference alone would re-queue unchanged files.
    """
    return json.dumps(
        {
            "size": stat_result.st_size,  # type: ignore[attr-defined]
            "mtime_ns": stat_result.st_mtime_ns,  # type: ignore[attr-defined]
        },
        separators=(",", ":"),
    )


class _SubscriptionHandler(FileSystemEventHandler):
    """Per-subscription watchdog handler: pushes ``SourceChangeEvent`` into one bridge."""

    def __init__(
        self,
        bridge: EventBridge,
        path_filter: _WatchedPathFilter,
        allowed_extensions: set[str],
    ) -> None:
        super().__init__()
        self._bridge = bridge
        self._path_filter = path_filter
        self._allowed_extensions = allowed_extensions

    def _emit_with_fingerprint(self, event_type: str, file_path: SyncPath) -> None:
        try:
            stat = file_path.stat()
        except OSError as e:
            logger.warning(f"Failed to stat {file_path}: {e}")
            return
        self._bridge.push(
            SourceChangeEvent(
                event_type=event_type,  # type: ignore[arg-type]
                # Resolved, so watcher events and the initial scan agree on
                # one external_id per file (the OS may report either form
                # when the watched path traverses a symlink).
                external_id=str(file_path.resolve()),
                fingerprint=_file_fingerprint(stat),
            )
        )

    def _wants(self, event: FileSystemEvent) -> SyncPath | None:
        if event.is_directory:
            return None
        file_path = SyncPath(event.src_path)
        if file_path.suffix not in self._allowed_extensions:
            return None
        if not self._path_filter.is_watched(file_path):
            return None
        return file_path

    def on_created(self, event: FileSystemEvent) -> None:
        path = self._wants(event)
        if path is not None:
            self._emit_with_fingerprint("created", path)

    def on_modified(self, event: FileSystemEvent) -> None:
        path = self._wants(event)
        if path is not None:
            self._emit_with_fingerprint("updated", path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        path = self._wants(event)
        if path is None:
            return
        self._bridge.push(
            SourceChangeEvent(
                event_type="deleted",
                external_id=str(path.resolve()),
                fingerprint=None,
            )
        )


@dataclass
class _Subscription:
    id: UUID
    bridge: EventBridge
    handler: _SubscriptionHandler
    watches: list[object] = field(default_factory=list)


class LocalFileWatcher:
    """Shared filesystem watcher: one Observer thread, many isolated subscriptions.

    Lifecycle: Observer starts lazily on first ``subscribe()`` and joins on
    ``shutdown()``. Subscriptions are independent — closing one does not
    affect others; closing the last one leaves the Observer running until
    explicit shutdown (avoids races with a subscribe arriving mid-stop).
    """

    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._observer_lock = threading.Lock()
        self._subscriptions: dict[UUID, _Subscription] = {}
        self._subs_lock = asyncio.Lock()

    async def startup(self) -> None:
        """No-op — Observer is started lazily on first ``subscribe()``."""
        return None

    async def shutdown(self) -> None:
        """Tear down every subscription and join the Observer thread."""
        async with self._subs_lock:
            for sub_id in list(self._subscriptions.keys()):
                await self._tear_down_subscription_locked(sub_id)
            observer = self._observer
            self._observer = None
        if observer is not None:
            observer.stop()
            observer.join(timeout=5.0)

    def _ensure_observer(self) -> Observer:
        with self._observer_lock:
            if self._observer is None:
                self._observer = Observer()
                self._observer.start()
            return self._observer

    async def subscribe(
        self,
        watched_paths: list[str],
        allowed_extensions: set[str],
    ) -> AsyncIterator[SourceChangeEvent]:
        """Open a new subscription and return an async iterator of change events.

        The Observer starts (if not running) and the watch handlers are
        scheduled before this returns — so events occurring during any
        post-subscribe initial-scan run by the caller are already being
        buffered.

        Args:
            watched_paths: Absolute directory or file paths to watch.
            allowed_extensions: File extensions (with leading dot) to forward.

        Returns:
            Async iterator that yields ``SourceChangeEvent``. Cancelling the
            consumer triggers cleanup (handler unscheduled, queue closed).
        """
        watched_dirs, watched_files, watch_targets = self._partition_paths(
            watched_paths
        )
        path_filter = _WatchedPathFilter(watched_dirs, watched_files)
        bridge = EventBridge()
        await bridge.initialize()
        handler = _SubscriptionHandler(bridge, path_filter, allowed_extensions)

        observer = self._ensure_observer()
        watches: list[object] = []
        for watch_path, recursive in watch_targets.items():
            try:
                watch = observer.schedule(handler, watch_path, recursive=recursive)
                watches.append(watch)
            except Exception as e:
                logger.exception(f"Failed to schedule watch on {watch_path}: {e}")

        sub_id = uuid4()
        sub = _Subscription(id=sub_id, bridge=bridge, handler=handler, watches=watches)
        async with self._subs_lock:
            self._subscriptions[sub_id] = sub

        return self._stream(sub_id)

    async def _stream(self, sub_id: UUID) -> AsyncIterator[SourceChangeEvent]:
        try:
            while True:
                sub = self._subscriptions.get(sub_id)
                if sub is None:
                    return
                event = await sub.bridge.pop(timeout=1.0)
                if event is not None:
                    yield event
        finally:
            async with self._subs_lock:
                await self._tear_down_subscription_locked(sub_id)

    async def _tear_down_subscription_locked(self, sub_id: UUID) -> None:
        """Caller must hold ``_subs_lock``."""
        sub = self._subscriptions.pop(sub_id, None)
        if sub is None:
            return
        observer = self._observer
        if observer is not None:
            for watch in sub.watches:
                try:
                    observer.unschedule(watch)
                except Exception as e:
                    logger.debug(f"Failed to unschedule watch: {e}")
        await sub.bridge.close()

    @staticmethod
    def _partition_paths(
        watched_paths: list[str],
    ) -> tuple[set[SyncPath], set[SyncPath], dict[str, bool]]:
        watched_dirs: set[SyncPath] = set()
        watched_files: set[SyncPath] = set()
        watch_targets: dict[str, bool] = {}
        for path_str in watched_paths:
            path = SyncPath(path_str)
            if not path.exists():
                logger.warning(f"Cannot watch non-existent path: {path_str}")
                continue
            if path.is_dir():
                watched_dirs.add(path)
                watch_targets[str(path)] = True
            else:
                watched_files.add(path)
                parent = str(path.parent)
                if parent not in watch_targets:
                    watch_targets[parent] = False
        return watched_dirs, watched_files, watch_targets


_default_watcher: LocalFileWatcher | None = None
_default_watcher_lock = threading.Lock()


def get_local_file_watcher() -> LocalFileWatcher:
    """Return the process-wide shared watcher, constructing it on first call."""
    global _default_watcher
    with _default_watcher_lock:
        if _default_watcher is None:
            _default_watcher = LocalFileWatcher()
        return _default_watcher


async def init_local_file_watcher() -> None:
    """Initialize the shared watcher's lifecycle (idempotent)."""
    await get_local_file_watcher().startup()


async def shutdown_local_file_watcher() -> None:
    """Shut down the shared watcher and clear the singleton (idempotent)."""
    global _default_watcher
    with _default_watcher_lock:
        watcher = _default_watcher
        _default_watcher = None
    if watcher is not None:
        await watcher.shutdown()
