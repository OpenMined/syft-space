"""Provisioner for an externally managed ChromaDB server.

Used when ``SYFT_CHROMADB_PROVISION=false``: there is no process to
manage — ``start`` ensures this space's database exists and health maps
to the server's heartbeat. A database is a Chroma v2 namespace; one per
space keeps collection names from colliding on a shared server.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from syft_space.components.vector_stores.interfaces import BaseVectorStoreProvisioner
from syft_space.config import app_settings

_HEARTBEAT_TIMEOUT_SECONDS = 5.0


def _server_url() -> str:
    scheme = "https" if app_settings.chromadb_ssl else "http"
    return f"{scheme}://{app_settings.chromadb_host}:{app_settings.chromadb_http_port}"


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


async def _heartbeat() -> bool:
    """Whether the configured ChromaDB server answers its heartbeat."""
    try:
        async with httpx.AsyncClient(timeout=_HEARTBEAT_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{_server_url()}/api/v2/heartbeat")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _ensure_database() -> None:
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


class ExternalChromaDBProvisioner(BaseVectorStoreProvisioner):
    """Provisioner for an externally managed ChromaDB server.

    The server's lifecycle is not ours: ``start`` only ensures the
    space's database exists, ``stop`` is a no-op, and running/status
    reflect the server's heartbeat. Failures surface where the
    provisioner is driven (dataset create/start), not at boot.
    """

    NAME = "chromadb_external"

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        return cls.NAME

    @classmethod
    async def start(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Ensure the space's database exists on the configured server.

        Args:
            config: Dataset connection config (unused — connection comes
                from ``SYFT_CHROMADB_*`` settings).

        Returns:
            State dict identifying the server and database.

        Raises:
            RuntimeError: If the server is unreachable or the database
                cannot be created.
        """
        try:
            await _ensure_database()
        except Exception as e:
            raise RuntimeError(f"ChromaDB at {_server_url()} unavailable: {e}") from e

        return {
            "host": app_settings.chromadb_host,
            "httpPort": app_settings.chromadb_http_port,
            "database": app_settings.chromadb_database,
        }

    @classmethod
    async def stop(cls, state: dict[str, Any]) -> None:
        """No-op — the server is managed externally."""

    @classmethod
    async def is_running(cls, state: dict[str, Any]) -> bool:
        """Whether the server answers its heartbeat."""
        return await _heartbeat()

    @classmethod
    async def status(cls, state: dict[str, Any]) -> str:
        """``running`` if the server answers its heartbeat, else ``stopped``."""
        return "running" if await _heartbeat() else "stopped"

    @classmethod
    async def wait_until_ready(cls, state: dict[str, Any]) -> None:
        """Check the server is reachable.

        Raises:
            TimeoutError: If the server does not answer its heartbeat.
        """
        if not await _heartbeat():
            raise TimeoutError(f"ChromaDB at {_server_url()} not reachable")
