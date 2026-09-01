"""Tests for the satellite half of SyftHubClient — wire format and errors.

These pin what this space *sends*; the hub's own semantics (which endpoints
a sync deletes, when a token's audience matches) are its to test. The
satellite_id must reach every write path, and each documented failure must
arrive as a type a caller can branch on rather than a bare status code.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import httpx
import pytest

from syft_space.components.shared.syfthub_client import (
    NotFoundError,
    Satellite,
    SatelliteKind,
    SatelliteKindMismatchError,
    SatelliteOriginConflictError,
    SatelliteRequiredError,
    SyftHubClient,
    ValidationError,
)

HUB_URL = "https://hub.test"
ORIGIN = "https://space.test"
SATELLITE_ID = str(uuid4())

SATELLITE_BODY = {
    "id": SATELLITE_ID,
    "kind": "space",
    "base_url": ORIGIN,
    "last_seen_at": None,
    "created_at": "2026-08-27T10:00:00Z",
}


def make_client(handler) -> tuple[SyftHubClient, list[httpx.Request]]:
    """An authenticated client whose requests go to `handler`, plus a log."""
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = SyftHubClient(HUB_URL)
    client._client = httpx.AsyncClient(
        base_url=HUB_URL, transport=httpx.MockTransport(record)
    )
    return client, seen


def responds(status: int, body: dict | list) -> object:
    return lambda request: httpx.Response(status, json=body)


def error(status: int, code: str, message: str, **extra) -> object:
    detail = {"code": code, "message": message, **extra}
    return lambda request: httpx.Response(status, json={"detail": detail})


def body_of(request: httpx.Request) -> dict:
    return json.loads(request.content)


# ── register ────────────────────────────────────────────────────────────


async def test_register_sends_kind_and_origin_and_parses_the_satellite():
    client, seen = make_client(responds(201, SATELLITE_BODY))

    satellite = await client.register_satellite(ORIGIN)

    assert body_of(seen[0]) == {"kind": "space", "base_url": ORIGIN}
    assert seen[0].url.path == "/api/v1/satellites"
    assert isinstance(satellite, Satellite)
    assert satellite.id == UUID(SATELLITE_ID)
    assert satellite.kind is SatelliteKind.SPACE


async def test_register_sends_the_local_url_verbatim():
    """The hub canonicalises; re-implementing that here could disagree."""
    client, seen = make_client(responds(201, SATELLITE_BODY))

    satellite = await client.register_satellite("  HTTPS://Space.TEST:443/v1/  ")

    assert body_of(seen[0])["base_url"] == "  HTTPS://Space.TEST:443/v1/  "
    # …and the canonical form comes back from the hub, not from us.
    assert satellite.base_url == ORIGIN


async def test_register_as_the_other_kind_raises_kind_mismatch():
    client, _ = make_client(
        error(409, "SATELLITE_KIND_MISMATCH", "already registered as a space")
    )

    with pytest.raises(SatelliteKindMismatchError) as excinfo:
        await client.register_satellite(ORIGIN, kind=SatelliteKind.STATION)

    assert excinfo.value.code == "SATELLITE_KIND_MISMATCH"


async def test_register_with_an_unusable_origin_raises_validation():
    client, _ = make_client(error(422, "VALIDATION_ERROR", "not an origin"))

    with pytest.raises(ValidationError):
        await client.register_satellite("not-a-url")


# ── move ────────────────────────────────────────────────────────────────


async def test_move_puts_to_the_satellite_and_keeps_its_id():
    client, seen = make_client(responds(200, SATELLITE_BODY))

    satellite = await client.move_satellite(SATELLITE_ID, "https://moved.test")

    assert seen[0].method == "PUT"
    assert seen[0].url.path == f"/api/v1/satellites/{SATELLITE_ID}"
    assert body_of(seen[0]) == {"base_url": "https://moved.test"}
    assert satellite.id == UUID(SATELLITE_ID)


async def test_move_of_an_unknown_satellite_raises_not_found():
    client, _ = make_client(error(404, "NOT_FOUND", "no such satellite"))

    with pytest.raises(NotFoundError):
        await client.move_satellite(SATELLITE_ID, ORIGIN)


async def test_move_onto_a_siblings_origin_raises_origin_conflict():
    client, _ = make_client(error(409, "CONFLICT", "Base_url already exists"))

    with pytest.raises(SatelliteOriginConflictError):
        await client.move_satellite(SATELLITE_ID, ORIGIN)


# ── the write paths all carry the id ────────────────────────────────────


async def test_sync_sends_the_satellite_id_in_the_body():
    client, seen = make_client(responds(200, {"synced": 0}))

    await client.sync_endpoints([], SATELLITE_ID)

    assert body_of(seen[0]) == {"endpoints": [], "satellite_id": SATELLITE_ID}


async def test_publish_sends_the_satellite_id_as_a_query_parameter():
    """A query param, not a body field: the body schema is reused inside sync."""
    client, seen = make_client(responds(201, {"id": "e1"}))

    await client.publish_endpoint({"slug": "ep"}, SATELLITE_ID)

    assert seen[0].url.params["satellite_id"] == SATELLITE_ID
    assert "satellite_id" not in body_of(seen[0])


async def test_health_sends_the_satellite_id_in_the_body():
    client, seen = make_client(responds(200, {"updated": 0}))

    await client.update_endpoint_health([], 90, ORIGIN, SATELLITE_ID)

    sent = body_of(seen[0])
    assert sent["satellite_id"] == SATELLITE_ID
    assert sent["url"] == ORIGIN
    assert sent["ttl_seconds"] == 90


async def test_overwrite_updates_by_slug_without_re_homing_the_endpoint():
    """An update never moves an endpoint between satellites, so it sends none."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(400, json={"detail": "slug exists"})
        return httpx.Response(200, json={"id": "e1"})

    client, seen = make_client(handler)

    await client.publish_endpoint({"slug": "ep"}, SATELLITE_ID, overwrite=True)

    patch = seen[1]
    assert patch.method == "PATCH"
    assert patch.url.path == "/api/v1/endpoints/slug/ep"
    assert "satellite_id" not in patch.url.params


async def test_without_overwrite_a_conflict_is_not_patched_away():
    client, seen = make_client(
        lambda request: httpx.Response(400, json={"detail": "slug exists"})
    )

    with pytest.raises(ValidationError):
        await client.publish_endpoint({"slug": "ep"}, SATELLITE_ID, overwrite=False)

    assert [r.method for r in seen] == ["POST"]


# ── verify ──────────────────────────────────────────────────────────────


async def test_verify_narrows_the_audience_when_an_id_is_known():
    client, seen = make_client(
        responds(
            200, {"valid": True, "email": "buyer@example.com", "aud": SATELLITE_ID}
        )
    )

    result = await client.verify_satellite_token("tok", SATELLITE_ID)

    assert body_of(seen[0]) == {"token": "tok", "satellite_id": SATELLITE_ID}
    assert result.valid and result.aud == SATELLITE_ID


async def test_verify_omits_the_id_when_there_is_none():
    """Unregistered spaces must keep authenticating exactly as before."""
    client, seen = make_client(
        responds(200, {"valid": True, "email": "buyer@example.com"})
    )

    await client.verify_satellite_token("tok", None)

    assert body_of(seen[0]) == {"token": "tok"}


async def test_verify_surfaces_the_failure_reason():
    client, _ = make_client(
        responds(
            200,
            {"valid": False, "error": "audience_mismatch", "message": "wrong aud"},
        )
    )

    result = await client.verify_satellite_token("tok", SATELLITE_ID)

    assert not result.valid
    assert result.error == "audience_mismatch"


# ── the ambiguous-satellite error ───────────────────────────────────────


async def test_a_422_carrying_a_count_becomes_satellite_required():
    """`count` is what separates "you owed us an id" from any other 422."""
    client, _ = make_client(
        error(422, "VALIDATION_ERROR", "satellite_id is required", count=2)
    )

    with pytest.raises(SatelliteRequiredError) as excinfo:
        await client.sync_endpoints([], SATELLITE_ID)

    assert excinfo.value.count == 2
    assert isinstance(excinfo.value, ValidationError)


async def test_a_422_without_a_count_stays_an_ordinary_validation_error():
    client, _ = make_client(error(422, "VALIDATION_ERROR", "bad payload"))

    with pytest.raises(ValidationError) as excinfo:
        await client.sync_endpoints([], SATELLITE_ID)

    assert not isinstance(excinfo.value, SatelliteRequiredError)


# ── what the client must never be able to do ────────────────────────────


def test_the_client_cannot_delete_a_satellite():
    """Deleting one deletes its endpoints, stars, uptime and memberships."""
    assert not hasattr(SyftHubClient, "delete_satellite")


def test_the_client_cannot_write_the_legacy_profile_domain():
    """Deprecated hub-side, and clearing it was always silently ignored."""
    assert not hasattr(SyftHubClient, "update_profile")
