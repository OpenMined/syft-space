"""Minimal SyftHub client for the sign-in proxy.

The station uses SyftHub purely as an identity provider: it validates the
member's credentials with a one-shot login, fetches the profile, and then
discards the hub tokens — the station issues its own session. This is
deliberately NOT syft-space's full SyftHubClient (zero code coupling).
"""

from typing import Any

import httpx
from pydantic import BaseModel

_HTTP_TIMEOUT_SECONDS = 15.0


class SyftHubAuthError(Exception):
    """Credentials rejected by SyftHub."""


class SyftHubUnavailableError(Exception):
    """SyftHub could not be reached or returned a server error."""


class SyftHubProfile(BaseModel):
    """Profile from ``GET /api/v1/users/me``."""

    username: str
    email: str
    full_name: str


class SyftHubIdentityClient:
    """Validates credentials against SyftHub and fetches the profile."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _build_http_client(self) -> httpx.AsyncClient:
        """Build the HTTP client (seam for tests to inject a MockTransport)."""
        return httpx.AsyncClient(base_url=self.base_url, timeout=_HTTP_TIMEOUT_SECONDS)

    async def authenticate(self, email: str, password: str) -> SyftHubProfile:
        """One-shot credential check: login, fetch profile, discard tokens."""
        async with self._build_http_client() as client:
            try:
                response = await client.post(
                    "/api/v1/auth/login",
                    data={"username": email, "password": password},
                )
            except httpx.HTTPError as e:
                raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

            if response.status_code in (400, 401, 403, 422):
                raise SyftHubAuthError("Invalid SyftHub credentials")
            if response.status_code != 200:
                raise SyftHubUnavailableError(
                    f"SyftHub login failed with status {response.status_code}"
                )

            tokens: dict[str, Any] = response.json()
            access_token = tokens.get("access_token")
            if not access_token:
                raise SyftHubUnavailableError(
                    "SyftHub login response missing access_token"
                )

            try:
                me = await client.get(
                    "/api/v1/users/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            except httpx.HTTPError as e:
                raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

            if me.status_code != 200:
                raise SyftHubUnavailableError(
                    f"SyftHub profile fetch failed with status {me.status_code}"
                )

            return SyftHubProfile.model_validate(me.json())
