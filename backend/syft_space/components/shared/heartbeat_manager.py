"""Heartbeat manager for sending periodic heartbeats to SyftHub marketplaces."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.shared.lifecycle import LifecycleService
from syft_space.components.shared.syfthub_client import SyftHubClient, SyftHubError

if TYPE_CHECKING:
    from syft_space.components.marketplaces.repository import MarketplaceRepository
    from syft_space.components.settings.repository import SettingsRepository


@dataclass
class HeartbeatState:
    """Tracks heartbeat state for a single marketplace."""

    marketplace_id: UUID
    current_interval: float = field(default=15.0)
    consecutive_successes: int = field(default=0)
    consecutive_failures: int = field(default=0)


class HeartbeatManager(LifecycleService):
    """Manages periodic heartbeats to SyftHub marketplaces with adaptive backoff.

    Features:
    - Exponential backoff: Starts frequent, increases interval on success
    - Jitter: 10-15% randomness to prevent thundering herd
    - Failure recovery: Resets to aggressive (small) interval on failure
    - Failure backoff: After repeated failures, backs off instead of aggressive retry
    - Multi-marketplace support: Sends heartbeats to all active marketplaces
    - TTL > interval: TTL is 3x the interval to tolerate missed heartbeats
    """

    # Timing configuration (in seconds)
    INITIAL_INTERVAL = 15.0  # Start with 15 second heartbeats
    MAX_INTERVAL = 600.0  # Cap at 10 minutes
    BACKOFF_FACTOR = 2.0  # Double interval on each success
    TTL_MULTIPLIER = 3.0  # TTL = interval * 3 (tolerance for missed heartbeats)
    JITTER_MIN = 0.10  # 10% minimum jitter
    JITTER_MAX = 0.15  # 15% maximum jitter
    POLL_INTERVAL = 5.0  # Poll for public_url every 5 seconds
    MAX_CONSECUTIVE_FAILURES = 10  # After this many failures, start backing off

    def __init__(
        self,
        marketplace_repository: MarketplaceRepository,
        settings_repository: SettingsRepository,
        enabled: bool = True,
    ) -> None:
        """Initialize the heartbeat manager.

        Args:
            marketplace_repository: Repository for accessing marketplace credentials
            settings_repository: Repository for accessing public_url setting
            enabled: Whether heartbeat manager is enabled
        """
        self._marketplace_repository = marketplace_repository
        self._settings_repository = settings_repository
        self._enabled = enabled

        # Per-marketplace state tracking
        self._states: dict[UUID, HeartbeatState] = {}

        # Track if we had a public URL (for detecting removal)
        self._had_public_url = False

        # Async primitives - initialized in startup()
        self._shutdown_event: asyncio.Event | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._tenant_id: UUID | None = None

    def set_tenant_id(self, tenant_id: UUID) -> None:
        """Set the tenant ID for marketplace queries.

        Args:
            tenant_id: Default tenant ID
        """
        self._tenant_id = tenant_id

    async def startup(self) -> None:
        """Start the heartbeat manager."""
        if not self._enabled:
            logger.info("Heartbeat manager is disabled")
            return

        # Check if heartbeat manager is already running
        # Just a safety check to prevent multiple startup calls
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            logger.warning("Heartbeat manager already running, skipping startup")
            return

        logger.info("Starting heartbeat manager...")

        # Initialize async primitives
        self._shutdown_event = asyncio.Event()

        # Start background heartbeat loop
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name="HeartbeatManager"
        )

        logger.info("Heartbeat manager started")

    async def shutdown(self) -> None:
        """Shutdown the heartbeat manager gracefully."""
        if not self._enabled:
            return

        logger.info("Shutting down heartbeat manager...")

        if self._shutdown_event:
            self._shutdown_event.set()

        if self._heartbeat_task and not self._heartbeat_task.done():
            try:
                await asyncio.wait_for(self._heartbeat_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass

        self._states.clear()
        logger.info("Heartbeat manager shutdown complete")

    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop - waits for public_url, then sends heartbeats."""
        logger.info("Heartbeat loop started, waiting for public_url to be set...")

        # Wait for public_url to be set before starting heartbeats
        if not await self._wait_for_public_url():
            logger.info("Heartbeat loop stopped (shutdown during public_url wait)")
            return

        logger.info("Public URL available, beginning heartbeat cycle")
        self._had_public_url = True

        while not self._shutdown_event.is_set():
            try:
                # Send heartbeats to all marketplaces
                await self._send_heartbeats_to_all()

                # Calculate sleep time (minimum interval across all marketplaces)
                sleep_time = self._get_minimum_interval()

                # Wait for sleep_time or shutdown signal
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=sleep_time
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Time to send next heartbeat

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Unexpected error in heartbeat loop: {e}")
                # Wait before retrying
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=self.INITIAL_INTERVAL
                    )
                    break
                except asyncio.TimeoutError:
                    pass

        logger.info("Heartbeat loop stopped")

    async def _wait_for_public_url(self) -> bool:
        """Wait for public_url to be set in settings.

        Works whether URL is set by proxy or manually by user.

        Returns:
            True if public_url is available, False if shutdown was requested
        """
        while not self._shutdown_event.is_set():
            public_url = await self._settings_repository.get_public_url()
            if public_url:
                return True

            # Poll every POLL_INTERVAL seconds
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=self.POLL_INTERVAL
                )
                return False  # Shutdown requested
            except asyncio.TimeoutError:
                pass  # Continue polling

        return False

    def _get_minimum_interval(self) -> float:
        """Get the minimum interval across all active marketplace states.

        Returns:
            Minimum interval in seconds, or INITIAL_INTERVAL if no states exist
        """
        if not self._states:
            return self.INITIAL_INTERVAL
        return min(state.current_interval for state in self._states.values())

    async def _send_heartbeats_to_all(self) -> None:
        """Send heartbeats to all active marketplaces concurrently."""
        if not self._tenant_id:
            logger.warning("Tenant ID not set, skipping heartbeat")
            return

        # Get public URL from settings
        public_url = await self._settings_repository.get_public_url()
        if not public_url:
            # URL was removed - reset all states
            if self._had_public_url and self._states:
                logger.info("Public URL removed, resetting heartbeat intervals")
                for state in self._states.values():
                    state.current_interval = self.INITIAL_INTERVAL
                    state.consecutive_successes = 0
            self._had_public_url = False
            return

        self._had_public_url = True

        # Get all active marketplaces
        marketplaces = await self._marketplace_repository.get_active(self._tenant_id)
        if not marketplaces:
            logger.debug("No active marketplaces, skipping heartbeat")
            return

        # Prune stale marketplace states (for removed marketplaces)
        active_ids = {m.id for m in marketplaces}
        stale_ids = set(self._states.keys()) - active_ids
        for stale_id in stale_ids:
            del self._states[stale_id]
            logger.debug(f"Pruned stale heartbeat state for marketplace {stale_id}")

        # Send heartbeats concurrently
        tasks = [
            self._send_heartbeat_to_marketplace(marketplace, public_url)
            for marketplace in marketplaces
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_heartbeat_to_marketplace(
        self,
        marketplace: Marketplace,
        public_url: str,
    ) -> None:
        """Send heartbeat to a single marketplace.

        Args:
            marketplace: Marketplace entity with credentials
            public_url: Public URL to send in heartbeat
        """
        # Validate credentials
        if not marketplace.email or not marketplace.password:
            logger.debug(
                f"Marketplace {marketplace.name} missing credentials, "
                "skipping heartbeat"
            )
            return

        state = self._get_or_create_state(marketplace.id)
        ttl = self._calculate_ttl(state.current_interval)

        try:
            async with SyftHubClient(base_url=marketplace.url) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                await client.send_heartbeat(public_url, ttl)

                self._update_state_on_success(state)
                logger.info(
                    f"Heartbeat sent to {marketplace.name}: "
                    f"ttl={ttl}s, next_interval={state.current_interval:.1f}s, "
                    f"successes={state.consecutive_successes}"
                )

        except SyftHubError as e:
            self._update_state_on_failure(state)
            logger.warning(
                f"Heartbeat to {marketplace.name} failed: {e.message} "
                f"(failures={state.consecutive_failures}, "
                f"next_interval={state.current_interval:.1f}s)"
            )
        except Exception as e:
            self._update_state_on_failure(state)
            logger.exception(
                f"Unexpected error sending heartbeat to {marketplace.name}: {e}"
            )

    def _get_or_create_state(self, marketplace_id: UUID) -> HeartbeatState:
        """Get or create heartbeat state for a marketplace.

        Args:
            marketplace_id: Marketplace UUID

        Returns:
            HeartbeatState for the marketplace
        """
        if marketplace_id not in self._states:
            self._states[marketplace_id] = HeartbeatState(
                marketplace_id=marketplace_id,
                current_interval=self.INITIAL_INTERVAL,
            )
        return self._states[marketplace_id]

    def _update_state_on_success(self, state: HeartbeatState) -> None:
        """Update state after successful heartbeat.

        Args:
            state: HeartbeatState to update
        """
        state.consecutive_successes += 1
        state.consecutive_failures = 0
        state.current_interval = self._calculate_next_interval(state, success=True)

    def _update_state_on_failure(self, state: HeartbeatState) -> None:
        """Update state after failed heartbeat.

        Args:
            state: HeartbeatState to update
        """
        state.consecutive_failures += 1
        state.consecutive_successes = 0
        state.current_interval = self._calculate_next_interval(state, success=False)

    def _calculate_next_interval(self, state: HeartbeatState, success: bool) -> float:
        """Calculate the next heartbeat interval based on success/failure.

        Algorithm:
        - On success: Double the interval (up to MAX_INTERVAL)
        - On failure (< MAX_CONSECUTIVE_FAILURES): Reset to INITIAL_INTERVAL
        - On failure (>= MAX_CONSECUTIVE_FAILURES): Back off exponentially
        - Add jitter (10-15%) to prevent thundering herd

        Args:
            state: Current heartbeat state for the marketplace
            success: Whether the last heartbeat succeeded

        Returns:
            Next interval in seconds (with jitter applied)
        """
        if success:
            # Exponential backoff on success (slow down)
            new_interval = min(
                state.current_interval * self.BACKOFF_FACTOR, self.MAX_INTERVAL
            )
        else:
            # After many consecutive failures, back off instead of aggressive retry
            if state.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                new_interval = min(
                    state.current_interval * self.BACKOFF_FACTOR, self.MAX_INTERVAL
                )
            else:
                # Reset to aggressive retry on failure
                new_interval = self.INITIAL_INTERVAL

        # Apply jitter (10-15% randomness)
        jitter_factor = 1.0 + secrets.SystemRandom().uniform(
            self.JITTER_MIN, self.JITTER_MAX
        )
        return new_interval * jitter_factor

    def _calculate_ttl(self, interval: float) -> int:
        """Calculate TTL based on heartbeat interval.

        TTL should be larger than interval to tolerate:
        - Network delays
        - Occasional missed heartbeats
        - Clock skew

        Args:
            interval: Current heartbeat interval in seconds

        Returns:
            TTL in seconds (integer, as required by API)
        """
        return int(interval * self.TTL_MULTIPLIER)
