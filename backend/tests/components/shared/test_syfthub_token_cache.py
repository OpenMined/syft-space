"""Tests for SyftHubClient session caching via TokenCache.

The cache exists so short-lived clients (heartbeats, per-request auth)
reuse sessions instead of hitting /auth/login on every instantiation.
Tests inject isolated TokenCache instances; one test covers the shared
process-wide default.
"""

from __future__ import annotations

import httpx
import pytest

import syft_space.components.shared.syfthub_client as syfthub_client_module
from syft_space.components.shared.syfthub_client import (
    AsyncRefreshTokenAuth,
    AuthenticationError,
    SyftHubClient,
    TokenCache,
    TokenResponse,
)

HUB_URL = "https://hub.test"
USER = "user@test.org"
TOKENS = TokenResponse(access_token="access-1", refresh_token="refresh-1")


@pytest.fixture
def login_spy(monkeypatch):
    """Replace the network login with a counting stub."""
    calls: list[tuple[str, str]] = []

    async def fake_password_login(self, username: str, password: str):
        calls.append((username, password))
        return TOKENS

    monkeypatch.setattr(SyftHubClient, "_password_login", fake_password_login)
    return calls


async def test_first_login_hits_network_and_caches(login_spy):
    cache = TokenCache()
    async with SyftHubClient(HUB_URL, token_cache=cache) as client:
        tokens = await client.login(USER, "pw")

    assert tokens == TOKENS
    assert login_spy == [(USER, "pw")]
    assert cache.get(HUB_URL, USER) == TOKENS


async def test_second_client_reuses_cached_session(login_spy):
    cache = TokenCache()
    async with SyftHubClient(HUB_URL, token_cache=cache) as first:
        await first.login(USER, "pw")
    async with SyftHubClient(HUB_URL, token_cache=cache) as second:
        tokens = await second.login(USER, "pw")

    assert len(login_spy) == 1
    assert tokens == TOKENS
    assert second.is_authenticated


async def test_default_cache_is_shared_across_clients(login_spy, monkeypatch):
    monkeypatch.setattr(syfthub_client_module, "_default_token_cache", TokenCache())
    async with SyftHubClient(HUB_URL) as first:
        await first.login(USER, "pw")
    async with SyftHubClient(HUB_URL) as second:
        await second.login(USER, "pw")

    assert len(login_spy) == 1


async def test_cache_is_scoped_per_url_and_username(login_spy):
    cache = TokenCache()
    async with SyftHubClient(HUB_URL, token_cache=cache) as client:
        await client.login(USER, "pw")
    async with SyftHubClient(HUB_URL, token_cache=cache) as client:
        await client.login("other@test.org", "pw")
    async with SyftHubClient("https://other-hub.test", token_cache=cache) as client:
        await client.login(USER, "pw")

    assert len(login_spy) == 3


async def test_use_cache_false_always_validates_credentials(login_spy):
    cache = TokenCache()
    async with SyftHubClient(HUB_URL, token_cache=cache) as client:
        await client.login(USER, "pw")
    async with SyftHubClient(HUB_URL, token_cache=cache) as client:
        await client.login(USER, "pw", use_cache=False)

    assert len(login_spy) == 2

    # Bypassing login must not populate the cache either
    fresh_cache = TokenCache()
    async with SyftHubClient(HUB_URL, token_cache=fresh_cache) as client:
        await client.login(USER, "pw", use_cache=False)
    assert fresh_cache.get(HUB_URL, USER) is None


async def test_authenticate_with_tokens_does_not_touch_cache():
    cache = TokenCache()
    async with SyftHubClient(HUB_URL, token_cache=cache) as client:
        client.authenticate_with_tokens("access-x", "refresh-x")

    assert client.is_authenticated
    assert cache.get(HUB_URL, USER) is None


async def test_relogin_failure_evicts_cached_session(monkeypatch):
    cache = TokenCache()
    cache.put(HUB_URL, USER, TOKENS)

    async def failing_login(self, username: str, password: str):
        raise AuthenticationError("Invalid credentials", status_code=401)

    monkeypatch.setattr(SyftHubClient, "_password_login", failing_login)

    async with SyftHubClient(HUB_URL, token_cache=cache) as client:
        with pytest.raises(AuthenticationError):
            await client._relogin(USER, "pw")

    assert cache.get(HUB_URL, USER) is None


class _StubAuthClient:
    """Fake httpx client returning canned responses for /auth/refresh."""

    def __init__(self, response: httpx.Response):
        self._response = response
        self.calls = 0

    async def post(self, *args, **kwargs) -> httpx.Response:
        self.calls += 1
        return self._response


async def test_refresh_success_updates_tokens_and_cache():
    fresh = {"access_token": "access-2", "refresh_token": "refresh-2"}
    stub = _StubAuthClient(httpx.Response(200, json=fresh))
    updated: list[TokenResponse] = []

    auth = AsyncRefreshTokenAuth(
        auth_client=stub,  # type: ignore[arg-type]
        access_token="access-1",
        refresh_token="refresh-1",
        on_tokens_updated=updated.append,
    )
    await auth._refresh()

    assert auth.access_token == "access-2"
    assert auth.refresh_token == "refresh-2"
    assert updated and updated[0].access_token == "access-2"


async def test_refresh_falls_back_to_relogin_when_refresh_rejected():
    stub = _StubAuthClient(httpx.Response(401, json={"detail": "expired"}))
    fresh = TokenResponse(access_token="access-3", refresh_token="refresh-3")
    updated: list[TokenResponse] = []

    async def relogin() -> TokenResponse:
        return fresh

    auth = AsyncRefreshTokenAuth(
        auth_client=stub,  # type: ignore[arg-type]
        access_token="access-1",
        refresh_token="refresh-1",
        on_tokens_updated=updated.append,
        relogin=relogin,
    )
    await auth._refresh()

    assert auth.access_token == "access-3"
    assert updated == [fresh]


async def test_refresh_without_relogin_propagates_error():
    stub = _StubAuthClient(httpx.Response(401, json={"detail": "expired"}))
    auth = AsyncRefreshTokenAuth(
        auth_client=stub,  # type: ignore[arg-type]
        access_token="access-1",
        refresh_token="refresh-1",
    )
    with pytest.raises(AuthenticationError):
        await auth._refresh()
