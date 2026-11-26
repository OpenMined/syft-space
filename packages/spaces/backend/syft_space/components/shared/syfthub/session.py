"""SyftHub login sessions shared between clients."""

import asyncio
from collections.abc import AsyncGenerator

import httpx

from .errors import NotAuthenticatedError, SyftHubError
from .responses import _handle_response
from .schemas import TokenResponse


class HubSession:
    """One account's login on one hub, shared by every client that uses it.

    A login or refresh runs once for all concurrent callers: those that
    waited take the new tokens, or the error the first caller got.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        tokens: TokenResponse | None = None,
    ) -> None:
        self.tokens = tokens
        self.username = username
        self.password = password
        self._lock = asyncio.Lock()
        self._error: Exception | None = None

    @property
    def access_token(self) -> str:
        """The token to send; raises if the session has none."""
        if self.tokens is None:
            raise NotAuthenticatedError()
        return self.tokens.access_token

    async def start(self, http: httpx.AsyncClient) -> TokenResponse:
        """Log in unless the session already has tokens."""
        if self.tokens is not None:
            return self.tokens
        return await self._replace_tokens(http, used_access_token=None)

    async def renew(self, http: httpx.AsyncClient, used_access_token: str) -> None:
        """Replace tokens the hub rejected, unless another caller already did."""
        await self._replace_tokens(http, used_access_token)

    async def _replace_tokens(
        self, http: httpx.AsyncClient, used_access_token: str | None
    ) -> TokenResponse:
        waited = self._lock.locked()
        async with self._lock:
            if self.tokens is not None and (
                self.tokens.access_token != used_access_token
            ):
                return self.tokens
            # The caller we waited for failed: fail the same way, no new call.
            if waited and self._error is not None:
                raise self._error
            self._error = None
            try:
                self.tokens = await self._fetch_tokens(http)
            except (SyftHubError, httpx.HTTPError) as error:
                self._error = error
                raise
            return self.tokens

    async def _fetch_tokens(self, http: httpx.AsyncClient) -> TokenResponse:
        """Refresh the tokens; log in if there are none or the hub refuses."""
        if self.tokens is not None:
            try:
                response = await http.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": self.tokens.refresh_token},
                )
                return _handle_response(response, TokenResponse)
            except SyftHubError:
                if self.password is None:
                    raise
        if self.username is None or self.password is None:
            raise NotAuthenticatedError()
        try:
            response = await http.post(
                "/api/v1/auth/login",
                data={"username": self.username, "password": self.password},
            )
            return _handle_response(response, TokenResponse)
        except SyftHubError:
            # Drop the dead tokens so the next client starts with a login.
            self.tokens = None
            raise


class HubSessions:
    """Process-wide sessions, keyed by (base_url, username).

    Lets short-lived SyftHubClient instances (heartbeats, per-request auth)
    share one session instead of hitting /auth/login — the most expensive
    and rate-limited endpoint — on every instantiation.
    """

    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], HubSession] = {}

    def for_account(self, base_url: str, username: str, password: str) -> HubSession:
        """Return this account's shared session, creating it on first use."""
        session = self._sessions.get((base_url, username))
        if session is None:
            session = HubSession(username, password)
            self._sessions[(base_url, username)] = session
        # Later logins use the password given most recently.
        session.password = password
        return session

    def clear(self) -> None:
        """Drop all sessions (forces fresh logins)."""
        self._sessions.clear()


class AsyncRefreshTokenAuth(httpx.Auth):
    """Sends the session's access token; on a 401, renews it and retries."""

    requires_response_body = True

    def __init__(self, session: HubSession, http: httpx.AsyncClient):
        self._session = session
        self._http = http

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        used = self._session.access_token
        request.headers["Authorization"] = f"Bearer {used}"
        response = yield request
        if response.status_code == 401:
            await self._session.renew(self._http, used)
            token = self._session.access_token
            request.headers["Authorization"] = f"Bearer {token}"
            yield request
