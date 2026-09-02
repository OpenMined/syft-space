"""Setup repository for database operations."""

from datetime import UTC, datetime

from syft_station.components.setup.entities import StationConfig
from syft_station.components.shared.database import AsyncBaseRepository, AsyncDatabase


class SetupRepository(AsyncBaseRepository[StationConfig]):
    """Repository for the singleton StationConfig row."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, StationConfig)

    async def get_config(self) -> StationConfig:
        """Get the station config, creating the row if missing."""
        rows = await self.get_all()
        if rows:
            return rows[0]
        return await self.create(StationConfig())

    async def update_identity(self, hub_pat: str, hub_user_id: int) -> StationConfig:
        """Record the station's SyftHub identity."""
        config = await self.get_config()
        config.hub_pat = hub_pat
        config.hub_user_id = hub_user_id
        config.updated_at = datetime.now(UTC)
        return await self.update(config)

    async def update_satellite_id(self, satellite_id: str) -> StationConfig:
        """Record the station's satellite. Kept off ``update_config`` so the
        onboarding form cannot reach it."""
        config = await self.get_config()
        config.satellite_id = satellite_id
        config.updated_at = datetime.now(UTC)
        return await self.update(config)

    async def update_config(
        self, domain: str | None = None, supported_version: str | None = None
    ) -> StationConfig:
        config = await self.get_config()
        if domain is not None:
            config.domain = domain
        if supported_version is not None:
            config.supported_version = supported_version
        config.updated_at = datetime.now(UTC)
        return await self.update(config)
