from pathlib import Path

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="SYFT_",
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

    # External service URLs
    default_accounting_url: HttpUrl = Field(
        default="https://syftaccounting.centralus.cloudapp.azure.com/",
        description="Default URL for the accounting service",
    )
    default_marketplace_url: HttpUrl = Field(
        default="https://syfthub.openmined.org",
        description="Default URL for the marketplace service",
    )

    # Syft Space Public URL
    public_url: HttpUrl | None = Field(
        None,
        description="Public URL for the Syft Space",
    )

    @field_validator("public_url", mode="before")
    @classmethod
    def validate_public_url(cls, v: HttpUrl | None) -> HttpUrl | None:
        if not v:
            return
        if not v.startswith("http"):
            v = HttpUrl(f"https://{v}")
        return v


# Global settings instance
app_settings = AppSettings()
