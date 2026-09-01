"""SyftHub marketplace API client using httpx."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
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

    # Pattern 3: Validation errors array
    if isinstance(detail, list):
        messages = [err.get("msg", str(err)) for err in detail]
        return ParsedError(message="; ".join(messages))

    return ParsedError(
        message=response.text[:200] if response.text else response.reason_phrase or ""
    )


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
        return model.model_validate(response.json())

    _raise_for_status(response)
    # This line is never reached but helps type checker
    raise AssertionError("Unreachable")


def _handle_response_raw(response: httpx.Response) -> dict[str, Any]:
    """Handle API response returning raw dict (for dynamic responses)."""
    if response.is_success:
        return response.json()

    _raise_for_status(response)
    # This line is never reached but helps type checker
    raise AssertionError("Unreachable")


# =============================================================================
# Auth Handler
# =============================================================================


class TokenCache:
    """Process-wide SyftHub session store, keyed by (base_url, username).

    Lets short-lived SyftHubClient instances (heartbeats, per-request auth)
    reuse sessions instead of hitting /auth/login — the most expensive and
    rate-limited endpoint — on every instantiation.
    """

    def __init__(self) -> None:
        self._tokens: dict[tuple[str, str], TokenResponse] = {}

    def get(self, base_url: str, username: str) -> TokenResponse | None:
        """Return the cached session for this identity, if any."""
        return self._tokens.get((base_url, username))

    def put(self, base_url: str, username: str, tokens: TokenResponse) -> None:
        """Store (or replace) the session for this identity."""
        self._tokens[(base_url, username)] = tokens

    def evict(self, base_url: str, username: str) -> None:
        """Drop the session for this identity so it can't be reused."""
        self._tokens.pop((base_url, username), None)

    def clear(self) -> None:
        """Drop all cached sessions (forces fresh logins)."""
        self._tokens.clear()


# Default cache shared by all clients in the process.
_default_token_cache = TokenCache()


class AsyncRefreshTokenAuth(httpx.Auth):
    """Auto-refresh auth that handles 401s by refreshing the access token."""

    requires_response_body = True

    def __init__(
        self,
        auth_client: httpx.AsyncClient,
        access_token: str,
        refresh_token: str,
        on_tokens_updated: Callable[[TokenResponse], None] | None = None,
        relogin: Callable[[], Awaitable[TokenResponse]] | None = None,
    ):
        self.auth_client = auth_client
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._on_tokens_updated = on_tokens_updated
        self._relogin = relogin
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        try:
            response = await self.auth_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": self.refresh_token},
            )
            tokens = _handle_response(response, TokenResponse)
        except SyftHubError:
            # Refresh token rejected (e.g. expired cached session) — fall
            # back to a full password login when credentials are available.
            if self._relogin is None:
                raise
            tokens = await self._relogin()
        self.access_token = tokens.access_token
        self.refresh_token = tokens.refresh_token
        if self._on_tokens_updated is not None:
            self._on_tokens_updated(tokens)

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        response = yield request
        if response.status_code == 401:
            async with self._lock:
                await self._refresh()
            request.headers["Authorization"] = f"Bearer {self.access_token}"
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
        token_cache: TokenCache | None = None,
    ):
        """Initialize SyftHub client.

        Args:
            base_url: Base URL for the SyftHub instance (str)
            timeout: Request timeout in seconds (default: 10.0)
            token_cache: Session cache consulted by login(). Defaults to the
                process-wide cache shared by all clients.
        """
        # Normalize URL (remove trailing slash)
        self.base_url = base_url.rstrip("/")
        self._token_cache = (
            token_cache if token_cache is not None else _default_token_cache
        )
        self._timeout = httpx.Timeout(timeout or self.DEFAULT_TIMEOUT)
        self._auth_client = httpx.AsyncClient(
            base_url=self.base_url, timeout=self._timeout
        )
        self._client: httpx.AsyncClient | None = None
        self._tokens: TokenResponse | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if client has been authenticated."""
        return self._client is not None

    @property
    def tokens(self) -> TokenResponse | None:
        """Get current tokens (if authenticated)."""
        return self._tokens

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
        self._install_auth(
            TokenResponse(access_token=access_token, refresh_token=refresh_token)
        )

    def _install_auth(
        self,
        tokens: TokenResponse,
        on_tokens_updated: Callable[[TokenResponse], None] | None = None,
        relogin: Callable[[], Awaitable[TokenResponse]] | None = None,
    ) -> None:
        """Build the authenticated client around the given tokens."""
        self._tokens = tokens
        auth = AsyncRefreshTokenAuth(
            auth_client=self._auth_client,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            on_tokens_updated=on_tokens_updated,
            relogin=relogin,
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url, auth=auth, timeout=self._timeout
        )

    async def _password_login(self, username: str, password: str) -> TokenResponse:
        """POST credentials to /auth/login and return fresh tokens."""
        response = await self._auth_client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": password},
        )
        return _handle_response(response, TokenResponse)

    async def _relogin(self, username: str, password: str) -> TokenResponse:
        """Full password login used as refresh fallback.

        Evicts the cached session on failure so a dead token can't be
        served to subsequent clients.
        """
        try:
            return await self._password_login(username, password)
        except SyftHubError:
            self._token_cache.evict(self.base_url, username)
            raise

    async def login(
        self, username: str, password: str, use_cache: bool = True
    ) -> TokenResponse:
        """
        Login and setup authenticated client.

        Reuses the token cache's session for this (base_url, username)
        when available, skipping the /auth/login round-trip. An expired
        cached session is refreshed transparently on first 401; if the
        refresh token is also rejected, a full password login runs instead.

        Args:
            username: SyftHub login email
            password: SyftHub password
            use_cache: Reuse/populate the token cache. Pass False to force
                a credential-validating login.

        Raises:
            AuthenticationError: Invalid credentials
            ValidationError: Invalid request data
            ServerError: Server-side error
        """

        def _cache_tokens(tokens: TokenResponse) -> None:
            self._tokens = tokens
            self._token_cache.put(self.base_url, username, tokens)

        async def _relogin_fallback() -> TokenResponse:
            return await self._relogin(username, password)

        if use_cache:
            cached = self._token_cache.get(self.base_url, username)
            if cached is not None:
                self._install_auth(
                    cached, on_tokens_updated=_cache_tokens, relogin=_relogin_fallback
                )
                return cached

        tokens = await self._password_login(username, password)
        if use_cache:
            self._token_cache.put(self.base_url, username, tokens)
            self._install_auth(
                tokens, on_tokens_updated=_cache_tokens, relogin=_relogin_fallback
            )
        else:
            self._install_auth(tokens)
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

    async def endpoint_exists(self, slug: str) -> bool:
        """Check if an endpoint exists on SyftHub.
        Args:
            slug: Slug of the endpoint
        Returns:
            True if endpoint exists, False otherwise.
        """
        self._require_auth()
        response = await self._client.get(f"/api/v1/endpoints/{slug}/exists")  # type: ignore
        return _handle_response_raw(response)

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
