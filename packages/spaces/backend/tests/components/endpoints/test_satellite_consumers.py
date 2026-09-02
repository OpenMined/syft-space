"""Tests for the satellite behaviour of the endpoint consumers.

Two of these pin *absences*, which no other test would catch: shutdown must
not touch the marketplace at all, and a slug this space never published must
not be overwritten just because publishing it returned a conflict.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import syft_space.components.endpoints.endpoint_heartbeat_manager as hb_module
import syft_space.components.endpoints.publish_handler as publish_module
from syft_space.components.endpoints.endpoint_heartbeat_manager import (
    EndpointHeartbeatManager,
)
from syft_space.components.endpoints.publish_handler import PublishEndpointHandler

SATELLITE_ID = str(uuid4())
ORIGIN = "https://space.test"


class ExplodingClient:
    """Any attempt to reach the marketplace fails the test."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("the marketplace must not be contacted here")


def make_marketplace(satellite_id: str | None = SATELLITE_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name="SyftHub",
        url="https://hub.test",
        email="space@example.com",
        password="pw",
        is_active=True,
        satellite_id=satellite_id,
    )


# ── shutdown says nothing to the marketplace ────────────────────────────


async def test_shutdown_does_not_contact_the_marketplace(monkeypatch):
    """No deregistration and no final report.

    Deleting a satellite would take its endpoints, stars, uptime history and
    collective memberships with it. Endpoints deactivate on their own once
    health reports stop, which also covers the unclean exits no hook can run
    for — so a shutdown-time call would buy at most the remaining TTL.
    """
    monkeypatch.setattr(hb_module, "SyftHubClient", ExplodingClient)
    marketplace = make_marketplace()

    # Stubs deliberately answer everything a final report would need, so the
    # test fails on the client call rather than passing on a missing attribute.
    async def get_public_url():
        return ORIGIN

    async def get_active(tenant_id):
        return [marketplace]

    async def get_published_endpoint_health(tenant, health_timeout=5.0):
        return [{"slug": "ep", "status": "healthy", "checked_at": "now"}]

    manager = EndpointHeartbeatManager(
        health_checker=SimpleNamespace(
            get_published_endpoint_health=get_published_endpoint_health
        ),
        marketplace_repository=SimpleNamespace(get_active=get_active),
        settings_repository=SimpleNamespace(get_public_url=get_public_url),
    )
    manager.set_tenant(SimpleNamespace(id=uuid4()))

    await manager.startup()
    await manager.shutdown()  # ExplodingClient raises if anything is sent


# ── publishing does not overwrite another space's slug ──────────────────


def make_publish_handler() -> PublishEndpointHandler:
    return PublishEndpointHandler(
        endpoint_repository=SimpleNamespace(),
        marketplace_repository=SimpleNamespace(),
        dataset_repository=SimpleNamespace(),
        model_repository=SimpleNamespace(),
        dataset_registry=SimpleNamespace(),
        model_registry=SimpleNamespace(),
    )


class RecordingClient:
    """Captures the publish arguments; stands in for a logged-in client."""

    last: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def login(self, *args, **kwargs):
        return None

    async def publish_endpoint(self, payload, satellite_id, overwrite=False):
        RecordingClient.last = {
            "slug": payload["slug"],
            "satellite_id": satellite_id,
            "overwrite": overwrite,
        }
        return {"id": "e1"}


@pytest.fixture
def publish_setup(monkeypatch):
    monkeypatch.setattr(publish_module, "SyftHubClient", RecordingClient)
    monkeypatch.setattr(
        publish_module.app_settings, "public_url", ORIGIN, raising=False
    )
    RecordingClient.last = {}

    handler = make_publish_handler()

    async def build_payload(endpoint):
        return {"slug": endpoint.slug}

    async def add_publication(*args, **kwargs):
        return None

    handler._build_publish_payload = build_payload  # type: ignore[method-assign]
    handler.endpoint_repository.add_publication = add_publication
    return handler


def make_endpoint(published_to: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(), tenant_id=uuid4(), slug="ep", published_to=published_to
    )


async def test_republishing_our_own_slug_overwrites_it(publish_setup):
    marketplace = make_marketplace()
    endpoint = make_endpoint(published_to=[str(marketplace.id)])

    result = await publish_setup._publish_to_marketplace(endpoint, marketplace)

    assert result.success
    assert RecordingClient.last["overwrite"] is True
    assert RecordingClient.last["satellite_id"] == SATELLITE_ID


async def test_a_first_publish_never_overwrites(publish_setup):
    """Slugs are unique per account: a conflict may be another space's endpoint."""
    marketplace = make_marketplace()
    endpoint = make_endpoint(published_to=[])

    await publish_setup._publish_to_marketplace(endpoint, marketplace)

    assert RecordingClient.last["overwrite"] is False


async def test_publishing_without_a_public_url_reports_instead_of_listing(
    publish_setup, monkeypatch
):
    """No origin means no satellite, and an endpoint the hub cannot route to."""
    monkeypatch.setattr(publish_module.app_settings, "public_url", None, raising=False)
    marketplace = make_marketplace(satellite_id=None)

    result = await publish_setup._publish_to_marketplace(
        make_endpoint(published_to=[]), marketplace
    )

    assert not result.success
    assert "public URL" in result.error
    assert RecordingClient.last == {}
