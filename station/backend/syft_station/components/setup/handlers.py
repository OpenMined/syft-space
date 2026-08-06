"""Setup handler — first-run station configuration."""

from urllib.parse import urlparse

from syft_station.components.setup.entities import StationConfig
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.setup.schemas import SetupResponse, UpdateSetupRequest
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
