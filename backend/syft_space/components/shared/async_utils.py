"""Async utilities for task coordination."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


async def run_after_event(
    event: asyncio.Event,
    coro_func: Callable[..., Awaitable[T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run a coroutine function after an event is set.

    Useful for coordinating async tasks that depend on other tasks completing.

    Args:
        event: Event to wait for before running the coroutine
        coro_func: Async function to call after event is set
        *args: Positional arguments to pass to coro_func
        **kwargs: Keyword arguments to pass to coro_func

    Returns:
        Result of the coroutine function

    Example:
        # Fire-and-forget task that waits for proxy to be ready:
        asyncio.create_task(
            run_after_event(proxy_ready_event, sync_public_url, handler, tenant)
        )
    """
    await event.wait()
    return await coro_func(*args, **kwargs)
