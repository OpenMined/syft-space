"""Settings repository for database operations."""

from datetime import datetime, timezone

from syftai_space.components.settings.entities import Settings
from syftai_space.components.shared.database import BaseRepository, Database


class SettingsRepository(BaseRepository[Settings]):
    """Repository for Settings CRUD operations.

    TODO: Add multi-tenant support.
    """

    def __init__(self, db: Database):
        super().__init__(db, Settings)

    def get_settings(self) -> Settings:
        """Get the settings."""
        settings = self.get_all()
        if len(settings) > 0:
            return settings[0]
        # Create a new settings object if no settings exist
        settings = Settings(public_url=None, ngrok_token=None)
        return self.create(settings)

    def update_public_url(self, url: str | None) -> Settings:
        """Update the public_url setting."""
        settings = self.get_settings()
        settings.public_url = url
        settings.updated_at = datetime.now(timezone.utc)
        return self.update(settings)

    def get_ngrok_token(self) -> str:
        """Get the stored ngrok token."""
        settings = self.get_settings()
        return settings.ngrok_token

    def update_ngrok_token(self, token: str | None) -> Settings:
        """Update the ngrok token setting."""
        settings = self.get_settings()
        settings.ngrok_token = token
        settings.updated_at = datetime.now(timezone.utc)
        return self.update(settings)
