"""The Hub decides whether a slug can be published; this space only relays.

Pins the wire call, the fallback for Hubs without the route, and that a
422's field name survives into the message a publisher reads.
"""

from __future__ import annotations

import httpx
import pytest

from syft_space.components.shared.syfthub_client import (
    SyftHubClient,
    ValidationError,
    _parse_error_response,
)

HUB_URL = "https://hub.test"


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


async def test_availability_relays_the_hubs_verdict():
    body = {
        "slug": "admin",
        "available": False,
        "reason": "reserved",
        "message": "'admin' is a reserved slug and cannot be used",
    }
    client, seen = make_client(lambda r: httpx.Response(200, json=body))

    verdict = await client.slug_availability("admin")

    assert seen[0].url.path == "/api/v1/endpoints/admin/availability"
    assert verdict.available is False
    assert verdict.reason == "reserved"
    assert verdict.message == body["message"]


@pytest.mark.parametrize("missing_status", [404, 405])
async def test_availability_falls_back_to_exists_on_older_hubs(missing_status: int):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/availability"):
            return httpx.Response(missing_status, json={"detail": "Not Found"})
        return httpx.Response(200, json=True)

    client, seen = make_client(handler)

    verdict = await client.slug_availability("radar")

    assert [r.url.path for r in seen] == [
        "/api/v1/endpoints/radar/availability",
        "/api/v1/endpoints/radar/exists",
    ]
    assert verdict.available is False
    assert verdict.reason == "taken"
    assert verdict.message is None


async def test_availability_fallback_reports_free_slug():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/availability"):
            return httpx.Response(404, json={"detail": "Not Found"})
        return httpx.Response(200, json=False)

    client, _ = make_client(handler)

    verdict = await client.slug_availability("radar")

    assert verdict.available is True
    assert verdict.reason is None


def test_validation_error_message_names_the_field():
    response = httpx.Response(
        422,
        json={
            "detail": [
                {
                    "type": "string_too_long",
                    "loc": ["body", "description"],
                    "msg": "String should have at most 500 characters",
                },
                {"loc": ["body", "slug"], "msg": "'admin' is a reserved slug"},
            ]
        },
        request=httpx.Request("POST", f"{HUB_URL}/api/v1/endpoints"),
    )

    parsed = _parse_error_response(response)

    assert parsed.message == (
        "description: String should have at most 500 characters; "
        "slug: 'admin' is a reserved slug"
    )


async def test_publish_raises_validation_error_with_field_message():
    detail = [{"loc": ["body", "description"], "msg": "too long"}]
    client, _ = make_client(lambda r: httpx.Response(422, json={"detail": detail}))

    with pytest.raises(ValidationError) as exc:
        await client.publish_endpoint({"slug": "x"}, satellite_id="sat")

    assert exc.value.message == "description: too long"
    assert exc.value.errors == detail
