"""Event bridge for sync-to-async file event communication.

This module provides a clean abstraction over janus queue for bridging
synchronous watchdog callbacks to asynchronous event processing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path as SyncPath
from typing import TYPE_CHECKING
from uuid import UUID

import janus
from loguru import logger

from syft_space.components.ingestion.events import FileEvent, FileEventType

if TYPE_CHECKING:
    from anyio import Path as AsyncPath


class EventBridge:
    """Bridge for sync-to-async file event communication.

    Encapsulates janus queue and provides clean interfaces for:
    - Sync producer (watchdog callbacks)
    - Async consumer (event processor)

    All FileEvent creation flows through this class, ensuring
    consistent validation and metadata.
    """

    def __init__(self, maxsize: int = 0):
        """Initialize the event bridge.

        Args:
            maxsize: Max queue size (0 = unbounded). Consider setting
                     a limit in production for backpressure.
        """
        self._queue: janus.Queue[FileEvent] | None = None
        self._maxsize = maxsize
        self._closed = False

    @property
    def is_initialized(self) -> bool:
        """Check if bridge has been initialized."""
        return self._queue is not None

    async def initialize(self) -> None:
        """Initialize the janus queue (call from async context)."""
        if self._queue is not None:
            return
        self._queue = janus.Queue(maxsize=self._maxsize)
        self._closed = False

    async def close(self) -> None:
        """Close the queue and wait for cleanup."""
        if self._queue is None:
            return
        self._queue.close()
        await self._queue.wait_closed()
        self._queue = None
        self._closed = True

    # -------------------------------------------------------------------------
    # Sync Producer Interface (for watchdog callbacks)
    # -------------------------------------------------------------------------

    def push_created(
        self,
        dataset_id: UUID,
        tenant_id: UUID,
        file_path: SyncPath,
        file_size: int,
        file_mtime_ns: int,
    ) -> bool:
        """Push a file created event (sync, non-blocking).

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            file_path: Path to the created file
            file_size: File size in bytes
            file_mtime_ns: File modification time in nanoseconds

        Returns:
            True if event was queued, False if queue is full/closed
        """
        if self._queue is None or self._closed:
            return False

        event = self.create_event(
            event_type=FileEventType.CREATED,
            dataset_id=dataset_id,
            tenant_id=tenant_id,
            file_path=file_path,
            file_size=file_size,
            file_mtime_ns=file_mtime_ns,
        )

        try:
            self._queue.sync_q.put_nowait(event)
            logger.debug(f"Queued file created: {file_path}")
            return True
        except janus.SyncQueueFull:
            logger.warning(f"Event queue full, dropping: {file_path}")
            return False

    def push_deleted(
        self,
        dataset_id: UUID,
        tenant_id: UUID,
        file_path: SyncPath,
    ) -> bool:
        """Push a file deleted event (sync, non-blocking).

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            file_path: Path to the deleted file

        Returns:
            True if event was queued, False if queue is full/closed
        """
        if self._queue is None or self._closed:
            return False

        event = self.create_event(
            event_type=FileEventType.DELETED,
            dataset_id=dataset_id,
            tenant_id=tenant_id,
            file_path=file_path,
        )

        try:
            self._queue.sync_q.put_nowait(event)
            logger.debug(f"Queued file deleted: {file_path}")
            return True
        except janus.SyncQueueFull:
            logger.warning(f"Event queue full, dropping delete: {file_path}")
            return False

    # -------------------------------------------------------------------------
    # Async Consumer Interface (for event processor)
    # -------------------------------------------------------------------------

    async def pop(self, timeout: float = 1.0) -> FileEvent | None:
        """Pop next event from queue (async, with timeout).

        Args:
            timeout: Seconds to wait for an event

        Returns:
            FileEvent or None if timeout/closed

        Raises:
            janus.AsyncQueueShutDown: If queue was closed
        """
        if self._queue is None:
            return None

        try:
            return await asyncio.wait_for(
                self._queue.async_q.get(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None

    async def push_async(self, event: FileEvent) -> None:
        """Push event from async context (for file scanning).

        Args:
            event: FileEvent to push
        """
        if self._queue is None:
            raise RuntimeError("EventBridge not initialized")
        await self._queue.async_q.put(event)

    # -------------------------------------------------------------------------
    # Factory Methods (centralize FileEvent creation)
    # -------------------------------------------------------------------------

    @staticmethod
    def create_event(
        event_type: FileEventType,
        dataset_id: UUID,
        tenant_id: UUID,
        file_path: SyncPath | AsyncPath,
        file_size: int | None = None,
        file_mtime_ns: int | None = None,
    ) -> FileEvent:
        """Create a FileEvent with validation.

        Centralizes event creation for consistency.
        """
        return FileEvent(
            event_type=event_type,
            dataset_id=dataset_id,
            tenant_id=tenant_id,
            file_path=file_path,
            file_size=file_size,
            file_mtime_ns=file_mtime_ns,
        )
