"""Proxy service for managing ngrok tunnel lifecycle."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

from loguru import logger

from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.shared.lifecycle import LifecycleService
from syft_space.config import app_settings

# Type alias: async callback that returns (auth_token, domain)
CredentialsProvider = Callable[[], Awaitable[tuple[str, str]]]


class ProxyService(LifecycleService):
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
        self._current_domain: str | None = None
        self._shutdown_event: asyncio.Event | None = None  # Initialized in startup()
        self._reconnect_task: asyncio.Task | None = None
        self._ready_event: asyncio.Event | None = None  # Set by main.py
        self._credentials_provider: CredentialsProvider | None = None
        self._creds_refreshed: bool = False

    def is_connected(self) -> bool:
        """Check if the tunnel is currently connected."""
        return self._listener is not None

    def set_ready_event(self, event: asyncio.Event) -> None:
        """Set the event to signal when startup is complete.

        Args:
            event: Event to set when proxy startup finishes (success or failure)
        """
        self._ready_event = event

    def set_credentials_provider(self, provider: CredentialsProvider) -> None:
        """Set an async callback to fetch fresh tunnel credentials.

        Used as a fallback when stored credentials fail on startup.

        Args:
            provider: Async callable returning (auth_token, domain)
        """
        self._credentials_provider = provider

    def get_public_url(self) -> str | None:
        """Get the current public URL if connected."""
        if self._listener is not None:
            return self._listener.url()
        return None

    def log_connection_info(self) -> None:
        """Log connection info."""

        admin_api_key = app_settings.admin_api_key or ""

        if not self.is_connected():
            return

        public_url = self.get_public_url()
        public_url_str = (
            f"{public_url.rstrip('/')}/frontend/#/?authToken={admin_api_key}"
            if admin_api_key and public_url
            else str(public_url)
        )
        local_url_str = (
            f"http://localhost:{self._port}/frontend/#/?authToken={admin_api_key}"
            if admin_api_key
            else f"http://localhost:{self._port}"
        )
        print()
        print("=" * 70)
        print("  Ngrok tunnel established!")
        print()
        print(f"  Public URL: {public_url_str}")
        print(f"  Local URL:  {local_url_str}")
        print()
        print("=" * 70)
        print()

    async def _connect(self, token: str, domain: str, persist: bool = True) -> str:
        """Connect to ngrok with explicit credentials.

        Args:
            token: Ngrok authentication token
            domain: Ngrok tunnel domain
            persist: Whether to save the token to database (default: True)

        Returns:
            The public URL of the tunnel

        Raises:
            Exception: If connection fails (invalid token, network issues, etc.)
        """
        import ngrok

        # Ensure shutdown event exists (connect can be called before startup)
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()

        # Clear current token FIRST to prevent reconnect loop from using old token
        self._current_token = None

        # Disconnect existing connection if any
        await self._close_listener()

        # Stop any existing reconnect task
        await self._stop_reconnect_task()

        # Set auth token and create tunnel
        ngrok.set_auth_token(token)
        self._listener = await ngrok.forward(self._port, domain=domain)
        self._current_token = token  # Set new token AFTER successful connection
        self._current_domain = domain  # Track domain for reconnection
        public_url = self._listener.url()

        logger.info(f"Ngrok tunnel established: {public_url}")

        # Persist token, domain, and public URL to database
        if persist:
            await self._settings_repository.update_ngrok_token(token)
            await self._settings_repository.update_ngrok_domain(domain)
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
        self._current_domain = None

        # Clear from database
        if clear_token:
            await self._settings_repository.update_ngrok_token(None)
            await self._settings_repository.update_ngrok_domain(None)
            await self._settings_repository.update_public_url(None)

        logger.info("Ngrok tunnel disconnected")

    async def connect(self) -> str:
        """Connect to ngrok tunnel.

        Tries stored token + domain from DB first. If they're missing or fail,
        fetches fresh credentials via the credentials provider.

        Returns:
            The public URL of the tunnel

        Raises:
            RuntimeError: If no credentials are available (nothing stored, no provider)
            Exception: If connection fails with both stored and fresh credentials
        """
        token = await self._settings_repository.get_ngrok_token()
        domain = await self._settings_repository.get_ngrok_domain()

        # Try stored credentials if both are present
        if token and domain:
            try:
                public_url = await self._connect(token, domain, persist=False)
                await self._settings_repository.update_public_url(public_url)
                logger.info(f"Ngrok tunnel connected with stored credentials: {public_url}")
                return public_url
            except Exception as e:
                logger.warning(f"Stored credentials failed: {e}")

        # Fall back to credentials provider
        if self._credentials_provider is None:
            raise RuntimeError(
                "No stored credentials and no credentials provider configured"
            )

        logger.info("Fetching fresh tunnel credentials from SyftHub...")
        fresh_token, fresh_domain = await self._credentials_provider()
        public_url = await self._connect(fresh_token, fresh_domain, persist=True)
        logger.info(f"Ngrok tunnel connected with fresh credentials: {public_url}")
        return public_url

    async def _auto_connect_background(self) -> None:
        """Background task to auto-connect and signal completion."""

        try:
            token = await self._settings_repository.get_ngrok_token()
            if not token:
                logger.info("No stored ngrok token, skipping auto-connect")
                return
            await self.connect()
            self.log_connection_info()
        except Exception as e:
            logger.warning(f"Auto-connect failed: {e}")
        finally:
            # Always signal completion (success or failure)
            if self._ready_event:
                self._ready_event.set()

    async def startup(self) -> None:
        """Start the proxy service.

        Implements LifecycleService protocol. Runs auto_connect_if_configured
        in a background task to avoid blocking server startup.
        """
        # Initialize async primitives in async context (not in __init__)
        self._shutdown_event = asyncio.Event()
        # Fire-and-forget: don't block API startup on ngrok connection
        asyncio.create_task(self._auto_connect_background())

    async def shutdown(self) -> None:
        """Gracefully shutdown the proxy service.

        Called during application shutdown.
        """
        logger.info("Shutting down proxy service...")
        if self._shutdown_event:
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

        if self._shutdown_event:
            self._shutdown_event.clear()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _stop_reconnect_task(self) -> None:
        """Stop the reconnection monitor task."""
        if self._reconnect_task is not None:
            if self._shutdown_event:
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
        """Background task that monitors connection and reconnects if needed.

        Self-healing: on the first reconnect failure, if a credentials provider
        is configured and fresh creds haven't been fetched yet this cycle,
        fetch new credentials from SyftHub and retry immediately.
        """
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
                    self._creds_refreshed = False  # Allow refresh on next cycle
                    logger.info("Ngrok tunnel reconnected successfully")
                except Exception as e:
                    logger.warning(f"Reconnection failed: {e}")

                    # Self-healing: fetch fresh creds once per disconnect cycle
                    if (
                        not self._creds_refreshed
                        and self._credentials_provider is not None
                    ):
                        logger.info(
                            "Fetching fresh tunnel credentials from SyftHub..."
                        )
                        try:
                            fresh_token, fresh_domain = (
                                await self._credentials_provider()
                            )
                            self._current_token = fresh_token
                            self._current_domain = fresh_domain
                            self._creds_refreshed = True
                            # Persist fresh creds
                            await self._settings_repository.update_ngrok_token(
                                fresh_token
                            )
                            await self._settings_repository.update_ngrok_domain(
                                fresh_domain
                            )
                            # Retry immediately with fresh creds
                            try:
                                await self._reconnect()
                                delay = self.RECONNECT_INITIAL_DELAY
                                self._creds_refreshed = False
                                logger.info(
                                    "Reconnected with fresh credentials"
                                )
                                continue
                            except Exception as e2:
                                logger.warning(
                                    f"Reconnect with fresh credentials also failed: {e2}"
                                )
                        except Exception as e3:
                            logger.warning(
                                f"Failed to fetch fresh credentials: {e3}"
                            )
                            self._creds_refreshed = True  # Don't retry fetch

                    # Exponential backoff
                    delay = min(
                        delay * self.RECONNECT_BACKOFF_FACTOR, self.RECONNECT_MAX_DELAY
                    )
                    logger.info(f"Will retry in {delay} seconds...")

    async def _reconnect(self) -> None:
        """Attempt to reconnect with the stored token and domain."""
        if not self._current_token:
            raise ValueError("No token available for reconnection")
        if not self._current_domain:
            raise ValueError("No domain available for reconnection")

        import ngrok

        ngrok.set_auth_token(self._current_token)
        self._listener = await ngrok.forward(self._port, domain=self._current_domain)
        public_url = self._listener.url()

        # Update public URL in database (it may have changed)
        await self._settings_repository.update_public_url(public_url)

    async def _close_listener(self) -> None:
        """Close the current listener if it exists."""
        if self._listener is not None:
            import ngrok

            try:
                url = self._listener.url()
                await self._listener.close()
                # Fully disconnect from ngrok service to clear session state
                if url:
                    ngrok.disconnect(url)
            except Exception as e:
                logger.warning(f"Error closing ngrok listener: {e}")
            finally:
                self._listener = None
