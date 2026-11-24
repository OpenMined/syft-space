"""Tests for the SyftHub session shared by short-lived SyftHubClient instances.

Clients for one (hub, account) share a HubSession, so heartbeats and
per-request auth log in once and refresh once, however many run at a time.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from syft_space.components.shared.syfthub import (
    AuthenticationError,
    HubClients,
    HubSession,
    HubSessions,
    ServerError,
    SyftHubClient,
    TokenResponse,
)

HUB_URL = "https://hub.test"
USER = "user@test.org"
PASSWORD = "pw"


class Hub:
    """Fake hub: issues numbered tokens and accepts only the newest one."""

    def __init__(self) -> None:
        self.logins = 0
        self.refreshes = 0
        self.issued = 0
        self.refresh_status = 200
        self.login_status = 200
        self.transport = httpx.MockTransport(self._handle)

    @property
    def current(self) -> TokenResponse:
        return TokenResponse(
            access_token=f"access-{self.issued}", refresh_token=f"refresh-{self.issued}"
        )

    def expire(self) -> None:
        """Make the hub reject every token issued so far."""
        self.issued += 1

    def _issue(self) -> httpx.Response:
        self.issued += 1
        return httpx.Response(200, json=self.current.model_dump())

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)
        if request.url.path == "/api/v1/auth/login":
            self.logins += 1
            if self.login_status != 200:
                return httpx.Response(self.login_status, json={"detail": "no"})
            return self._issue()
        if request.url.path == "/api/v1/auth/refresh":
            self.refreshes += 1
            if self.refresh_status != 200:
                return httpx.Response(self.refresh_status, json={"detail": "no"})
            return self._issue()
        if request.headers["Authorization"] == f"Bearer {self.current.access_token}":
            return httpx.Response(200, json={"available": True})
        return httpx.Response(401, json={"detail": "expired"})

    def client(self, sessions: HubSessions | None = None, url: str = HUB_URL):
        http = httpx.AsyncClient(base_url=url, transport=self.transport)
        return SyftHubClient(url, sessions=sessions, http=http)


async def _call(hub: Hub, sessions: HubSessions, **login_kwargs) -> bool:
    """Log in with a new client and make one authenticated call."""
    async with hub.client(sessions) as client:
        await client.login(USER, PASSWORD, **login_kwargs)
        return (await client.slug_availability("slug")).available


# --- Sharing the session ---


async def test_first_login_hits_the_hub():
    hub = Hub()
    async with hub.client(HubSessions()) as client:
        tokens = await client.login(USER, PASSWORD)

    assert hub.logins == 1
    assert tokens == hub.current
    assert client.tokens == hub.current


async def test_second_client_reuses_the_session():
    hub = Hub()
    sessions = HubSessions()
    async with hub.client(sessions) as first:
        await first.login(USER, PASSWORD)
    async with hub.client(sessions) as second:
        tokens = await second.login(USER, PASSWORD)

    assert hub.logins == 1
    assert tokens == hub.current
    assert second.is_authenticated


async def test_clients_from_one_factory_share_a_session():
    hub = Hub()
    hub_clients = HubClients(transport=hub.transport)
    async with hub_clients.for_url(HUB_URL) as first:
        await first.login(USER, PASSWORD)
    async with hub_clients.for_url(HUB_URL) as second:
        await second.login(USER, PASSWORD)

    assert hub.logins == 1


async def test_clients_built_on_their_own_do_not_share_a_session():
    hub = Hub()
    async with hub.client() as first:
        await first.login(USER, PASSWORD)
    async with hub.client() as second:
        await second.login(USER, PASSWORD)

    assert hub.logins == 2


async def test_sessions_are_scoped_per_url_and_username():
    hub = Hub()
    sessions = HubSessions()
    async with hub.client(sessions) as client:
        await client.login(USER, PASSWORD)
    async with hub.client(sessions) as client:
        await client.login("other@test.org", PASSWORD)
    async with hub.client(sessions, url="https://other-hub.test") as client:
        await client.login(USER, PASSWORD)

    assert hub.logins == 3


async def test_use_cache_false_always_validates_credentials():
    hub = Hub()
    sessions = HubSessions()
    async with hub.client(sessions) as client:
        await client.login(USER, PASSWORD)
    async with hub.client(sessions) as client:
        await client.login(USER, PASSWORD, use_cache=False)

    assert hub.logins == 2

    # A private session is not shared with later clients.
    fresh = HubSessions()
    async with hub.client(fresh) as client:
        await client.login(USER, PASSWORD, use_cache=False)
    async with hub.client(fresh) as client:
        await client.login(USER, PASSWORD)
    assert hub.logins == 4


async def test_authenticate_with_tokens_does_not_share_a_session():
    hub = Hub()
    sessions = HubSessions()
    async with hub.client(sessions) as client:
        client.authenticate_with_tokens("access-x", "refresh-x")
        assert client.is_authenticated
    async with hub.client(sessions) as client:
        await client.login(USER, PASSWORD)

    assert hub.logins == 1


# --- Refreshing ---


async def test_expired_tokens_are_refreshed_and_the_call_retried():
    hub = Hub()
    sessions = HubSessions()
    assert await _call(hub, sessions)
    hub.expire()

    assert await _call(hub, sessions)
    assert (hub.logins, hub.refreshes) == (1, 1)
    assert sessions.for_account(HUB_URL, USER, PASSWORD).tokens == hub.current


async def test_rejected_refresh_falls_back_to_login():
    hub = Hub()
    sessions = HubSessions()
    await _call(hub, sessions)
    hub.expire()
    hub.refresh_status = 401

    assert await _call(hub, sessions)
    assert (hub.logins, hub.refreshes) == (2, 1)


async def test_failed_relogin_drops_the_tokens():
    hub = Hub()
    sessions = HubSessions()
    await _call(hub, sessions)
    hub.expire()
    hub.refresh_status = 401
    hub.login_status = 401

    with pytest.raises(AuthenticationError):
        await _call(hub, sessions)
    assert sessions.for_account(HUB_URL, USER, PASSWORD).tokens is None

    # The next client starts with a login instead of the dead tokens.
    hub.login_status = 200
    assert await _call(hub, sessions)
    assert hub.logins == 3


async def test_refresh_without_credentials_propagates_the_error():
    hub = Hub()
    hub.refresh_status = 401
    async with hub.client(HubSessions()) as client:
        client.authenticate_with_tokens("access-x", "refresh-x")
        with pytest.raises(AuthenticationError):
            await client.slug_availability("slug")

    assert hub.logins == 0


async def test_later_login_uses_the_newest_password():
    sessions = HubSessions()
    session = sessions.for_account(HUB_URL, USER, "old")

    assert sessions.for_account(HUB_URL, USER, "new") is session
    assert session.password == "new"


# --- One login or refresh, however many clients are waiting ---


async def test_concurrent_first_logins_share_one_login():
    hub = Hub()
    sessions = HubSessions()

    results = await asyncio.gather(*(_call(hub, sessions) for _ in range(20)))

    assert results == [True] * 20
    assert hub.logins == 1


async def test_clients_sharing_a_session_refresh_it_once():
    hub = Hub()
    sessions = HubSessions()
    await _call(hub, sessions)
    hub.expire()

    results = await asyncio.gather(*(_call(hub, sessions) for _ in range(20)))

    assert results == [True] * 20
    assert (hub.logins, hub.refreshes) == (1, 1)


async def test_requests_on_one_client_refresh_once():
    hub = Hub()
    async with hub.client(HubSessions()) as client:
        await client.login(USER, PASSWORD)
        hub.expire()
        results = await asyncio.gather(
            *(client.slug_availability("slug") for _ in range(10))
        )

    assert all(r.available for r in results)
    assert hub.refreshes == 1


async def test_client_with_stale_tokens_takes_the_session_s_newer_ones():
    hub = Hub()
    session = HubSession(USER, PASSWORD)
    async with httpx.AsyncClient(base_url=HUB_URL, transport=hub.transport) as http:
        stale = (await session.start(http)).access_token
        hub.expire()
        await session.renew(http, stale)
        assert hub.refreshes == 1

        # A second caller that also saw `stale` rejected does not refresh.
        await session.renew(http, stale)

    assert hub.refreshes == 1
    assert session.tokens == hub.current


async def test_waiters_get_the_first_failure_without_calling_the_hub():
    hub = Hub()
    sessions = HubSessions()
    await _call(hub, sessions)
    hub.expire()
    hub.refresh_status = 503
    hub.login_status = 503

    results = await asyncio.gather(
        *(_call(hub, sessions) for _ in range(20)), return_exceptions=True
    )

    assert all(isinstance(r, ServerError) for r in results)
    assert (hub.logins, hub.refreshes) == (2, 1)

    # A later client makes its own attempt.
    hub.login_status = 200
    assert await _call(hub, sessions)
    assert hub.logins == 3


# --- One connection per hub, kept open between clients ---


async def test_clients_from_one_factory_share_the_connection():
    hub = Hub()
    hub_clients = HubClients(transport=hub.transport)
    async with hub_clients.for_url(HUB_URL) as first:
        await first.login(USER, PASSWORD)

    # Closing the first client left the hub connection open for the second.
    async with hub_clients.for_url(HUB_URL + "/") as second:
        await second.login(USER, PASSWORD)
        assert (await second.slug_availability("slug")).available
        assert second._http is first._http

    await hub_clients.close()
    assert first._http.is_closed


async def test_each_hub_gets_its_own_connection():
    hub_clients = HubClients(transport=Hub().transport)

    first = hub_clients.for_url(HUB_URL)
    other = hub_clients.for_url("https://other-hub.test")

    assert first._http is not other._http
    await hub_clients.close()


async def test_shared_connection_is_dropped_after_fifty_idle_seconds():
    hub_clients = HubClients()
    client = hub_clients.for_url(HUB_URL)

    pool = client._http._transport._pool
    assert pool._keepalive_expiry == 50.0
    await hub_clients.close()


async def test_one_off_client_closes_its_own_connection():
    hub_clients = HubClients()
    shared = hub_clients.for_url(HUB_URL)

    async with hub_clients.one_off(HUB_URL) as client:
        assert client._http is not shared._http

    assert client._http.is_closed
    assert not shared._http.is_closed
    await hub_clients.close()


async def test_a_client_built_on_its_own_closes_its_connection():
    async with SyftHubClient(HUB_URL) as client:
        pass

    assert client._http.is_closed
