"""Auth: SyftHub sign-in proxy, role routing, session round-trip."""

import httpx
import pytest
from fastapi import HTTPException

from syft_station.components.auth.handlers import AuthHandler
from syft_station.components.auth.session import (
    ROLE_ADMIN,
    ROLE_MEMBER,
    SessionUser,
    _serializer,
)
from syft_station.components.auth.syfthub import SyftHubIdentityClient
from syft_station.config import app_settings

HUB_URL = "https://hub.test"


def make_hub_client(handler) -> SyftHubIdentityClient:
    """SyftHub client whose HTTP layer is a MockTransport."""
    client = SyftHubIdentityClient(HUB_URL)
    client._build_http_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        base_url=HUB_URL, transport=httpx.MockTransport(handler)
    )
    return client


def happy_hub(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/auth/login":
        assert b"username=" in request.content and b"password=" in request.content
        return httpx.Response(200, json={"access_token": "tok", "token_type": "bearer"})
    if request.url.path == "/api/v1/users/me":
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json={"username": "alice", "email": "alice@test.com", "full_name": "Alice"},
        )
    raise AssertionError(f"unexpected path {request.url.path}")


async def test_login_returns_member(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "admin@openmined.org")
    handler = AuthHandler(make_hub_client(happy_hub))
    user = await handler.login("alice@test.com", "pw")
    assert user.email == "alice@test.com"
    assert user.role == ROLE_MEMBER


async def test_login_admin_role_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "Alice@Test.com")
    handler = AuthHandler(make_hub_client(happy_hub))
    user = await handler.login("alice@test.com", "pw")
    assert user.role == ROLE_ADMIN


async def test_login_bad_credentials_401(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "")

    def hub(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "bad credentials"})

    handler = AuthHandler(make_hub_client(hub))
    with pytest.raises(HTTPException) as exc:
        await handler.login("alice@test.com", "wrong")
    assert exc.value.status_code == 401


async def test_login_hub_unreachable_502(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "")

    def hub(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    handler = AuthHandler(make_hub_client(hub))
    with pytest.raises(HTTPException) as exc:
        await handler.login("alice@test.com", "pw")
    assert exc.value.status_code == 502


async def test_no_admin_email_means_no_admin(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "")
    handler = AuthHandler(make_hub_client(happy_hub))
    user = await handler.login("alice@test.com", "pw")
    assert user.role == ROLE_MEMBER


def test_session_payload_round_trips(monkeypatch):
    monkeypatch.setattr(app_settings, "session_secret", "test-secret")
    user = SessionUser(email="a@b.c", username="a", name="A", role=ROLE_MEMBER)
    token = _serializer().dumps(user.model_dump())
    restored = SessionUser.model_validate(_serializer().loads(token, max_age=60))
    assert restored == user
