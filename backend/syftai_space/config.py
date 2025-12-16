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
        "~/.syai-space/app.db"
    ).expanduser()  # Default path for SQLite database

    # Application settings
    debug: bool = False

    # Reset database settings
    reset_db: bool = Field(
        default=False,
        description="Reset the database (delete and recreate all tables)",
    )

    # Ngrok settings
    use_ngrok: bool = Field(
        default=False,
        description="Use ngrok to expose the server to the internet",
    )
    ngrok_auth_token: str = Field(
        default="",
        description="Ngrok authentication token",
    )

    # Multi-tenancy settings
    enable_multi_tenancy: bool = Field(
        default=False,
        description="Enable multi-tenancy support",
    )
    default_tenant_name: str = Field(
        default="root",
        description="Default tenant name (used when multi-tenancy is disabled)",
    )

    # Admin authentication
    admin_api_key: str = Field(
        default="",
        description="Admin API key for protected endpoints. If empty, no auth is enforced (dev mode).",
    )


# Global settings instance
app_settings = AppSettings()
