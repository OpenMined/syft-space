"""Setup handler — first-run station configuration."""

from syft_station.components.setup.repository import SetupRepository
from syft_station.components.setup.schemas import SetupResponse, UpdateSetupRequest


class SetupHandler:
    """First-run setup: domain + supported version; onboarded ⇔ domain set."""

    def __init__(self, repository: SetupRepository):
        self.repository = repository

    async def get_setup(self) -> SetupResponse:
        config = await self.repository.get_config()
        return SetupResponse(
            domain=config.domain,
            supported_version=config.supported_version,
            onboarded=config.domain != "",
        )

    async def update_setup(self, request: UpdateSetupRequest) -> SetupResponse:
        config = await self.repository.update_config(
            domain=request.domain,
            supported_version=request.supported_version,
        )
        return SetupResponse(
            domain=config.domain,
            supported_version=config.supported_version,
            onboarded=config.domain != "",
        )
