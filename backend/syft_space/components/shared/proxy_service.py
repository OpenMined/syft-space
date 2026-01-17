"""Proxy service for managing ngrok tunnel lifecycle."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from syft_space.components.settings.repository import SettingsRepository


class ProxyService:
    """Manages ngrok tunnel lifecycle with auto-reconnection.

    This service handles:
    - Creating and managing ngrok tunnel connections
    - Automatic reconnection on connection loss
    - Graceful shutdown
    - Token persistence via SettingsRepository
    """

    # Reconnection settings
    RECONNECT_INITIAL_DELAY = 5  # seconds
    RECONNECT_MAX_DELAY = 60  # seconds
    RECONNECT_BACKOFF_FACTOR = 2

    def __init__(
        self,
        settings_repository: SettingsRepository,
        port: int | None = None,
    ) -> None:
        """Initialize the proxy service.

        Args:
            settings_repository: Repository for persisting settings
            port: Port to forward traffic to (default: SYFT_PORT environment variable or 8080)
        """
        self._settings_repository = settings_repository
        self._port = port or int(os.getenv("SYFT_PORT", "8080"))
        self._listener = None
        self._current_token: str | None = None
        self._shutdown_event = asyncio.Event()
        self._reconnect_task: asyncio.Task | None = None

    def is_connected(self) -> bool:
        """Check if the tunnel is currently connected."""
        return self._listener is not None

    def get_public_url(self) -> str | None:
        """Get the current public URL if connected."""
        if self._listener is not None:
            return self._listener.url()
        return None

    def log_connection_info(self, admin_api_key: str | None = None) -> None:
        """Log connection info with optional auth token appended.

        Args:
            admin_api_key: Optional admin API key to append as auth token fragment
        """
        if not self.is_connected():
            return

        public_url = self.get_public_url()
        public_url_str = (
            f"{public_url}#authToken={admin_api_key}"
            if admin_api_key
            else str(public_url)
        )
        local_url_str = (
            f"http://localhost:{self._port}#authToken={admin_api_key}"
            if admin_api_key
            else f"http://localhost:{self._port}"
        )
        logger.info("\n" + "=" * 70)
        logger.info("🚀 Ngrok tunnel established!")
        logger.info(f"📡 Public URL: {public_url_str}")
        logger.info(f"🔗 Local URL: {local_url_str}")
        logger.info("=" * 70 + "\n")

    async def connect(self, token: str, persist: bool = True) -> str:
        """Connect to ngrok with the provided token.

        Args:
            token: Ngrok authentication token
            persist: Whether to save the token to database (default: True)

        Returns:
            The public URL of the tunnel

        Raises:
            Exception: If connection fails (invalid token, network issues, etc.)
        """
        import ngrok

        # Disconnect existing connection if any
        await self._close_listener()

        # Stop any existing reconnect task
        await self._stop_reconnect_task()

        # Set auth token and create tunnel
        ngrok.set_auth_token(token)
        self._listener = await ngrok.forward(self._port)
        self._current_token = token
        public_url = self._listener.url()

        logger.info(f"Ngrok tunnel established: {public_url}")

        # Persist token and public URL to database
        if persist:
            await self._settings_repository.update_ngrok_token(token)
            await self._settings_repository.update_public_url(public_url)

        # Start reconnection monitor
        self._start_reconnect_monitor()

        return public_url

    async def disconnect(self, clear_token: bool = True) -> None:
        """Disconnect the tunnel and optionally clear stored token.

        Args:
            clear_token: Whether to clear the stored token (default: True)
        """
        # Stop reconnect task first
        await self._stop_reconnect_task()

        # Close the listener
        await self._close_listener()
        self._current_token = None

        # Clear from database
        if clear_token:
            await self._settings_repository.update_ngrok_token(None)
            await self._settings_repository.update_public_url(None)

        logger.info("Ngrok tunnel disconnected")

    async def auto_connect_if_configured(self) -> None:
        """Automatically connect if a token is stored in the database.

        Called during application startup to restore tunnel connection.
        """
        token = await self._settings_repository.get_ngrok_token()
        if not token:
            logger.info("No ngrok token configured, skipping auto-connect")
            return

        try:
            # Connect but don't re-persist the token (it's already in DB)
            public_url = await self.connect(token, persist=False)
            # Update public URL in case it changed
            await self._settings_repository.update_public_url(public_url)
            logger.info(f"Ngrok tunnel auto-connected: {public_url}")
        except Exception as e:
            logger.error(f"Failed to auto-connect ngrok tunnel: {e}")
            # Don't clear the token on auto-connect failure
            # User can retry or reconfigure

    async def shutdown(self) -> None:
        """Gracefully shutdown the proxy service.

        Called during application shutdown.
        """
        logger.info("Shutting down proxy service...")
        self._shutdown_event.set()

        # Stop reconnect task
        await self._stop_reconnect_task()

        # Close listener
        await self._close_listener()

        logger.info("Proxy service shutdown complete")

    def _start_reconnect_monitor(self) -> None:
        """Start the background reconnection monitor task."""
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return  # Already running

        self._shutdown_event.clear()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _stop_reconnect_task(self) -> None:
        """Stop the reconnection monitor task."""
        if self._reconnect_task is not None:
            self._shutdown_event.set()
            try:
                # Wait for task to complete with timeout
                await asyncio.wait_for(self._reconnect_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._reconnect_task.cancel()
                try:
                    await self._reconnect_task
                except asyncio.CancelledError:
                    pass
            self._reconnect_task = None

    async def _reconnect_loop(self) -> None:
        """Background task that monitors connection and reconnects if needed."""
        delay = self.RECONNECT_INITIAL_DELAY

        while not self._shutdown_event.is_set():
            try:
                # Wait before checking (also allows shutdown to interrupt)
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=delay,
                )
                # If we get here, shutdown was requested
                break
            except asyncio.TimeoutError:
                # Timeout means we should check connection
                pass

            # Check if connection is still alive
            if self._listener is None and self._current_token:
                logger.warning("Ngrok tunnel disconnected, attempting to reconnect...")
                try:
                    await self._reconnect()
                    delay = self.RECONNECT_INITIAL_DELAY  # Reset delay on success
                    logger.info("Ngrok tunnel reconnected successfully")
                except Exception as e:
                    logger.error(f"Reconnection failed: {e}")
                    # Exponential backoff
                    delay = min(
                        delay * self.RECONNECT_BACKOFF_FACTOR, self.RECONNECT_MAX_DELAY
                    )
                    logger.info(f"Will retry in {delay} seconds...")

    async def _reconnect(self) -> None:
        """Attempt to reconnect with the stored token."""
        if not self._current_token:
            raise ValueError("No token available for reconnection")

        import ngrok

        ngrok.set_auth_token(self._current_token)
        self._listener = await ngrok.forward(self._port)
        public_url = self._listener.url()

        # Update public URL in database (it may have changed)
        await self._settings_repository.update_public_url(public_url)

    async def _close_listener(self) -> None:
        """Close the current listener if it exists."""
        if self._listener is not None:
            try:
                await self._listener.close()
            except Exception as e:
                logger.warning(f"Error closing ngrok listener: {e}")
            finally:
                self._listener = None
