"""Settings repository for database operations."""

from datetime import datetime, timezone

from syftai_space.components.settings.entities import Settings
from syftai_space.components.shared.database import BaseRepository, Database


class SettingsRepository(BaseRepository[Settings]):
    """Repository for Settings CRUD operations."""

    def __init__(self, db: Database):
        super().__init__(db, Settings)

    def get_settings(self) -> Settings:
        """Get the singleton settings row, creating if not exists."""
        settings = self.get_by_id(1)
        if not settings:
            settings = self.create(Settings(id=1))
        return settings

    def update_public_url(self, url: str | None) -> Settings:
        """Update the public_url setting."""
        settings = self.get_settings()
        settings.public_url = url
        settings.updated_at = datetime.now(timezone.utc)
        return self.update(settings)
