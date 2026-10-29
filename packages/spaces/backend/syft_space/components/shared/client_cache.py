"""One process-wide cache of long-lived clients (vector stores, model APIs).

Store and model-type instances are rebuilt per request, so a client cannot
live on the instance. Callers ask here for a client by (namespace,
connection key) and say how to connect and, if needed, how to close. Each
client is connected at most once, even under concurrent first callers.
The app lifespan closes everything at shutdown; tests clear between cases.
Importing this module pulls in no client library, so the composition root
can close clients without defeating the registries' lazy imports.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from pydantic import BaseModel

_clients: dict[tuple, tuple[Any, Callable[[Any], Awaitable[None]] | None]] = {}
_locks: dict[tuple, asyncio.Lock] = {}


async def get_client(
    namespace: str,
    key: tuple,
    connect: Callable[[], Awaitable[Any]],
    close: Callable[[Any], Awaitable[None]] | None = None,
) -> Any:
    """The shared client for ``namespace`` + ``key``, connecting on first use.

    ``namespace`` is the caller's name (e.g. the store's ``NAME``) so equal
    keys from different callers never collide. ``close`` is kept with the
    client and run by ``evict`` / ``close_all``. A failing ``connect``
    caches nothing, so the next caller retries.
    """
    full_key = (namespace, *key)
    if full_key in _clients:
        return _clients[full_key][0]
    async with _locks.setdefault(full_key, asyncio.Lock()):
        if full_key not in _clients:
            _clients[full_key] = (await connect(), close)
        return _clients[full_key][0]


async def evict(namespace: str, key: tuple) -> None:
    """Close and drop one client so the next ``get_client`` reconnects."""
    await _evict((namespace, *key))


async def close_all() -> None:
    for full_key in list(_clients):
        await _evict(full_key)


def key_from(config: BaseModel, fields: list[str]) -> tuple:
    """Cache key: the named config fields (alias names), frozen to hash."""
    dump = config.model_dump(by_alias=True, mode="json")
    return tuple(_freeze(dump.get(f)) for f in fields)


async def _evict(full_key: tuple) -> None:
    entry = _clients.pop(full_key, None)
    _locks.pop(full_key, None)
    if entry is None:
        return
    client, close = entry
    if close is None:
        return
    try:
        await close(client)
    except Exception as e:
        logger.warning(f"Error closing cached {type(client).__name__}: {e}")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value
