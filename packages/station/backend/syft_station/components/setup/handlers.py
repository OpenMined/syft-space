"""Setup handler — first-run station configuration."""

from urllib.parse import urlparse

from fastapi import HTTPException, status

from syft_station.components.auth.syfthub import (
    SyftHubAuthError,
    SyftHubIdentityClient,
    SyftHubUnavailableError,
)
from syft_station.components.setup.entities import StationConfig
from syft_station.components.setup.interfaces import SpaceFlags
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.setup.satellites import StationSatelliteRegistrar
from syft_station.components.setup.schemas import (
    ConnectIdentityRequest,
    IdentityResponse,
    SetupResponse,
    UpdateSetupRequest,
)
from syft_station.config import app_settings


def _station_host() -> str:
    """Bare host of the station's public URL (no scheme/port), for onboarding.

    Empty when public_url is unset (host-run dev) — the admin then types the
    spaces domain directly.
    """
    return urlparse(app_settings.public_url).hostname or ""


class SetupHandler:
    """First-run setup: domain + supported version; onboarded ⇔ domain set."""

    def __init__(self, repository: SetupRepository):
        self.repository = repository

    def _response(self, config: StationConfig) -> SetupResponse:
        return SetupResponse(
            domain=config.domain,
            supported_version=config.supported_version,
            onboarded=config.domain != "",
            station_host=_station_host(),
        )

    async def get_setup(self) -> SetupResponse:
        return self._response(await self.repository.get_config())

    async def update_setup(self, request: UpdateSetupRequest) -> SetupResponse:
        return self._response(
            await self.repository.update_config(
                domain=request.domain,
                supported_version=request.supported_version,
            )
        )


class StationIdentityHandler:
    """The station's one SyftHub identity, shared by every wallet.

    Holding it here rather than on a wallet means a second gateway reuses
    the same token instead of minting another, and the satellite that token
    registers covers the station's origin however many wallets it grows.
    """

    def __init__(
        self,
        repository: SetupRepository,
        hub: SyftHubIdentityClient,
        satellites: StationSatelliteRegistrar,
        spaces: SpaceFlags,
    ):
        self.repository = repository
        self.hub = hub
        self.satellites = satellites
        self.spaces = spaces

    async def get(self) -> IdentityResponse:
        config = await self.repository.get_config()
        if not config.hub_pat:
            return IdentityResponse(connected=False)
        try:
            profile = await self.hub.whoami(config.hub_pat)
        except (SyftHubAuthError, SyftHubUnavailableError):
            # The stored token may be revoked or the hub down; either way the
            # identity exists locally and the admin can rotate it.
            return IdentityResponse(connected=True, satellite_id=config.satellite_id)
        return IdentityResponse(
            connected=True,
            username=profile.username,
            email=str(profile.email),
            satellite_id=config.satellite_id,
        )

    async def connect(
        self, request: ConnectIdentityRequest, admin_email: str
    ) -> IdentityResponse:
        """Adopt or mint a token, store it, then register the satellite.

        Registration is a side effect: the identity is saved either way, and
        a failed registration retries at the next boot.
        """
        try:
            if request.syfthub_api_token:
                pat = request.syfthub_api_token
                profile = await self.hub.whoami(pat)
            elif request.syfthub_password:
                pat = await self.hub.mint_pat(admin_email, request.syfthub_password)
                profile = await self.hub.whoami(pat)
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Paste a SyftHub API token, or send a password to mint one",
                )
        except SyftHubAuthError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except SyftHubUnavailableError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e

        previous_owner = (await self.repository.get_config()).hub_user_id
        await self.repository.update_identity(pat, profile.id)
        await self._flag_stale_spaces(previous_owner, profile)
        await self.satellites.ensure_quietly(pat)

        config = await self.repository.get_config()
        return IdentityResponse(
            connected=True,
            username=profile.username,
            email=str(profile.email),
            satellite_id=config.satellite_id,
        )

    async def _flag_stale_spaces(self, previous: int | None, profile) -> None:
        """Flag attached spaces when the hub account behind the station changes.

        Every attached space publishes this id as its wallet owner, which is
        how the hub decides whose audience to mint buyer tokens for and who
        to credit as host. A space carrying the old one — or none, if it was
        attached before the station had an identity — credits the wrong
        account until it is re-applied.
        """
        if previous == profile.id:
            return
        was = f"SyftHub owner {previous}" if previous is not None else "no wallet owner"
        await self.spaces.flag_wallet_stale(
            f"Publishes {was}; the station now signs in as {profile.username}"
        )
