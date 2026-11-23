"""SyftHub marketplace API client using httpx."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, TypeVar
from uuid import UUID

import httpx
from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, EmailStr, Field, HttpUrl

# =============================================================================
# Exceptions
# =============================================================================


class SyftHubError(Exception):
    """Base exception for SyftHub API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str | None = None,
        field: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.field = field
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException.

        When the upstream error carries a structured ``code`` (e.g.
        ``EMAIL_NOT_VERIFIED``), surface it as a dict so the frontend can
        branch on it. Otherwise fall back to the historical string detail so
        existing error toasts keep rendering unchanged.
        """
        if self.code is None and self.field is None:
            return HTTPException(status_code=self.status_code, detail=self.message)

        detail: dict[str, Any] = {"message": self.message}
        if self.code is not None:
            detail["code"] = self.code
        if self.field is not None:
            detail["field"] = self.field
        return HTTPException(status_code=self.status_code, detail=detail)


class AuthenticationError(SyftHubError):
    """Invalid credentials or token expired (401)."""

    pass


class ForbiddenError(SyftHubError):
    """Access forbidden (403)."""

    pass


class NotFoundError(SyftHubError):
    """Resource not found (404)."""

    pass


class ConflictError(SyftHubError):
    """Resource already exists (409)."""

    pass


class ValidationError(SyftHubError):
    """Request validation failed (400, 422)."""

    def __init__(
        self,
        message: str,
        status_code: int = 422,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message, status_code=status_code, code=code)
        self.errors = errors or []


class SatelliteKindMismatchError(ConflictError):
    """409 - the origin is registered as the other kind. Needs an operator."""

    pass


class SatelliteOriginConflictError(ConflictError):
    """409 - another satellite on this account already serves that origin."""

    pass


class SatelliteRequiredError(ValidationError):
    """422 - the account runs 2+ spaces and the call named no satellite."""

    def __init__(
        self,
        message: str,
        status_code: int = 422,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        count: int | None = None,
    ):
        super().__init__(message, status_code=status_code, code=code, errors=errors)
        self.count = count


class FailedDependencyError(SyftHubError):
    """Failed dependency - accounting service issue (424)."""

    pass


class RateLimitError(SyftHubError):
    """Rate limited by SyftHub (429) - callers should back off, not retry."""

    pass


class ServerError(SyftHubError):
    """Server-side error (5xx) - covers 500, 502, 503, 504, etc."""

    pass


class NotAuthenticatedError(SyftHubError):
    """Client not authenticated - login() not called."""

    def __init__(self):
        super().__init__("Not authenticated. Call login() first.", status_code=401)


# =============================================================================
# Response Schemas
# =============================================================================


class SlugAvailability(BaseModel):
    """The Hub's answer to "could I publish under this slug right now?"."""

    available: bool
    reason: str | None = None  # why not, for a person; None when available


class TokenResponse(BaseModel):
    """Response from login/refresh endpoints."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User information from registration."""

    username: str
    email: str
    full_name: str


class RegisterResponse(BaseModel):
    """Response from registration endpoint.

    When SyftHub has SMTP configured, registration becomes a two-step flow:
    tokens come back null and ``requires_email_verification`` is True. The
    client must then call ``/auth/register/verify-otp`` with the code emailed
    to the user before tokens are issued.
    """

    user: UserResponse
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    requires_email_verification: bool = False


class VerifyOTPResponse(BaseModel):
    """Response from /auth/register/verify-otp on SyftHub."""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccountingResponse(BaseModel):
    """Response from accounting endpoint."""

    url: HttpUrl
    email: EmailStr
    password: str


class EndpointResponse(BaseModel):
    """Response from publish endpoint."""

    id: str
    name: str
    # Add other fields as needed

    model_config = {"extra": "allow"}


class UserProfile(BaseModel):
    """User profile from SyftHub."""

    username: str = Field(..., description="Username")
    email: str = Field(..., description="Login email")
    full_name: str = Field(..., description="Full name")
    password: str | None = Field(None, description="Login password")
    domain: str | None = Field(None, description="Domain")


class SatelliteKind(StrEnum):
    """What a satellite serves. The hub matches on origin alone; this is a label."""

    SPACE = "space"
    STATION = "station"


class Satellite(BaseModel):
    """A marketplace registry row for one origin owned by one account."""

    id: UUID
    kind: SatelliteKind
    base_url: str = Field(
        ...,
        description="Origin, canonicalised by the marketplace. Not a URL type: "
        "`tunneling:<username>` is legal here",
    )
    last_seen_at: datetime | None = None
    created_at: datetime | None = None


class SatelliteToken(BaseModel):
    """Response from verify satellite token endpoint."""

    valid: bool = Field(..., description="True if token is valid, False otherwise.")
    email: EmailStr | None = Field(None, description="User email")
    iat: int | None = Field(None, description="Issued at time")
    exp: int | None = Field(None, description="Expiration time")
    aud: str | None = Field(None, description="Satellite the token was minted for")
    sub: str | None = Field(None, description="Subject; 'guest' for guest tokens")
    username: str | None = None
    role: str | None = None
    error: str | None = Field(None, description="Failure kind when valid is False")
    message: str | None = None

    class Config:
        """Pydantic config."""

        from_attributes = True

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.exp is None or self.iat is None:
            return True
        return self.exp < self.iat


class TunnelCredentialsResponse(BaseModel):
    """Response from tunnel credentials endpoint."""

    auth_token: str = Field(..., description="Ngrok authentication token")
    domain: str = Field(..., description="Ngrok tunnel domain")


# =============================================================================
# Response Handler
# =============================================================================

T = TypeVar("T", bound=BaseModel)


@dataclass
class ParsedError:
    """Parsed error response from SyftHub."""

    message: str
    code: str | None = None
    field: str | None = None
    count: int | None = None


def _parse_error_response(response: httpx.Response) -> ParsedError:
    """Parse SyftHub error response into structured format.

    Handles patterns:
    1. {"detail": {"code/error": "...", "message": "...", ...}} - Structured
    2. {"detail": "string"} - Simple string
    3. {"detail": [...]} - Validation errors
    """
    try:
        data = response.json()
    except Exception:
        return ParsedError(
            message=response.reason_phrase or f"HTTP {response.status_code}"
        )

    detail = data.get("detail") if isinstance(data, dict) else None

    # Pattern 1: Structured dict
    if isinstance(detail, dict):
        count = detail.get("count")
        return ParsedError(
            message=detail.get("message", str(detail)),
            code=detail.get("code") or detail.get("error"),  # Handle both formats
            field=detail.get("field"),
            count=count if isinstance(count, int) else None,
        )

    # Pattern 2: Simple string
    if isinstance(detail, str):
        return ParsedError(message=detail)

    # Pattern 3: Validation errors array (FastAPI/pydantic shape). Keep the
    # field name so a publisher learns *which* value was rejected.
    if isinstance(detail, list):
        return ParsedError(
            message="; ".join(_describe_validation_error(e) for e in detail)
        )

    return ParsedError(
        message=response.text[:200] if response.text else response.reason_phrase or ""
    )


def _describe_validation_error(err: Any) -> str:
    """``{"loc": ["body", "description"], "msg": "..."}`` -> ``description: ...``."""
    if not isinstance(err, dict):
        return str(err)
    msg = err.get("msg", str(err))
    loc = [
        str(part)
        for part in err.get("loc", ())
        if part not in ("body", "query", "path")
    ]
    return f"{'.'.join(loc)}: {msg}" if loc else msg


def _extract_validation_errors(response: httpx.Response) -> list[dict[str, Any]]:
    """Extract validation error details from response."""
    try:
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("detail"), list):
            return data["detail"]
    except Exception as e:
        logger.exception(f"Error extracting validation errors: {e}")
    return []


def _raise_for_status(response: httpx.Response) -> None:
    """Raise appropriate exception based on response status code."""
    parsed = _parse_error_response(response)
    status = response.status_code

    # Ties a failure here to the hub-side request that produced it.
    correlation_id = response.headers.get("X-Correlation-ID")
    if correlation_id:
        logger.warning(
            f"SyftHub error {status} on {response.request.method} "
            f"{response.request.url.path} "
            f"(code={parsed.code}, correlation_id={correlation_id})"
        )

    if status == 400:
        raise ValidationError(parsed.message, status_code=status, code=parsed.code)
    elif status == 401:
        raise AuthenticationError(parsed.message, status_code=status, code=parsed.code)
    elif status == 403:
        raise ForbiddenError(parsed.message, status_code=status, code=parsed.code)
    elif status == 404:
        raise NotFoundError(parsed.message, status_code=status, code=parsed.code)
    elif status == 409:
        raise ConflictError(
            parsed.message, status_code=status, code=parsed.code, field=parsed.field
        )
    elif status == 422:
        errors = _extract_validation_errors(response)
        if parsed.count is not None:
            # `count` is carried only by the ambiguous-satellite error.
            raise SatelliteRequiredError(
                parsed.message,
                status_code=status,
                code=parsed.code,
                errors=errors,
                count=parsed.count,
            )
        raise ValidationError(
            parsed.message, status_code=status, code=parsed.code, errors=errors
        )
    elif status == 424:
        raise FailedDependencyError(
            parsed.message, status_code=status, code=parsed.code
        )
    elif status == 429:
        raise RateLimitError(parsed.message, status_code=status, code=parsed.code)
    elif status >= 500:
        raise ServerError(parsed.message, status_code=status, code=parsed.code)
    else:
        raise SyftHubError(parsed.message, status_code=status, code=parsed.code)


def _handle_response(response: httpx.Response, model: type[T]) -> T:
    """Handle API response: parse success or raise appropriate exception."""
    if response.is_success:
        try:
            return model.model_validate(response.json())
        except ValueError as exc:
            # A 2xx with a body this client cannot read - a proxy error page,
            # a truncated response - is a hub failure, not a success.
            raise ServerError(f"Unreadable response from SyftHub: {exc}") from exc

    _raise_for_status(response)
    # This line is never reached but helps type checker
    raise AssertionError("Unreachable")


def _handle_response_raw(response: httpx.Response) -> dict[str, Any]:
    """Handle API response returning raw dict (for dynamic responses)."""
    if response.is_success:
        try:
            return response.json()
        except ValueError as exc:
            raise ServerError(f"Unreadable response from SyftHub: {exc}") from exc

    _raise_for_status(response)
    # This line is never reached but helps type checker
    raise AssertionError("Unreachable")


# =============================================================================
# Auth Handler
# =============================================================================


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


# Sessions shared by all clients in the process.
_default_sessions = HubSessions()


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


# =============================================================================
# Client
# =============================================================================


class SyftHubClient:
    """Async HTTP client for SyftHub marketplace API with typed requests/responses."""

    # Default timeout for HTTP requests (10 seconds)
    DEFAULT_TIMEOUT = 10.0

    def __init__(
        self,
        base_url: str,
        timeout: float | None = None,
        sessions: HubSessions | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """Initialize SyftHub client.

        Args:
            base_url: Base URL for the SyftHub instance (str)
            timeout: Request timeout in seconds (default: 10.0)
            sessions: Sessions that login() shares between clients. Defaults
                to the process-wide set.
            transport: httpx transport for both HTTP clients (tests).
        """
        # Normalize URL (remove trailing slash)
        self.base_url = base_url.rstrip("/")
        self._sessions = sessions if sessions is not None else _default_sessions
        self._timeout = httpx.Timeout(timeout or self.DEFAULT_TIMEOUT)
        self._transport = transport
        self._auth_client = httpx.AsyncClient(
            base_url=self.base_url, timeout=self._timeout, transport=transport
        )
        self._client: httpx.AsyncClient | None = None
        self._session: HubSession | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if client has been authenticated."""
        return self._client is not None

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

        response = await self._auth_client.post("/api/v1/auth/register", json=payload)
        return _handle_response(response, RegisterResponse)

    async def verify_otp(self, email: str, code: str) -> VerifyOTPResponse:
        """Verify a registration OTP and obtain tokens.

        Raises:
            ValidationError: Invalid/expired code or malformed input
            NotFoundError: No pending verification for this email
            ServerError: Server-side error
        """
        response = await self._auth_client.post(
            "/api/v1/auth/register/verify-otp",
            json={"email": email, "code": code},
        )
        return _handle_response(response, VerifyOTPResponse)

    async def resend_otp(self, email: str) -> None:
        """Request a fresh registration OTP for an unverified email.

        SyftHub intentionally returns a generic success message regardless of
        whether the email exists, so this method does not surface a model.
        """
        response = await self._auth_client.post(
            "/api/v1/auth/register/resend-otp",
            json={"email": email},
        )
        _handle_response_raw(response)

    async def _is_username_available(self, username: str) -> bool:
        """
        Check if a username is available.
        Returns:
            True if username is available, False otherwise.
        """
        response = await self._auth_client.get(
            f"/api/v1/users/check-username/{username}"
        )
        return _handle_response_raw(response)["available"]

    def authenticate_with_tokens(self, access_token: str, refresh_token: str) -> None:
        """Seed the authenticated client from pre-fetched tokens.

        Used when a sibling endpoint (e.g. /auth/register/verify-otp) already
        issued tokens — skips the extra /auth/login round-trip.
        """
        tokens = TokenResponse(access_token=access_token, refresh_token=refresh_token)
        self._install_auth(HubSession(tokens=tokens))

    def _install_auth(self, session: HubSession) -> None:
        """Build the authenticated client around the given session."""
        self._session = session
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=AsyncRefreshTokenAuth(session, self._auth_client),
            timeout=self._timeout,
            transport=self._transport,
        )

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
        tokens = await session.start(self._auth_client)
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
        response = await self._client.get("/api/v1/users/me/accounting")  # type: ignore
        return _handle_response(response, AccountingResponse)

    async def slug_availability(self, slug: str) -> SlugAvailability:
        """Ask the Hub whether a publish under ``slug`` would be accepted.

        The Hub owns the slug rules (length, format, reserved names) and the
        per-user uniqueness, so the answer comes from it rather than from a
        copy of those rules here.
        """
        self._require_auth()
        response = await self._client.get(  # type: ignore[union-attr]
            f"/api/v1/endpoints/{slug}/availability"
        )
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
        response = await self._client.post(  # type: ignore[union-attr]
            "/api/v1/endpoints",
            json=payload,
            params={"satellite_id": satellite_id},
        )

        if overwrite and response.status_code == 400:
            # Endpoint already exists, try to update it
            response = await self._client.patch(
                f"/api/v1/endpoints/slug/{payload['slug']}", json=payload
            )  # type: ignore
        return _handle_response_raw(response)

    async def profile(self) -> UserProfile:
        """Get the profile of the current user.
        Returns:
            UserProfile: User profile
        """
        self._require_auth()
        response = await self._client.get("/api/v1/users/me")  # type: ignore
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
        response = await self._client.get("/api/v1/users/me/tunnel-credentials")  # type: ignore
        return _handle_response(response, TunnelCredentialsResponse)

    async def unpublish_endpoint(self, endpoint_slug: str) -> bool:
        """Unpublish an endpoint from SyftHub.

        Args:
            endpoint_slug: Slug of the endpoint

        Returns:
            True if endpoint was unpublished successfully
        """
        self._require_auth()
        response = await self._client.delete(f"/api/v1/endpoints/slug/{endpoint_slug}")  # type: ignore

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
        response = await self._client.post(  # type: ignore[union-attr]
            "/api/v1/satellites", json={"kind": str(kind), "base_url": base_url}
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
        response = await self._client.put(  # type: ignore[union-attr]
            f"/api/v1/satellites/{satellite_id}", json={"base_url": base_url}
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
        response = await self._client.post("/api/v1/verify", json=body)  # type: ignore
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
        response = await self._client.post(  # type: ignore[union-attr]
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
        response = await self._client.post(  # type: ignore[union-attr]
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
        if self._client is None:
            raise NotAuthenticatedError()

    async def close(self) -> None:
        """Close HTTP clients."""
        await self._auth_client.aclose()
        if self._client:
            await self._client.aclose()

    async def __aenter__(self) -> "SyftHubClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
