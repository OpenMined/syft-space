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
# Values that live and die with a client: (client key, name) -> value.
_attached: dict[tuple[tuple, str], Any] = {}


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


async def attached(
    namespace: str, key: tuple, name: str, load: Callable[[], Awaitable[Any]]
) -> Any:
    """A value memoised under a client's key and ``name``, loaded once.

    Dropped by the ``evict`` of that client, so anything derived from a
    connection (a remote collection's schema) needs no eviction of its own.
    """
    full_key = (namespace, *key)
    if (full_key, name) in _attached:
        return _attached[(full_key, name)]
    async with _locks.setdefault(full_key, asyncio.Lock()):
        if (full_key, name) not in _attached:
            _attached[(full_key, name)] = await load()
        return _attached[(full_key, name)]


async def evict(namespace: str, key: tuple) -> None:
    """Close and drop one client, and what is attached to it, so the next
    ``get_client`` reconnects."""
    await _evict((namespace, *key))


async def close_all() -> None:
    for full_key in list(_clients):
        await _evict(full_key)
    _attached.clear()


def key_from(config: BaseModel, fields: list[str]) -> tuple:
    """Cache key: the named config fields (alias names), frozen to hash.

    Python mode, not JSON: a JSON dump masks every ``SecretStr`` as
    asterisks, which would make differently-keyed hosts collide.
    ``SecretStr`` and ``HttpUrl`` hash and compare on their real values.
    """
    dump = config.model_dump(by_alias=True, mode="python")
    return tuple(_freeze(dump.get(f)) for f in fields)


async def _evict(full_key: tuple) -> None:
    entry = _clients.pop(full_key, None)
    _locks.pop(full_key, None)
    for k in [k for k in _attached if k[0] == full_key]:
        del _attached[k]
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
