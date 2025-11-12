from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database settings
    sqlite_db_path: Path = Path(
        "~/.syai-server/app.db"
    ).expanduser()  # Default path for SQLite database

    # Application settings
    debug: bool = False

    # Reset database settings
    reset_db: bool = Field(
        default=False,
        description="Reset the database (delete and recreate all tables)",
    )


# Global settings instance
app_settings = AppSettings()
