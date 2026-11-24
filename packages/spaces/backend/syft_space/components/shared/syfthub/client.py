"""SyftHub marketplace API client using httpx."""

from collections.abc import Callable
from typing import Any

import httpx
from loguru import logger

from .errors import (
    ConflictError,
    NotAuthenticatedError,
    SatelliteKindMismatchError,
    SatelliteOriginConflictError,
)
from .responses import _handle_response, _handle_response_raw, _raise_for_status
from .schemas import (
    AccountingResponse,
    RegisterResponse,
    Satellite,
    SatelliteKind,
    SatelliteToken,
    SlugAvailability,
    TokenResponse,
    TunnelCredentialsResponse,
    UserProfile,
    VerifyOTPResponse,
)
from .session import AsyncRefreshTokenAuth, HubSession, HubSessions

# --- Tunables for talking to a hub ---

# Request timeout for hub calls.
DEFAULT_TIMEOUT_SECONDS = 10.0

# A shared connection idle this long is closed. Kept under the hub's own
# idle limit (nginx, 65 s) so we never reuse one the hub is about to close.
KEEPALIVE_EXPIRY_SECONDS = 50.0


class SyftHubClient:
    """Async HTTP client for SyftHub marketplace API with typed requests/responses."""

    def __init__(
        self,
        base_url: str,
        timeout: float | None = None,
        sessions: HubSessions | None = None,
        http: httpx.AsyncClient | None = None,
    ):
        """Initialize SyftHub client.

        Args:
            base_url: Base URL for the SyftHub instance (str)
            timeout: Request timeout in seconds (default: 10.0). Unused
                when ``http`` is given, which has its own.
            sessions: Sessions that login() shares with other clients.
                Defaults to a set of its own (see HubClients).
            http: Connection to the hub that outlives this client and is
                left open by close(). Defaults to one this client owns.
        """
        # Normalize URL (remove trailing slash)
        self.base_url = base_url.rstrip("/")
        self._sessions = sessions if sessions is not None else HubSessions()
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout or DEFAULT_TIMEOUT_SECONDS),
        )
        self._auth: AsyncRefreshTokenAuth | None = None
        self._session: HubSession | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if client has been authenticated."""
        return self._auth is not None

    @property
    def tokens(self) -> TokenResponse | None:
        """Get current tokens (if authenticated)."""
        return self._session.tokens if self._session else None

    async def register(
        self,
        username: str,
        email: str,
        full_name: str,
        password: str,
    ) -> RegisterResponse:
        """
        Register a new user on SyftHub.

        Raises:
            ConflictError: User already exists
            ValidationError: Invalid request data
            ServerError: Server-side error
        """

        payload = {
            "username": username,
            "email": email,
            "full_name": full_name,
            "password": password,
        }

        response = await self._http.post("/api/v1/auth/register", json=payload)
        return _handle_response(response, RegisterResponse)

    async def verify_otp(self, email: str, code: str) -> VerifyOTPResponse:
        """Verify a registration OTP and obtain tokens.

        Raises:
            ValidationError: Invalid/expired code or malformed input
            NotFoundError: No pending verification for this email
            ServerError: Server-side error
        """
        response = await self._http.post(
            "/api/v1/auth/register/verify-otp",
            json={"email": email, "code": code},
        )
        return _handle_response(response, VerifyOTPResponse)

    async def resend_otp(self, email: str) -> None:
        """Request a fresh registration OTP for an unverified email.

        SyftHub intentionally returns a generic success message regardless of
        whether the email exists, so this method does not surface a model.
        """
        response = await self._http.post(
            "/api/v1/auth/register/resend-otp",
            json={"email": email},
        )
        _handle_response_raw(response)

    async def is_username_available(self, username: str) -> bool:
        """
        Check if a username is available.
        Returns:
            True if username is available, False otherwise.
        """
        response = await self._http.get(f"/api/v1/users/check-username/{username}")
        return _handle_response_raw(response)["available"]

    def authenticate_with_tokens(self, access_token: str, refresh_token: str) -> None:
        """Seed the authenticated client from pre-fetched tokens.

        Used when a sibling endpoint (e.g. /auth/register/verify-otp) already
        issued tokens — skips the extra /auth/login round-trip.
        """
        tokens = TokenResponse(access_token=access_token, refresh_token=refresh_token)
        self._install_auth(HubSession(tokens=tokens))

    def _install_auth(self, session: HubSession) -> None:
        """Send this client's authenticated requests as the given session."""
        self._session = session
        self._auth = AsyncRefreshTokenAuth(session, self._http)

    async def login(
        self, username: str, password: str, use_cache: bool = True
    ) -> TokenResponse:
        """
        Login and setup authenticated client.

        Joins the session shared by every client of this (base_url,
        username), logging in only if it has no tokens yet. Expired tokens
        are refreshed on the first 401; if the refresh token is also
        rejected, a full password login runs instead.

        Args:
            username: SyftHub login email
            password: SyftHub password
            use_cache: Share the session with other clients. Pass False to
                force a credential-validating login on a private session.

        Raises:
            AuthenticationError: Invalid credentials
            ValidationError: Invalid request data
            ServerError: Server-side error
        """
        if use_cache:
            session = self._sessions.for_account(self.base_url, username, password)
        else:
            session = HubSession(username, password)
        tokens = await session.start(self._http)
        self._install_auth(session)
        return tokens

    async def accounting_credentials(self) -> AccountingResponse:
        """
        Get accounting credentials for current user.
        Returns:
            AccountingResponse: Accounting credentials for current user.
        Raises:
            NotAuthenticatedError: login() not called
            AuthenticationError: Token invalid/expired
            ValidationError: Invalid request data
            ServerError: Server-side error
        """
        self._require_auth()
        response = await self._request("GET", "/api/v1/users/me/accounting")
        return _handle_response(response, AccountingResponse)

    async def slug_availability(self, slug: str) -> SlugAvailability:
        """Ask the Hub whether a publish under ``slug`` would be accepted.

        The Hub owns the slug rules (length, format, reserved names) and the
        per-user uniqueness, so the answer comes from it rather than from a
        copy of those rules here.
        """
        self._require_auth()
        response = await self._request("GET", f"/api/v1/endpoints/{slug}/availability")
        return _handle_response(response, SlugAvailability)

    async def publish_endpoint(
        self,
        payload: dict[str, Any],
        satellite_id: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        Publish an endpoint to SyftHub.

        Args:
            payload: Endpoint data (structure depends on API version)
            satellite_id: Satellite to attach the endpoint to. A query
                parameter, not a body field — the body schema is reused per
                item inside a sync payload.
            overwrite: Update the endpoint when it already exists. Carries no
                satellite_id: an update never re-homes an endpoint, so only
                the slug's owner may take this path.

        Raises:
            NotAuthenticatedError: login() not called
            AuthenticationError: Token invalid/expired
            ValidationError: Invalid endpoint data
            ConflictError: Endpoint already exists
            ServerError: Server-side error
        """
        self._require_auth()
        response = await self._request(
            "POST",
            "/api/v1/endpoints",
            json=payload,
            params={"satellite_id": satellite_id},
        )

        if overwrite and response.status_code == 400:
            # Endpoint already exists, try to update it
            response = await self._request(
                "PATCH", f"/api/v1/endpoints/slug/{payload['slug']}", json=payload
            )
        return _handle_response_raw(response)

    async def profile(self) -> UserProfile:
        """Get the profile of the current user.
        Returns:
            UserProfile: User profile
        """
        self._require_auth()
        response = await self._request("GET", "/api/v1/users/me")
        return _handle_response(response, UserProfile)

    async def get_tunnel_credentials(self) -> TunnelCredentialsResponse:
        """Get tunnel credentials for current user.

        Returns:
            TunnelCredentialsResponse: Tunnel credentials (auth_token, domain)

        Raises:
            NotAuthenticatedError: login() not called
            AuthenticationError: Token invalid/expired
            ServerError: Server-side error
        """
        self._require_auth()
        response = await self._request("GET", "/api/v1/users/me/tunnel-credentials")
        return _handle_response(response, TunnelCredentialsResponse)

    async def unpublish_endpoint(self, endpoint_slug: str) -> bool:
        """Unpublish an endpoint from SyftHub.

        Args:
            endpoint_slug: Slug of the endpoint

        Returns:
            True if endpoint was unpublished successfully
        """
        self._require_auth()
        response = await self._request(
            "DELETE", f"/api/v1/endpoints/slug/{endpoint_slug}"
        )

        logger.info(
            f"Unpublish endpoint response: {response.status_code}: {response.content}"
        )

        _raise_for_status(response)

        return True

    async def register_satellite(
        self, base_url: str, kind: SatelliteKind = SatelliteKind.SPACE
    ) -> Satellite:
        """Get-or-create the satellite at this origin.

        Idempotent after canonicalisation, so base_url goes over verbatim. A
        *different* origin creates a new satellite — use move_satellite.
        """
        self._require_auth()
        response = await self._request(
            "POST", "/api/v1/satellites", json={"kind": str(kind), "base_url": base_url}
        )
        try:
            return _handle_response(response, Satellite)
        except ConflictError as e:
            raise SatelliteKindMismatchError(
                e.message, status_code=e.status_code, code=e.code, field=e.field
            ) from e

    async def move_satellite(self, satellite_id: str, base_url: str) -> Satellite:
        """Point a satellite at a new origin, keeping its id.

        Endpoints stay attached. Safe to call with the origin it already has:
        self is excluded from the conflict check, so a no-op move is a 200.
        """
        self._require_auth()
        response = await self._request(
            "PUT", f"/api/v1/satellites/{satellite_id}", json={"base_url": base_url}
        )
        try:
            return _handle_response(response, Satellite)
        except ConflictError as e:
            raise SatelliteOriginConflictError(
                e.message, status_code=e.status_code, code=e.code, field=e.field
            ) from e

    async def verify_satellite_token(
        self, token: str, satellite_id: str | None = None
    ) -> SatelliteToken:
        """Verify a satellite token.

        Args:
            token: Satellite token
            satellite_id: Restrict the accepted audience to this satellite.
                Omitted, any satellite the account owns is accepted.
        Returns:
            SatelliteToken: Verify satellite token response
        """
        self._require_auth()
        body: dict[str, Any] = {"token": token}
        if satellite_id:
            body["satellite_id"] = satellite_id
        response = await self._request("POST", "/api/v1/verify", json=body)
        return _handle_response(response, SatelliteToken)

    async def sync_endpoints(
        self, payload: list[dict[str, Any]], satellite_id: str
    ) -> dict[str, Any]:
        """Replace one satellite's endpoint catalogue with this payload.

        SyftHub deletes the satellite's endpoints (plus any not yet attached
        to one) and recreates from the payload; other satellites on the
        account are untouched.

        Args:
            payload: List of endpoints to sync
            satellite_id: Whose catalogue this replaces. Sync carries no URL,
                so SyftHub cannot infer the caller.
        Returns:
            dict[str, Any]: Sync endpoints response
        """
        self._require_auth()
        response = await self._request(
            "POST",
            "/api/v1/endpoints/sync",
            json={"endpoints": payload, "satellite_id": satellite_id},
        )
        return _handle_response_raw(response)

    async def update_endpoint_health(
        self,
        endpoint_health: list[dict[str, Any]],
        ttl_seconds: int,
        public_url: str,
        satellite_id: str,
    ) -> dict[str, Any]:
        """Send endpoint health status to SyftHub.

        Non-destructive: unknown slugs are ignored. Doubles as the liveness
        signal — endpoints go stale once TTL passes with no new report.

        Args:
            endpoint_health: List of {"slug": str, "status": str, "checked_at": str}
            ttl_seconds: Liveness TTL in seconds
            public_url: Resolves the satellite, and moves it if the URL changed
            satellite_id: Addresses the satellite explicitly. Optional to the
                hub today; always sent so it can be made mandatory.
        Returns:
            dict[str, Any]: Health update response
        """
        self._require_auth()
        response = await self._request(
            "POST",
            "/api/v1/endpoints/health",
            json={
                "endpoints": endpoint_health,
                "ttl_seconds": ttl_seconds,
                "url": public_url,
                "satellite_id": satellite_id,
            },
        )
        return _handle_response_raw(response)

    def _require_auth(self) -> None:
        if self._auth is None:
            raise NotAuthenticatedError()

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request as the logged-in account."""
        if self._auth is None:
            raise NotAuthenticatedError()
        return await self._http.request(method, url, auth=self._auth, **kwargs)

    async def close(self) -> None:
        """Close the connection, unless it was passed in."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> "SyftHubClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class HubClients:
    """Builds SyftHubClient instances that share sessions and connections.

    Created once at startup; ``for_url`` is passed to whatever talks to
    the hub. Clients for an account reuse its login session, and clients
    for a hub reuse its open connection instead of reconnecting each time.
    """

    def __init__(
        self,
        sessions: HubSessions | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._sessions = sessions if sessions is not None else HubSessions()
        self._transport = transport
        self._https: dict[str, httpx.AsyncClient] = {}

    def for_url(self, base_url: str) -> SyftHubClient:
        """Return a new client that reuses the connection to this hub."""
        url = base_url.rstrip("/")
        http = self._https.get(url)
        if http is None:
            http = httpx.AsyncClient(
                base_url=url,
                timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS),
                limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY_SECONDS),
                transport=self._transport,
            )
            self._https[url] = http
        return SyftHubClient(url, sessions=self._sessions, http=http)

    def one_off(self, base_url: str) -> SyftHubClient:
        """Return a new client whose connection closes with it.

        For a URL someone typed that is not a saved marketplace, so no
        connection is kept open for it.
        """
        return SyftHubClient(base_url, sessions=self._sessions)

    async def close(self) -> None:
        """Close every connection opened by ``for_url``."""
        https, self._https = self._https, {}
        for http in https.values():
            await http.aclose()


# Builds a client for a hub URL; what handlers are given, not HubClients.
HubClientFactory = Callable[[str], SyftHubClient]
