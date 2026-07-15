"""Startup bootstrap for an externally managed ChromaDB server.

Used when ``SYFT_CHROMADB_PROVISION=false``: verifies the configured
server is reachable and creates this space's database if missing.
A database is a Chroma v2 namespace — one per space keeps collection
names from colliding on a shared server.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from syft_space.config import app_settings

_ENSURE_TIMEOUT_SECONDS = 60.0
_RETRY_INTERVAL_SECONDS = 2.0


def _build_admin_client():
    """Build an async admin client for the configured ChromaDB server."""
    try:
        from chromadb.api.async_client import AsyncAdminClient
        from chromadb.config import Settings
    except ImportError as e:
        raise ImportError(
            "chromadb required when SYFT_CHROMADB_PROVISION is false"
        ) from e

    return AsyncAdminClient(
        Settings(
            chroma_api_impl="chromadb.api.async_fastapi.AsyncFastAPI",
            chroma_server_host=app_settings.chromadb_host,
            chroma_server_http_port=app_settings.chromadb_http_port,
            chroma_server_ssl_enabled=app_settings.chromadb_ssl,
        )
    )


async def _ensure_database_once() -> None:
    """Create this space's database if missing."""
    admin = _build_admin_client()
    database = app_settings.chromadb_database

    try:
        await admin.get_database(database)
        logger.info(f"ChromaDB database '{database}' exists")
        return
    except Exception as e:
        # Missing database and unreachable server both land here;
        # create() below tells them apart.
        logger.debug(f"ChromaDB database '{database}' lookup failed: {e}")

    try:
        await admin.create_database(database)
        logger.info(f"Created ChromaDB database '{database}'")
    except Exception as e:
        # Lost a create race with another instance — same outcome.
        message = str(e).lower()
        if "already exists" in message or "409" in message:
            logger.info(f"ChromaDB database '{database}' already exists")
            return
        raise


async def ensure_external_database() -> None:
    """Ensure the ChromaDB server is reachable and our database exists.

    Retries while the server comes up, then fails fast — the space must
    not serve traffic without its vector database.

    Raises:
        RuntimeError: If the database can't be ensured within the timeout.
    """
    target = (
        f"{app_settings.chromadb_host}:{app_settings.chromadb_http_port}"
        f"/{app_settings.chromadb_database}"
    )
    deadline = asyncio.get_running_loop().time() + _ENSURE_TIMEOUT_SECONDS
    last_error: Exception | None = None

    while asyncio.get_running_loop().time() < deadline:
        try:
            await _ensure_database_once()
            return
        except Exception as e:
            last_error = e
            logger.warning(f"ChromaDB ensure-database at {target} failed: {e}")
            await asyncio.sleep(_RETRY_INTERVAL_SECONDS)

    raise RuntimeError(
        f"ChromaDB at {target} unavailable after "
        f"{_ENSURE_TIMEOUT_SECONDS:.0f}s: {last_error}"
    )
