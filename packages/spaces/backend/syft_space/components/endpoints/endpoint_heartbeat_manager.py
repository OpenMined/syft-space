"""Endpoint heartbeat manager for sending periodic endpoint health to SyftHub marketplaces."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

from loguru import logger

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.satellites import SatelliteRegistrar
from syft_space.components.shared.lifecycle import LifecycleService
from syft_space.components.shared.syfthub_client import (
    NotFoundError,
    RateLimitError,
    SyftHubClient,
    SyftHubError,
)

if TYPE_CHECKING:
    from syft_space.components.marketplaces.repository import MarketplaceRepository
    from syft_space.components.settings.repository import SettingsRepository
    from syft_space.components.tenants.entities import Tenant


@runtime_checkable
class EndpointHealthChecker(Protocol):
    """Interface for checking published endpoint health.

    Satisfied structurally by EndpointHandler — no import needed.
    """

    async def get_published_endpoint_health(
        self, tenant: Tenant, health_timeout: float = ...
    ) -> list[dict[str, Any]]: ...


@dataclass
class MarketplaceDeliveryState:
    """Tracks transport delivery state for a single marketplace."""

    marketplace_id: UUID
    consecutive_failures: int = field(default=0)
    next_delivery_at: float = field(default=0.0)


class EndpointHeartbeatManager(LifecycleService):
    """Manages periodic endpoint health reporting to SyftHub marketplaces.

    Checks every published endpoint on a fixed interval, so detection latency
    for a health change is bounded by it. Transport failures back off per
    marketplace — health checks themselves continue unaffected.
    """

    CHECK_INTERVAL = 30.0
    JITTER_MAX = 5.0  # Random extra sleep so co-located instances desynchronize
    # TTL must clear one whole cycle — interval + jitter + up to 10s of health
    # checks — or a healthy space reports late and looks stale. Blips are
    # absorbed by the hub needing 3 consecutive stale sweeps, not by this margin.
    TTL_MULTIPLIER = 2.0
    POLL_INTERVAL = 5.0  # While waiting for public_url to be set

    # Transport failure backoff (only when the SyftHub POST fails)
    TRANSPORT_BACKOFF_FACTOR = 2.0
    TRANSPORT_MAX_INTERVAL = 300.0
    TRANSPORT_MAX_FAILURES = 5  # Consecutive failures tolerated before backoff

    def __init__(
        self,
        health_checker: EndpointHealthChecker,
        marketplace_repository: MarketplaceRepository,
        settings_repository: SettingsRepository,
        enabled: bool = True,
        check_interval: float = CHECK_INTERVAL,
    ) -> None:
        """Initialize the endpoint heartbeat manager.

        Args:
            health_checker: Provider for endpoint health checks (e.g. EndpointHandler)
            marketplace_repository: Repository for accessing marketplace credentials
            settings_repository: Repository for accessing public_url setting
            enabled: Whether endpoint heartbeat manager is enabled
            check_interval: Interval in seconds between health checks
        """
        self._health_checker = health_checker
        self._marketplace_repository = marketplace_repository
        self._satellites = SatelliteRegistrar(marketplace_repository)
        self._settings_repository = settings_repository
        self._enabled = enabled
        self._check_interval = check_interval

        # Per-marketplace delivery state
        self._states: dict[UUID, MarketplaceDeliveryState] = {}

        # Track if we had a public URL (for detecting removal)
        self._had_public_url = False

        # Async primitives - initialized in startup()
        self._shutdown_event: asyncio.Event | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._tenant: Tenant | None = None
        self._tenant_id: UUID | None = None

    def set_tenant(self, tenant: Tenant) -> None:
        """Set the tenant for endpoint health queries.

        Args:
            tenant: Default tenant
        """
        self._tenant = tenant
        self._tenant_id = tenant.id

    async def startup(self) -> None:
        """Start the endpoint heartbeat manager."""
        if not self._enabled:
            logger.info("Endpoint heartbeat manager is disabled")
            return

        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            logger.warning(
                "Endpoint heartbeat manager already running, skipping startup"
            )
            return

        logger.info("Starting endpoint heartbeat manager...")

        self._shutdown_event = asyncio.Event()
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name="EndpointHeartbeatManager"
        )

        logger.info("Endpoint heartbeat manager started")

    async def shutdown(self) -> None:
        """Shutdown the endpoint heartbeat manager gracefully."""
        if not self._enabled:
            return

        logger.info("Shutting down endpoint heartbeat manager...")

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
        logger.info("Endpoint heartbeat manager shutdown complete")

    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop - waits for public_url, then sends endpoint health."""
        logger.info(
            "Endpoint heartbeat loop started, waiting for public_url to be set..."
        )

        if not await self._wait_for_public_url():
            logger.info(
                "Endpoint heartbeat loop stopped (shutdown during public_url wait)"
            )
            return

        logger.info("Public URL available, beginning endpoint heartbeat cycle")
        self._had_public_url = True

        while not self._shutdown_event.is_set():
            try:
                await self._send_endpoint_heartbeats_to_all()

                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=self._jittered_interval()
                    )
                    break
                except asyncio.TimeoutError:
                    pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Unexpected error in endpoint heartbeat loop: {e}")
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=self._jittered_interval()
                    )
                    break
                except asyncio.TimeoutError:
                    pass

        logger.info("Endpoint heartbeat loop stopped")

    def _jittered_interval(self) -> float:
        """Check interval plus random jitter.

        Co-located instances otherwise heartbeat in lockstep and hit the
        marketplace's rate limiter together.
        """
        return self._check_interval + random.uniform(0.0, self.JITTER_MAX)  # nosec B311

    async def _wait_for_public_url(self) -> bool:
        """Wait for public_url to be set in settings.

        Returns:
            True if public_url is available, False if shutdown was requested
        """
        while not self._shutdown_event.is_set():
            public_url = await self._settings_repository.get_public_url()
            if public_url:
                return True

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=self.POLL_INTERVAL
                )
                return False
            except asyncio.TimeoutError:
                pass

        return False

    async def _send_endpoint_heartbeats_to_all(self) -> None:
        """Send endpoint health to all active marketplaces concurrently."""
        if not self._tenant:
            logger.warning("Tenant not set, skipping endpoint heartbeat")
            return

        public_url = await self._settings_repository.get_public_url()
        if not public_url:
            if self._had_public_url and self._states:
                logger.info("Public URL removed, resetting endpoint heartbeat state")
                self._states.clear()
            self._had_public_url = False
            return

        self._had_public_url = True

        marketplaces = await self._marketplace_repository.get_active(self._tenant_id)
        if not marketplaces:
            logger.debug("No active marketplaces, skipping endpoint heartbeat")
            return

        # Prune stale marketplace states
        active_ids = {m.id for m in marketplaces}
        stale_ids = set(self._states.keys()) - active_ids
        for stale_id in stale_ids:
            del self._states[stale_id]
            logger.debug(f"Pruned stale delivery state for marketplace {stale_id}")

        # Check health of all published endpoints (once, shared across marketplaces)
        endpoint_health = await self._health_checker.get_published_endpoint_health(
            self._tenant
        )
        if not endpoint_health:
            logger.debug("No published endpoints, skipping endpoint heartbeat")
            return

        # Send to each marketplace concurrently
        tasks = [
            self._send_endpoint_heartbeat_to_marketplace(
                marketplace, public_url, endpoint_health, self._tenant.id
            )
            for marketplace in marketplaces
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_endpoint_heartbeat_to_marketplace(
        self,
        marketplace: Marketplace,
        public_url: str,
        endpoint_health: list[dict[str, Any]],
        tenant_id: UUID,
    ) -> None:
        """Send endpoint health to a single marketplace.

        Skips delivery if the marketplace is in transport backoff.

        Args:
            marketplace: Marketplace entity with credentials
            public_url: Domain's public URL
            endpoint_health: List of endpoint health statuses
            tenant_id: Tenant owning this marketplace
        """
        if not marketplace.email or not marketplace.password:
            logger.debug(
                f"Marketplace {marketplace.name} missing credentials, "
                "skipping endpoint heartbeat"
            )
            return

        state = self._get_or_create_state(marketplace.id)

        # Skip if in transport backoff
        now = asyncio.get_running_loop().time()
        if now < state.next_delivery_at:
            logger.debug(
                f"Marketplace {marketplace.name} in transport backoff, "
                f"skipping delivery (retry in {state.next_delivery_at - now:.0f}s)"
            )
            return

        ttl = int(self._check_interval * self.TTL_MULTIPLIER)

        try:
            async with SyftHubClient(base_url=marketplace.url) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                satellite_id = await self._satellites.resolve_id(
                    client, marketplace, public_url, tenant_id
                )
                if satellite_id is None:
                    # Unreachable: the loop waits for public_url first.
                    logger.warning(
                        f"Marketplace {marketplace.name} has no satellite, "
                        "skipping endpoint heartbeat"
                    )
                    return
                await client.update_endpoint_health(
                    endpoint_health=endpoint_health,
                    ttl_seconds=ttl,
                    public_url=public_url,
                    satellite_id=satellite_id,
                )

                state.consecutive_failures = 0
                state.next_delivery_at = 0.0
                logger.info(
                    f"Endpoint heartbeat sent to {marketplace.name}: "
                    f"{len(endpoint_health)} endpoints, ttl={ttl}s"
                )

        except RateLimitError as e:
            self._handle_transport_failure(state, now, immediate=True)
            logger.warning(
                f"Endpoint heartbeat to {marketplace.name} rate limited, "
                f"backing off {state.next_delivery_at - now:.0f}s: {e.message} "
                f"(failures={state.consecutive_failures})"
            )
        except NotFoundError as e:
            await self._satellites.forget_id(marketplace, tenant_id)
            self._handle_transport_failure(state, now)
            logger.warning(
                f"Endpoint heartbeat to {marketplace.name} hit an unknown "
                f"satellite: {e.message} (failures={state.consecutive_failures})"
            )
        except SyftHubError as e:
            self._handle_transport_failure(state, now)
            logger.warning(
                f"Endpoint heartbeat to {marketplace.name} failed: {e.message} "
                f"(failures={state.consecutive_failures})"
            )
        except Exception as e:
            self._handle_transport_failure(state, now)
            logger.exception(
                f"Unexpected error sending endpoint heartbeat to "
                f"{marketplace.name}: {e}"
            )

    def _get_or_create_state(self, marketplace_id: UUID) -> MarketplaceDeliveryState:
        """Get or create delivery state for a marketplace."""
        if marketplace_id not in self._states:
            self._states[marketplace_id] = MarketplaceDeliveryState(
                marketplace_id=marketplace_id,
            )
        return self._states[marketplace_id]

    def _handle_transport_failure(
        self, state: MarketplaceDeliveryState, now: float, immediate: bool = False
    ) -> None:
        """Handle a transport failure — backoff after repeated failures.

        First TRANSPORT_MAX_FAILURES attempts retry every CHECK_INTERVAL (no backoff).
        After that, exponential backoff up to TRANSPORT_MAX_INTERVAL.

        With immediate=True (rate limited: the server asked us to slow
        down), the grace period is skipped and backoff starts on the first
        failure, escalating with each consecutive one.
        """
        state.consecutive_failures += 1
        effective_failures = state.consecutive_failures
        if immediate:
            effective_failures += self.TRANSPORT_MAX_FAILURES - 1
        if effective_failures >= self.TRANSPORT_MAX_FAILURES:
            backoff = min(
                self._check_interval
                * (
                    self.TRANSPORT_BACKOFF_FACTOR
                    ** (effective_failures - self.TRANSPORT_MAX_FAILURES)
                ),
                self.TRANSPORT_MAX_INTERVAL,
            )
            state.next_delivery_at = now + backoff
