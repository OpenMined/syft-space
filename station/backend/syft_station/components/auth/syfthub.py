"""Minimal SyftHub client for the sign-in proxy and the credits identity.

The station uses SyftHub purely as an identity provider: it validates the
member's credentials with a one-shot login, fetches the profile, and then
discards the hub tokens — the station issues its own session. For the credits
wallet it additionally holds a PAT (API token) minted the same one-shot way,
used to verify buyers' satellite tokens server-side. This is deliberately NOT
syft-space's full SyftHubClient (zero code coupling).
"""

from typing import Any

import httpx
from pydantic import BaseModel

_HTTP_TIMEOUT_SECONDS = 15.0

_GUEST_SUB = "guest"


class SyftHubAuthError(Exception):
    """Credentials or the station's API token rejected by SyftHub."""


class SyftHubUnavailableError(Exception):
    """SyftHub could not be reached or returned a server error."""


class SyftHubBuyerTokenError(Exception):
    """The buyer's satellite token is invalid, expired, or a guest token."""


class SyftHubProfile(BaseModel):
    """Profile from ``GET /api/v1/users/me``."""

    id: int
    username: str
    email: str
    full_name: str


class VerifiedBuyer(BaseModel):
    """Claims the station bills on, from ``POST /api/v1/verify``."""

    email: str
    exp: int | None = None


class SyftHubIdentityClient:
    """Validates credentials against SyftHub and fetches the profile."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _build_http_client(self) -> httpx.AsyncClient:
        """Build the HTTP client (seam for tests to inject a MockTransport)."""
        return httpx.AsyncClient(base_url=self.base_url, timeout=_HTTP_TIMEOUT_SECONDS)

    async def _login(self, client: httpx.AsyncClient, email: str, password: str) -> str:
        """Exchange credentials for a short-lived hub access token."""
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
            raise SyftHubUnavailableError("SyftHub login response missing access_token")
        return str(access_token)

    async def _fetch_profile(
        self, client: httpx.AsyncClient, bearer_token: str
    ) -> SyftHubProfile:
        """Fetch ``/users/me`` with any bearer credential (session token or PAT)."""
        try:
            me = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
        except httpx.HTTPError as e:
            raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

        if me.status_code == 401:
            raise SyftHubAuthError("SyftHub rejected the token")
        if me.status_code != 200:
            raise SyftHubUnavailableError(
                f"SyftHub profile fetch failed with status {me.status_code}"
            )

        return SyftHubProfile.model_validate(me.json())

    async def authenticate(self, email: str, password: str) -> SyftHubProfile:
        """One-shot credential check: login, fetch profile, discard tokens."""
        async with self._build_http_client() as client:
            access_token = await self._login(client, email, password)
            return await self._fetch_profile(client, access_token)

    async def mint_pat(
        self, email: str, password: str, *, label: str = "Syft Station credits"
    ) -> str:
        """One-shot PAT mint: login, create an API token, discard the session.

        The PAT is write-scoped (the hub gates scopes by HTTP method, and
        ``POST /verify`` counts as a write) and never expires. Rotation is
        minting a replacement here; old PATs stay valid until revoked from
        the hub's own token list. The full token value is returned only by
        this call — the hub never shows it again.
        """
        async with self._build_http_client() as client:
            access_token = await self._login(client, email, password)
            try:
                response = await client.post(
                    "/api/v1/auth/tokens",
                    json={"name": label, "scopes": ["write"]},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            except httpx.HTTPError as e:
                raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

            if response.status_code == 400:
                raise SyftHubAuthError(
                    "SyftHub refused to mint an API token (token limit reached?)"
                )
            if response.status_code != 201:
                raise SyftHubUnavailableError(
                    f"SyftHub token mint failed with status {response.status_code}"
                )

            pat = response.json().get("token")
            if not pat:
                raise SyftHubUnavailableError(
                    "SyftHub token mint response missing token"
                )
            return str(pat)

    async def whoami(self, pat: str) -> SyftHubProfile:
        """Resolve the PAT owner's profile (id is the published wallet owner)."""
        async with self._build_http_client() as client:
            return await self._fetch_profile(client, pat)

    async def verify_buyer_token(self, pat: str, token: str) -> VerifiedBuyer:
        """Verify a buyer's satellite token server-side; return billing claims.

        The hub derives the authorized audience from the PAT owner, so this
        can only verify tokens minted for the station's own wallet owner.
        """
        async with self._build_http_client() as client:
            try:
                response = await client.post(
                    "/api/v1/verify",
                    json={"token": token},
                    headers={"Authorization": f"Bearer {pat}"},
                )
            except httpx.HTTPError as e:
                raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

            if response.status_code in (401, 403):
                raise SyftHubAuthError("SyftHub rejected the station's API token")
            if response.status_code != 200:
                raise SyftHubUnavailableError(
                    f"SyftHub verify failed with status {response.status_code}"
                )

            result: dict[str, Any] = response.json()
            if not result.get("valid"):
                raise SyftHubBuyerTokenError(
                    str(result.get("message") or "Invalid satellite token")
                )
            if result.get("sub") == _GUEST_SUB:
                raise SyftHubBuyerTokenError("Guest tokens cannot buy credits")
            email = result.get("email")
            if not email:
                raise SyftHubBuyerTokenError("Token missing email claim")
            return VerifiedBuyer(email=str(email), exp=result.get("exp"))
