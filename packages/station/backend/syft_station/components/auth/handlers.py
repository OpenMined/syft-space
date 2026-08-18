"""Auth handler — SyftHub sign-in proxy with role routing."""

from fastapi import HTTPException, status

from syft_station.components.auth.schemas import AuthConfigResponse
from syft_station.components.auth.session import ROLE_ADMIN, ROLE_MEMBER, SessionUser
from syft_station.components.auth.syfthub import (
    SyftHubAuthError,
    SyftHubGoogleNotLinkedError,
    SyftHubIdentityClient,
    SyftHubProfile,
    SyftHubUnavailableError,
)
from syft_station.config import app_settings


class AuthHandler:
    """Validates credentials against SyftHub and builds the session user."""

    def __init__(self, syfthub_client: SyftHubIdentityClient):
        self.syfthub_client = syfthub_client

    def auth_config(self) -> AuthConfigResponse:
        """Public sign-in config for the frontend (which sign-in methods exist).

        Google is offered only when a client ID is configured.
        """
        client_id = app_settings.google_client_id
        return AuthConfigResponse(
            google_enabled=bool(client_id),
            google_client_id=client_id,
        )

    async def login(self, email: str, password: str) -> SessionUser:
        try:
            profile = await self.syfthub_client.authenticate(email, password)
        except SyftHubAuthError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            ) from e
        except SyftHubUnavailableError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SyftHub is unavailable — try again shortly",
            ) from e

        return self._to_session_user(profile)

    async def login_with_google(self, credential: str) -> SessionUser:
        try:
            profile = await self.syfthub_client.authenticate_with_google(credential)
        except SyftHubGoogleNotLinkedError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This SyftHub account isn't linked to Google. Sign in with "
                    "your password, or link Google in SyftHub first."
                ),
            ) from e
        except SyftHubAuthError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e) or "Google sign-in failed",
            ) from e
        except SyftHubUnavailableError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SyftHub is unavailable — try again shortly",
            ) from e

        return self._to_session_user(profile)

    def _to_session_user(self, profile: SyftHubProfile) -> SessionUser:
        """Map a verified SyftHub profile to the session user, deciding the role.

        Role = admin iff the (normalized) email is the configured admin email;
        the sign-in method doesn't matter.
        """
        role = (
            ROLE_ADMIN
            if app_settings.admin_email
            and profile.email == app_settings.admin_email.lower()
            else ROLE_MEMBER
        )
        return SessionUser(
            email=profile.email,
            username=profile.username,
            name=profile.full_name,
            role=role,
        )
