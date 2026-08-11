"""Auth handler — SyftHub sign-in proxy with role routing."""

from fastapi import HTTPException, status

from syft_station.components.auth.session import ROLE_ADMIN, ROLE_MEMBER, SessionUser
from syft_station.components.auth.syfthub import (
    SyftHubAuthError,
    SyftHubIdentityClient,
    SyftHubUnavailableError,
)
from syft_station.config import app_settings


class AuthHandler:
    """Validates credentials against SyftHub and builds the session user."""

    def __init__(self, syfthub_client: SyftHubIdentityClient):
        self.syfthub_client = syfthub_client

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
