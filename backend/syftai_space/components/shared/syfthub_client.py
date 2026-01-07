"""SyftHub marketplace API client using httpx."""

import threading
from typing import Any, TypeVar

import httpx
from loguru import logger
from pydantic import BaseModel, Field

# =============================================================================
# Exceptions
# =============================================================================


class SyftHubError(Exception):
    """Base exception for SyftHub API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(SyftHubError):
    """Invalid credentials or token expired (401)."""

    pass


class ValidationError(SyftHubError):
    """Request validation failed (400, 422)."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message, status_code=422)
        self.errors = errors or []


class ConflictError(SyftHubError):
    """Resource already exists (409)."""

    pass


class NotFoundError(SyftHubError):
    """Resource not found (404)."""

    pass


class ServerError(SyftHubError):
    """Server-side error (5xx)."""

    pass


class NotAuthenticatedError(SyftHubError):
    """Client not authenticated - login() not called."""

    def __init__(self):
        super().__init__("Not authenticated. Call login() first.", status_code=None)


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
    """Response from registration endpoint."""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccountingResponse(BaseModel):
    """Response from accounting endpoint."""

    url: str
    email: str
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


class SatelliteToken(BaseModel):
    """Response from verify satellite token endpoint."""

    valid: bool = Field(..., description="True if token is valid, False otherwise.")
    email: str | None = Field(None, description="Email")
    iat: int | None = Field(None, description="Issued at time")
    exp: int | None = Field(None, description="Expiration time")

    class Config:
        """Pydantic config."""

        from_attributes = True

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.exp is None or self.iat is None:
            return True
        return self.exp < self.iat


# =============================================================================
# Response Handler
# =============================================================================

T = TypeVar("T", bound=BaseModel)


def _extract_error_detail(response: httpx.Response) -> str:
    """Extract error message from response body."""
    try:
        data = response.json()
        if isinstance(data, dict):
            # FastAPI style: {"detail": "message"} or {"detail": [...]}
            detail = data.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, list) and detail:
                # Validation errors: [{"loc": [...], "msg": "...", "type": "..."}]
                messages = [err.get("msg", str(err)) for err in detail]
                return "; ".join(messages)
            # Other formats
            if "message" in data:
                return data["message"]
            if "error" in data:
                return data["error"]
        return response.text[:200] if response.text else response.reason_phrase
    except Exception:
        return response.reason_phrase or f"HTTP {response.status_code}"


def _extract_validation_errors(response: httpx.Response) -> list[dict[str, Any]]:
    """Extract validation error details from response."""
    try:
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("detail"), list):
            return data["detail"]
    except Exception as e:
        logger.error(f"Error extracting validation errors: {e}")
    return []


def _handle_response(response: httpx.Response, model: type[T]) -> T:
    """Handle API response: parse success or raise appropriate exception."""
    if response.is_success:
        return model.model_validate(response.json())

    status = response.status_code
    detail = _extract_error_detail(response)

    if status == 401:
        raise AuthenticationError(detail, status_code=status)
    elif status == 404:
        raise NotFoundError(detail, status_code=status)
    elif status == 409:
        raise ConflictError(detail, status_code=status)
    elif status in (400, 422):
        errors = _extract_validation_errors(response)
        raise ValidationError(detail, errors=errors)
    elif status >= 500:
        raise ServerError(detail, status_code=status)
    else:
        raise SyftHubError(detail, status_code=status)


def _handle_response_raw(response: httpx.Response) -> dict[str, Any]:
    """Handle API response returning raw dict (for dynamic responses)."""
    if response.is_success:
        return response.json()

    status = response.status_code
    detail = _extract_error_detail(response)

    if status == 401:
        raise AuthenticationError(detail, status_code=status)
    elif status == 404:
        raise NotFoundError(detail, status_code=status)
    elif status == 409:
        raise ConflictError(detail, status_code=status)
    elif status in (400, 422):
        errors = _extract_validation_errors(response)
        raise ValidationError(detail, errors=errors)
    elif status >= 500:
        raise ServerError(detail, status_code=status)
    else:
        raise SyftHubError(detail, status_code=status)


# =============================================================================
# Auth Handler
# =============================================================================


class RefreshTokenAuth(httpx.Auth):
    """Auto-refresh auth that handles 401s by refreshing the access token."""

    def __init__(
        self, auth_client: httpx.Client, access_token: str, refresh_token: str
    ):
        self.auth_client = auth_client
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._lock = threading.Lock()

    def _refresh(self) -> None:
        response = self.auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": self.refresh_token},
        )
        tokens = _handle_response(response, TokenResponse)
        self.access_token = tokens.access_token
        self.refresh_token = tokens.refresh_token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        response = yield request
        if response.status_code == 401:
            with self._lock:
                self._refresh()
            request.headers["Authorization"] = f"Bearer {self.access_token}"
            yield request


# =============================================================================
# Client
# =============================================================================


class SyftHubClient:
    """HTTP client for SyftHub marketplace API with typed requests/responses."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._auth_client = httpx.Client(base_url=self.base_url)
        self._client: httpx.Client | None = None
        self._tokens: TokenResponse | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if client has been authenticated."""
        return self._client is not None

    @property
    def tokens(self) -> TokenResponse | None:
        """Get current tokens (if authenticated)."""
        return self._tokens

    def register(
        self,
        username: str,
        email: str,
        full_name: str,
        password: str,
        accounting_service_url: str,
        accounting_password: str,
    ) -> RegisterResponse:
        """
        Register a new user on SyftHub.

        Raises:
            ConflictError: User already exists
            ValidationError: Invalid request data
            ServerError: Server-side error
        """
        response = self._auth_client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": email,
                "full_name": full_name,
                "password": password,
                "accounting_service_url": accounting_service_url,
                "accounting_password": accounting_password,
            },
        )
        return _handle_response(response, RegisterResponse)

    def _is_username_available(self, username: str) -> bool:
        """
        Check if a username is available.
        Returns:
            True if username is available, False otherwise.
        """
        response = self._auth_client.get(f"/api/v1/users/check-username/{username}")
        return _handle_response_raw(response)["available"]

    def login(self, username: str, password: str) -> TokenResponse:
        """
        Login and setup authenticated client.

        Raises:
            AuthenticationError: Invalid credentials
            ValidationError: Invalid request data
            ServerError: Server-side error
        """
        response = self._auth_client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": password},
        )
        tokens = _handle_response(response, TokenResponse)
        self._tokens = tokens

        # Setup authenticated client with auto-refresh
        auth = RefreshTokenAuth(
            auth_client=self._auth_client,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        )
        self._client = httpx.Client(base_url=self.base_url, auth=auth)
        return tokens

    def accounting_credentials(self) -> AccountingResponse:
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
        response = self._client.get("/api/v1/users/me/accounting-credentials")  # type: ignore
        return _handle_response(response, AccountingResponse)

    def publish_endpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Publish an endpoint to SyftHub.

        Args:
            payload: Endpoint data (structure depends on API version)

        Raises:
            NotAuthenticatedError: login() not called
            AuthenticationError: Token invalid/expired
            ValidationError: Invalid endpoint data
            ConflictError: Endpoint already exists
            ServerError: Server-side error
        """
        self._require_auth()
        response = self._client.post("/api/v1/endpoints/", json=payload)  # type: ignore
        return _handle_response_raw(response)

    def profile(self) -> UserProfile:
        """Get the profile of the current user.
        Returns:
            UserProfile: User profile
        """
        self._require_auth()
        response = self._client.get("/api/v1/users/me/")  # type: ignore
        return _handle_response(response, UserProfile)

    def update_profile(
        self,
        domain: str | None = None,
        username: str | None = None,
        email: str | None = None,
        full_name: str | None = None,
    ) -> UserProfile:
        """Update the profile of the current user.
        Args:
            domain: Domain of the current user
            username: Username of the current user
            email: Email of the current user
            full_name: Full name of the current user
        Returns:
            UserProfile: User profile
        """
        self._require_auth()
        payload = {
            "domain": domain,
            "username": username,
            "email": email,
            "full_name": full_name,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        response = self._client.put("api/v1/users/me/", json=payload)  # type: ignore
        return _handle_response(response, UserProfile)

    def verify_satellite_token(self, token: str) -> SatelliteToken:
        """Verify a satellite token.
        Args:
            token: Satellite token
        Returns:
            SatelliteToken: Verify satellite token response
        """
        self._require_auth()
        response = self._client.post("/api/v1/verify", json={"token": token})  # type: ignore
        return _handle_response(response, SatelliteToken)

    def _require_auth(self) -> None:
        if self._client is None:
            raise NotAuthenticatedError()

    def close(self) -> None:
        """Close HTTP clients."""
        self._auth_client.close()
        if self._client:
            self._client.close()

    def __enter__(self) -> "SyftHubClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
