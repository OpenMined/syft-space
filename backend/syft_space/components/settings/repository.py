"""Settings repository for database operations."""

from datetime import datetime, timezone

from syft_space.components.settings.entities import Settings
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class SettingsRepository(AsyncBaseRepository[Settings]):
    """Repository for Settings CRUD operations.

    TODO: Add multi-tenant support.
    """

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Settings)

    async def get_settings(self) -> Settings:
        """Get the settings."""
        settings = await self.get_all()
        if len(settings) > 0:
            return settings[0]
        # Create a new settings object if no settings exist
        settings = Settings(public_url=None, ngrok_token=None)
        return await self.create(settings)

    async def update_public_url(self, url: str | None) -> Settings:
        """Update the public_url setting."""
        settings = await self.get_settings()
        settings.public_url = url
        settings.updated_at = datetime.now(timezone.utc)
        return await self.update(settings)

    async def get_ngrok_token(self) -> str:
        """Get the stored ngrok token."""
        settings = await self.get_settings()
        return settings.ngrok_token

    async def update_ngrok_token(self, token: str | None) -> Settings:
        """Update the ngrok token setting."""
        settings = await self.get_settings()
        settings.ngrok_token = token
        settings.updated_at = datetime.now(timezone.utc)
        return await self.update(settings)

    async def get_ngrok_username(self) -> str | None:
        """Get the stored ngrok username for subdomain."""
        settings = await self.get_settings()
        return settings.ngrok_username

    async def update_ngrok_username(self, username: str | None) -> Settings:
        """Update the ngrok username setting."""
        settings = await self.get_settings()
        settings.ngrok_username = username
        settings.updated_at = datetime.now(timezone.utc)
        return await self.update(settings)
