"""Generic sync→async event bridge backed by ``janus``.

Wraps a single janus queue with an explicit lifecycle (``initialize`` /
``close``). Producers may be sync (e.g. watchdog callbacks) or async; the
consumer is async. The bridge is event-type-agnostic — anything yieldable
as a Python object can flow through it. Today it carries
``SourceChangeEvent`` instances; nothing in the bridge itself depends on
that.
"""

from __future__ import annotations

import asyncio

import janus
from loguru import logger

from syft_space.components.sources.interfaces import SourceChangeEvent


class EventBridge:
    """Single-queue sync↔async bridge for source change events."""

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: janus.Queue[SourceChangeEvent] | None = None
        self._maxsize = maxsize
        self._closed = False

    @property
    def is_initialized(self) -> bool:
        return self._queue is not None

    async def initialize(self) -> None:
        """Create the janus queue (must be called from an async context)."""
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

    def push(self, event: SourceChangeEvent) -> bool:
        """Sync-producer entrypoint. Returns False on full or closed queue."""
        if self._queue is None or self._closed:
            return False
        try:
            self._queue.sync_q.put_nowait(event)
            return True
        except janus.SyncQueueFull:
            logger.warning(f"Event queue full, dropping: {event}")
            return False

    async def push_async(self, event: SourceChangeEvent) -> None:
        """Async-producer entrypoint."""
        if self._queue is None:
            raise RuntimeError("EventBridge not initialized")
        await self._queue.async_q.put(event)

    async def pop(self, timeout: float = 1.0) -> SourceChangeEvent | None:
        """Async-consumer entrypoint. Returns None on timeout or shutdown."""
        if self._queue is None:
            return None
        try:
            return await asyncio.wait_for(self._queue.async_q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
