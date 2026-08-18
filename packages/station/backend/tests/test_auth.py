"""Auth: SyftHub sign-in proxy, role routing, session round-trip."""

import json

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
from syft_station.components.auth.syfthub import (
    SyftHubAuthError,
    SyftHubBuyerTokenError,
    SyftHubGoogleNotLinkedError,
    SyftHubIdentityClient,
    SyftHubUnavailableError,
)
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
            json={
                "id": 7,
                "username": "alice",
                "email": "alice@test.com",
                "full_name": "Alice",
            },
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


async def test_login_lowercases_profile_email(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "")

    def hub(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(
            200,
            json={
                "id": 7,
                "username": "alice",
                "email": "Alice@Test.COM",
                "full_name": "Alice",
            },
        )

    handler = AuthHandler(make_hub_client(hub))
    user = await handler.login("Alice@Test.COM", "pw")
    assert user.email == "alice@test.com"


# ── Google sign-in (existing SyftHub users only) ────────────────────────────


def google_hub(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/auth/google":
        body = json.loads(request.content)
        assert body["credential"] == "gtok"
        assert body["allow_signup"] is False  # existing users only
        return httpx.Response(200, json={"access_token": "tok"})
    if request.url.path == "/api/v1/users/me":
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json={
                "id": 7,
                "username": "alice",
                "email": "alice@test.com",
                "full_name": "Alice",
            },
        )
    raise AssertionError(f"unexpected path {request.url.path}")


async def test_google_login_returns_profile():
    profile = await make_hub_client(google_hub).authenticate_with_google("gtok")
    assert profile.email == "alice@test.com"
    assert profile.username == "alice"


async def test_google_unknown_email_is_auth_error():
    def hub(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"detail": {"code": "account_not_found", "message": "nope"}}
        )

    with pytest.raises(SyftHubAuthError, match="No SyftHub account"):
        await make_hub_client(hub).authenticate_with_google("gtok")


async def test_google_not_linked_is_not_linked_error():
    def hub(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "email already exists"})

    with pytest.raises(SyftHubGoogleNotLinkedError):
        await make_hub_client(hub).authenticate_with_google("gtok")


async def test_google_hub_down_is_unavailable():
    def hub(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(SyftHubUnavailableError):
        await make_hub_client(hub).authenticate_with_google("gtok")


async def test_handler_google_login_routes_role(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "alice@test.com")
    user = await AuthHandler(make_hub_client(google_hub)).login_with_google("gtok")
    assert user.email == "alice@test.com"
    assert user.role == ROLE_ADMIN


async def test_handler_google_not_linked_409(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "")

    def hub(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "exists"})

    with pytest.raises(HTTPException) as exc:
        await AuthHandler(make_hub_client(hub)).login_with_google("gtok")
    assert exc.value.status_code == 409


async def test_handler_google_unknown_401(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "")

    def hub(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": {"code": "account_not_found"}})

    with pytest.raises(HTTPException) as exc:
        await AuthHandler(make_hub_client(hub)).login_with_google("gtok")
    assert exc.value.status_code == 401


def test_auth_config_reflects_google_client_id(monkeypatch):
    monkeypatch.setattr(app_settings, "google_client_id", "abc.googleusercontent.com")
    cfg = AuthHandler(make_hub_client(happy_hub)).auth_config()
    assert cfg.google_enabled is True
    assert cfg.google_client_id == "abc.googleusercontent.com"


def test_auth_config_google_disabled_when_unset(monkeypatch):
    monkeypatch.setattr(app_settings, "google_client_id", "")
    cfg = AuthHandler(make_hub_client(happy_hub)).auth_config()
    assert cfg.google_enabled is False


# ── Credits identity: PAT mint / whoami / buyer-token verification ──────────


def pat_hub(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/auth/login":
        return httpx.Response(200, json={"access_token": "tok", "token_type": "bearer"})
    if request.url.path == "/api/v1/auth/tokens":
        assert request.headers["Authorization"] == "Bearer tok"
        body = json.loads(request.content)
        assert body["scopes"] == ["write"]
        return httpx.Response(201, json={"token": "syft_pat_abc", "name": body["name"]})
    if request.url.path == "/api/v1/users/me":
        assert request.headers["Authorization"] == "Bearer syft_pat_abc"
        return httpx.Response(
            200,
            json={
                "id": 42,
                "username": "admin",
                "email": "admin@test.com",
                "full_name": "Admin",
            },
        )
    raise AssertionError(f"unexpected path {request.url.path}")


async def test_mint_pat_returns_token():
    client = make_hub_client(pat_hub)
    pat = await client.mint_pat("admin@test.com", "pw")
    assert pat == "syft_pat_abc"


async def test_mint_pat_limit_reached_is_auth_error():
    def hub(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(400, json={"detail": "token limit"})

    with pytest.raises(SyftHubAuthError):
        await make_hub_client(hub).mint_pat("admin@test.com", "pw")


async def test_whoami_resolves_pat_owner():
    client = make_hub_client(pat_hub)
    profile = await client.whoami("syft_pat_abc")
    assert profile.id == 42
    assert profile.username == "admin"


async def test_whoami_rejected_pat_is_auth_error():
    def hub(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid API token"})

    with pytest.raises(SyftHubAuthError):
        await make_hub_client(hub).whoami("syft_pat_revoked")


def verify_hub(result: dict):
    def hub(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/verify"
        assert request.headers["Authorization"] == "Bearer syft_pat_abc"
        return httpx.Response(200, json=result)

    return hub


async def test_verify_buyer_token_returns_billing_claims():
    client = make_hub_client(
        verify_hub(
            {
                "valid": True,
                "sub": "9",
                "email": "buyer@test.com",
                "username": "buyer",
                "aud": "admin",
                "exp": 1700000000,
                "iat": 1699999940,
            }
        )
    )
    buyer = await client.verify_buyer_token("syft_pat_abc", "sat-token")
    assert buyer.email == "buyer@test.com"
    assert buyer.exp == 1700000000


async def test_verify_buyer_token_lowercases_email():
    client = make_hub_client(
        verify_hub(
            {"valid": True, "sub": "9", "email": "Buyer@Test.COM", "username": "buyer"}
        )
    )
    buyer = await client.verify_buyer_token("syft_pat_abc", "sat-token")
    assert buyer.email == "buyer@test.com"


async def test_verify_buyer_token_invalid_raises_buyer_error():
    client = make_hub_client(
        verify_hub({"valid": False, "error": "token_expired", "message": "expired"})
    )
    with pytest.raises(SyftHubBuyerTokenError, match="expired"):
        await client.verify_buyer_token("syft_pat_abc", "sat-token")


async def test_verify_buyer_token_guest_rejected():
    client = make_hub_client(
        verify_hub(
            {
                "valid": True,
                "sub": "guest",
                "email": "guest@syfthub.org",
                "username": "guest",
            }
        )
    )
    with pytest.raises(SyftHubBuyerTokenError, match="Guest"):
        await client.verify_buyer_token("syft_pat_abc", "sat-token")


async def test_verify_buyer_token_bad_pat_is_auth_error():
    def hub(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid API token"})

    with pytest.raises(SyftHubAuthError):
        await make_hub_client(hub).verify_buyer_token("syft_pat_bad", "sat-token")


async def test_verify_buyer_token_hub_down_is_unavailable():
    def hub(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(SyftHubUnavailableError):
        await make_hub_client(hub).verify_buyer_token("syft_pat_abc", "sat-token")


def test_session_payload_round_trips(monkeypatch):
    monkeypatch.setattr(app_settings, "session_secret", "test-secret")
    user = SessionUser(email="a@b.c", username="a", name="A", role=ROLE_MEMBER)
    token = _serializer().dumps(user.model_dump())
    restored = SessionUser.model_validate(_serializer().loads(token, max_age=60))
    assert restored == user
