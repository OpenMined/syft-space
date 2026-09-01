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

from syft_station.components.shared.email import NormalizedEmail

_HTTP_TIMEOUT_SECONDS = 15.0

_GUEST_SUB = "guest"


class SyftHubAuthError(Exception):
    """Credentials or the station's API token rejected by SyftHub."""


class SyftHubUnavailableError(Exception):
    """SyftHub could not be reached or returned a server error."""


class SyftHubBuyerTokenError(Exception):
    """The buyer's satellite token is invalid, expired, or a guest token."""


class SyftHubSatelliteError(Exception):
    """SyftHub refused to register the station's origin as a satellite."""


class SyftHubGoogleNotLinkedError(Exception):
    """The Google email maps to a SyftHub account not linked to Google.

    SyftHub refuses to implicitly link (409) — the user must sign in with
    their password, or link Google from SyftHub's account settings first.
    """


class SyftHubProfile(BaseModel):
    """Profile from ``GET /api/v1/users/me``."""

    id: int
    username: str
    email: NormalizedEmail
    full_name: str


class Satellite(BaseModel):
    """A satellite row from ``/api/v1/satellites``."""

    id: str
    base_url: str


class VerifiedBuyer(BaseModel):
    """Claims the station bills on, from ``POST /api/v1/verify``."""

    email: NormalizedEmail
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

    async def _google_login(self, client: httpx.AsyncClient, credential: str) -> str:
        """Exchange a Google ID token for a hub access token.

        Sends ``allow_signup=false`` so SyftHub rejects an unknown email
        (401) instead of signing it up — the station admits existing SyftHub
        users only. A 409 means the email exists but isn't Google-linked.
        """
        try:
            response = await client.post(
                "/api/v1/auth/google",
                json={"credential": credential, "allow_signup": False},
            )
        except httpx.HTTPError as e:
            raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

        if response.status_code == 409:
            raise SyftHubGoogleNotLinkedError(
                "This SyftHub account isn't linked to Google"
            )
        if response.status_code == 401:
            detail = None
            try:
                detail = response.json().get("detail")
            except ValueError:
                pass
            if isinstance(detail, dict) and detail.get("code") == "account_not_found":
                raise SyftHubAuthError("No SyftHub account for this Google email")
            raise SyftHubAuthError("Google sign-in was rejected")
        if response.status_code != 200:
            raise SyftHubUnavailableError(
                f"SyftHub Google sign-in failed with status {response.status_code}"
            )

        access_token = response.json().get("access_token")
        if not access_token:
            raise SyftHubUnavailableError("SyftHub login response missing access_token")
        return str(access_token)

    async def authenticate(self, email: str, password: str) -> SyftHubProfile:
        """One-shot credential check: login, fetch profile, discard tokens."""
        async with self._build_http_client() as client:
            access_token = await self._login(client, email, password)
            return await self._fetch_profile(client, access_token)

    async def authenticate_with_google(self, credential: str) -> SyftHubProfile:
        """One-shot Google sign-in: exchange the ID token, fetch profile, discard.

        Existing SyftHub users only (see ``_google_login``).
        """
        async with self._build_http_client() as client:
            access_token = await self._google_login(client, credential)
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

    async def verify_buyer_token(
        self, pat: str, token: str, satellite_id: str | None = None
    ) -> VerifiedBuyer:
        """Verify a buyer's satellite token server-side; return billing claims.

        The hub derives the authorized audience from the PAT owner. Naming
        the station's own satellite narrows that to this station, so a token
        minted for the owner's space cannot be replayed here.
        """
        payload: dict[str, Any] = {"token": token}
        if satellite_id:
            payload["satellite_id"] = satellite_id
        async with self._build_http_client() as client:
            try:
                response = await client.post(
                    "/api/v1/verify",
                    json=payload,
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

    async def register_satellite(
        self, pat: str, base_url: str, kind: str = "station"
    ) -> Satellite:
        """Claim this origin as a satellite of the PAT owner's account.

        Idempotent on the origin, so it is safe to call repeatedly. The
        publish and mint gates ask whether the wallet owner's account holds
        a satellite at the exact credits origin; nothing heartbeats the
        station, so this is the only way one appears.
        """
        async with self._build_http_client() as client:
            try:
                response = await client.post(
                    "/api/v1/satellites",
                    json={"kind": kind, "base_url": base_url},
                    headers={"Authorization": f"Bearer {pat}"},
                )
            except httpx.HTTPError as e:
                raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

        if response.status_code in (401, 403):
            raise SyftHubAuthError("SyftHub rejected the station's API token")
        if response.status_code == 409:
            raise SyftHubSatelliteError(
                f"SyftHub already holds {base_url} under a different kind"
            )
        if response.status_code not in (200, 201):
            raise SyftHubSatelliteError(
                f"SyftHub refused the satellite ({response.status_code})"
            )
        return Satellite.model_validate(response.json())

    async def move_satellite(
        self, pat: str, satellite_id: str, base_url: str
    ) -> Satellite | None:
        """Point the station's satellite at its current origin.

        None when the hub no longer knows the id — the caller registers
        afresh. Moving to the origin it already has is a no-op 200.
        """
        async with self._build_http_client() as client:
            try:
                response = await client.put(
                    f"/api/v1/satellites/{satellite_id}",
                    json={"base_url": base_url},
                    headers={"Authorization": f"Bearer {pat}"},
                )
            except httpx.HTTPError as e:
                raise SyftHubUnavailableError(f"SyftHub is unreachable: {e}") from e

        if response.status_code == 404:
            return None
        if response.status_code in (401, 403):
            raise SyftHubAuthError("SyftHub rejected the station's API token")
        if response.status_code != 200:
            raise SyftHubSatelliteError(
                f"SyftHub refused the move ({response.status_code})"
            )
        return Satellite.model_validate(response.json())
