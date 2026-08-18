"""Tests for endpoint heartbeat transport backoff, especially 429 handling.

Rate-limited deliveries (429) must back off immediately instead of
retrying every cycle; other transport failures keep the grace period of
TRANSPORT_MAX_FAILURES fast retries.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from syft_space.components.endpoints import endpoint_heartbeat_manager as hb_module
from syft_space.components.endpoints.endpoint_heartbeat_manager import (
    EndpointHeartbeatManager,
    MarketplaceDeliveryState,
)
from syft_space.components.shared.syfthub_client import RateLimitError

NOW = 1000.0


def make_manager() -> EndpointHeartbeatManager:
    return EndpointHeartbeatManager(
        health_checker=SimpleNamespace(),
        marketplace_repository=SimpleNamespace(),
        settings_repository=SimpleNamespace(),
    )


def make_state() -> MarketplaceDeliveryState:
    return MarketplaceDeliveryState(marketplace_id=uuid4())


def test_first_rate_limit_backs_off_immediately():
    manager = make_manager()
    state = make_state()

    manager._handle_transport_failure(state, NOW, immediate=True)

    assert state.consecutive_failures == 1
    assert state.next_delivery_at == NOW + manager.CHECK_INTERVAL


def test_consecutive_rate_limits_escalate_and_cap():
    manager = make_manager()
    state = make_state()

    backoffs = []
    for _ in range(6):
        manager._handle_transport_failure(state, NOW, immediate=True)
        backoffs.append(state.next_delivery_at - NOW)

    assert backoffs == [30.0, 60.0, 120.0, 240.0, 300.0, 300.0]


def test_transient_failures_keep_grace_period():
    manager = make_manager()
    state = make_state()

    for _ in range(manager.TRANSPORT_MAX_FAILURES - 1):
        manager._handle_transport_failure(state, NOW)
    assert state.next_delivery_at == 0.0  # still retrying every cycle

    manager._handle_transport_failure(state, NOW)
    assert state.next_delivery_at == NOW + manager.CHECK_INTERVAL


def test_rate_limit_after_transient_failures_escalates_from_streak():
    manager = make_manager()
    state = make_state()

    manager._handle_transport_failure(state, NOW)  # transient, no backoff
    manager._handle_transport_failure(state, NOW, immediate=True)

    assert state.consecutive_failures == 2
    assert state.next_delivery_at == NOW + 2 * manager.CHECK_INTERVAL


class _RateLimitedClient:
    """SyftHubClient stand-in whose login is always rate limited."""

    instantiations = 0

    def __init__(self, *args, **kwargs):
        type(self).instantiations += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def login(self, *args, **kwargs):
        raise RateLimitError("Too many requests", status_code=429)


def make_marketplace() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name="Test Hub",
        url="https://hub.test",
        email="space@test.org",
        password="pw",
    )


async def test_rate_limited_delivery_backs_off_and_skips_next_attempt(monkeypatch):
    monkeypatch.setattr(hb_module, "SyftHubClient", _RateLimitedClient)
    _RateLimitedClient.instantiations = 0

    manager = make_manager()
    marketplace = make_marketplace()
    health = [{"slug": "ep", "status": "online", "checked_at": "now"}]

    await manager._send_endpoint_heartbeat_to_marketplace(
        marketplace, "https://space.test", health
    )

    state = manager._states[marketplace.id]
    assert state.consecutive_failures == 1
    assert state.next_delivery_at > 0
    assert _RateLimitedClient.instantiations == 1

    # Second cycle arrives while still in backoff: no request is attempted
    await manager._send_endpoint_heartbeat_to_marketplace(
        marketplace, "https://space.test", health
    )
    assert _RateLimitedClient.instantiations == 1
    assert state.consecutive_failures == 1
