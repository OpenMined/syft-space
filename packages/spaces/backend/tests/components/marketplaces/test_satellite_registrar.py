"""Tests for SatelliteRegistrar — when this space registers, moves, or does neither.

The invariant these exist for: a space must end up with exactly one satellite
however its public URL changes. POST is idempotent only on the origin, so a
rotated tunnel URL that POSTed again would leave a second satellite behind
and the old one serving a dead address.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from syft_space.components.marketplaces.satellites import SatelliteRegistrar
from syft_space.components.shared.syfthub_client import (
    SatelliteKindMismatchError,
    SyftHubClient,
)

HUB_URL = "https://hub.test"
ORIGIN = "https://space.test"
MOVED = "https://moved.test"
SATELLITE_ID = str(uuid4())
NEW_SATELLITE_ID = str(uuid4())


def satellite_body(satellite_id: str = SATELLITE_ID, base_url: str = ORIGIN) -> dict:
    return {
        "id": satellite_id,
        "kind": "space",
        "base_url": base_url,
        "last_seen_at": None,
        "created_at": "2026-08-27T10:00:00Z",
    }


class FakeMarketplaceRepository:
    """Records what the registrar persists."""

    def __init__(self) -> None:
        self.writes: list[str | None] = []

    async def set_satellite(self, id, tenant_id, satellite_id):  # noqa: A002
        self.writes.append(satellite_id)


def make_marketplace(satellite_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name="SyftHub",
        url=HUB_URL,
        email="space@example.com",
        password="pw",
        satellite_id=satellite_id,
    )


def make_client(handler) -> tuple[SyftHubClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = SyftHubClient(HUB_URL)
    client._client = httpx.AsyncClient(
        base_url=HUB_URL, transport=httpx.MockTransport(record)
    )
    return client, seen


def routes(*, post=None, put=None):
    """Dispatch by method; an unrouted call fails the test loudly."""

    def handler(request: httpx.Request) -> httpx.Response:
        response = {"POST": post, "PUT": put}.get(request.method)
        if response is None:
            raise AssertionError(f"unexpected {request.method} {request.url}")
        return response(request) if callable(response) else response

    return handler


def calls(seen: list[httpx.Request]) -> list[tuple[str, str]]:
    return [(r.method, r.url.path) for r in seen]


# ── ensure_with_client: register vs move ────────────────────────────────


async def test_no_stored_id_registers_and_returns_the_satellite():
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(routes(post=httpx.Response(201, json=satellite_body())))

    satellite = await registrar.ensure_with_client(client, ORIGIN, None)

    assert str(satellite.id) == SATELLITE_ID
    assert calls(seen) == [("POST", "/api/v1/satellites")]


async def test_a_changed_origin_moves_and_never_creates_a_second_satellite():
    """The reason the registrar exists: POST here would duplicate."""
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(
        routes(put=httpx.Response(200, json=satellite_body(base_url=MOVED)))
    )

    satellite = await registrar.ensure_with_client(client, MOVED, SATELLITE_ID)

    assert calls(seen) == [("PUT", f"/api/v1/satellites/{SATELLITE_ID}")]
    assert str(satellite.id) == SATELLITE_ID  # same satellite, new origin
    assert satellite.base_url == MOVED


async def test_an_unchanged_origin_is_a_no_op_move_not_a_second_satellite():
    """Self is excluded from the hub's conflict check, so re-moving is a 200."""
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(routes(put=httpx.Response(200, json=satellite_body())))

    satellite = await registrar.ensure_with_client(client, ORIGIN, SATELLITE_ID)

    assert calls(seen) == [("PUT", f"/api/v1/satellites/{SATELLITE_ID}")]
    assert str(satellite.id) == SATELLITE_ID


async def test_a_stale_id_re_registers_and_adopts_the_new_one():
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(
        routes(
            put=httpx.Response(404, json={"detail": {"code": "NOT_FOUND"}}),
            post=httpx.Response(201, json=satellite_body(NEW_SATELLITE_ID)),
        )
    )

    satellite = await registrar.ensure_with_client(client, ORIGIN, SATELLITE_ID)

    assert calls(seen) == [
        ("PUT", f"/api/v1/satellites/{SATELLITE_ID}"),
        ("POST", "/api/v1/satellites"),
    ]
    assert str(satellite.id) == NEW_SATELLITE_ID


async def test_a_sibling_on_that_origin_keeps_our_id_rather_than_stealing_theirs():
    """Taking it would drag this space's endpoints onto another's satellite."""
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(
        routes(put=httpx.Response(409, json={"detail": {"code": "CONFLICT"}}))
    )

    satellite = await registrar.ensure_with_client(client, ORIGIN, SATELLITE_ID)

    assert satellite is None
    assert calls(seen) == [("PUT", f"/api/v1/satellites/{SATELLITE_ID}")]


async def test_no_public_url_registers_nothing():
    """Onboarding connects the marketplace before the URL is set."""
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(routes())

    assert await registrar.ensure_with_client(client, None, None) is None
    assert seen == []


async def test_a_kind_mismatch_is_raised_not_swallowed():
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, _ = make_client(
        routes(
            post=httpx.Response(
                409, json={"detail": {"code": "SATELLITE_KIND_MISMATCH"}}
            )
        )
    )

    with pytest.raises(SatelliteKindMismatchError):
        await registrar.ensure_with_client(client, ORIGIN, None)


async def test_a_space_only_ever_registers_itself_as_a_space():
    """Registering our own origin as a station is a guaranteed 409.

    The credits_url of a self-hosted wallet shares the space's origin, and
    the heartbeat has already claimed it as a `space`. Nothing here may ask
    for the other kind.
    """
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    kinds: list[str] = []

    def capture(request: httpx.Request) -> httpx.Response:
        kinds.append(json.loads(request.content)["kind"])
        return httpx.Response(201, json=satellite_body())

    client, _ = make_client(routes(post=capture))
    await registrar.ensure_with_client(client, ORIGIN, None)
    await registrar.resolve_id(client, make_marketplace(None), ORIGIN, uuid4())

    assert kinds == ["space", "space"]


# ── resolve_id: what the consumers call ─────────────────────────────────


async def test_resolve_id_spends_no_hub_call_when_the_id_is_known():
    """The heartbeat runs every 30s; it must not move the satellite each time."""
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(routes())
    marketplace = make_marketplace(SATELLITE_ID)

    resolved = await registrar.resolve_id(client, marketplace, ORIGIN, uuid4())

    assert resolved == SATELLITE_ID
    assert seen == []


async def test_resolve_id_registers_and_persists_when_there_is_no_id():
    repository = FakeMarketplaceRepository()
    registrar = SatelliteRegistrar(repository)
    client, seen = make_client(routes(post=httpx.Response(201, json=satellite_body())))
    marketplace = make_marketplace(None)

    resolved = await registrar.resolve_id(client, marketplace, ORIGIN, uuid4())

    assert resolved == SATELLITE_ID
    assert repository.writes == [SATELLITE_ID]
    assert marketplace.satellite_id == SATELLITE_ID
    assert calls(seen) == [("POST", "/api/v1/satellites")]


async def test_resolve_id_returns_none_without_a_public_url():
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    client, seen = make_client(routes())

    resolved = await registrar.resolve_id(client, make_marketplace(None), None, uuid4())

    assert resolved is None
    assert seen == []


async def test_forget_id_clears_the_stored_id_so_the_next_resolve_registers():
    repository = FakeMarketplaceRepository()
    registrar = SatelliteRegistrar(repository)
    marketplace = make_marketplace(SATELLITE_ID)

    await registrar.forget_id(marketplace, uuid4())

    assert repository.writes == [None]
    assert marketplace.satellite_id is None


# ── ensure: the persisting wrapper used by the settings routes ──────────


async def test_ensure_persists_the_id_and_surfaces_hub_errors_as_http(monkeypatch):
    import syft_space.components.marketplaces.satellites as satellites_module

    repository = FakeMarketplaceRepository()
    registrar = SatelliteRegistrar(repository)
    marketplace = make_marketplace(None)

    def fake_client(base_url, **kwargs):
        client, _ = make_client(routes(post=httpx.Response(201, json=satellite_body())))

        async def login(*args, **kwargs):
            return None

        client.login = login  # type: ignore[method-assign]
        return client

    monkeypatch.setattr(satellites_module, "SyftHubClient", fake_client)

    resolved = await registrar.ensure(marketplace, ORIGIN, uuid4())

    assert resolved == SATELLITE_ID
    assert repository.writes == [SATELLITE_ID]


async def test_ensure_without_credentials_keeps_whatever_id_is_stored():
    registrar = SatelliteRegistrar(FakeMarketplaceRepository())
    marketplace = make_marketplace(SATELLITE_ID)
    marketplace.password = ""

    assert await registrar.ensure(marketplace, ORIGIN, uuid4()) == SATELLITE_ID
