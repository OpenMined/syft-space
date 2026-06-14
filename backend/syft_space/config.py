from pathlib import Path

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # backend/syft_space/config.py -> syft_space/ -> backend/ -> repo root
    return Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    preferred = Path("~/.syft-space").expanduser()
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback = _repo_root() / ".syft-space"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="SYFT_",
    )

    # Server settings
    host: str = Field(
        default="0.0.0.0",
        description="Host for the server to bind to",
    )
    port: int = Field(
        default=8080,
        description="Port for the server to listen on",
    )

    # Database settings
    sqlite_db_path: Path = Field(
        default_factory=lambda: _default_data_dir() / "app.db",
        description="Path for SQLite database file",
    )

    # Application settings
    debug: bool = False

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Log level for all handlers (DEBUG, INFO, WARNING, ERROR)",
    )
    log_file: str = Field(
        default_factory=lambda: str(_default_data_dir() / "logs" / "syft-space-server.log"),
        description="Path to log file. If set, enables file logging with rotation. Example: /data/logs/syft-space.log",
    )

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
    default_marketplace_url: HttpUrl = Field(
        default="https://syfthub.openmined.org",
        description="Default URL for the marketplace service",
    )

    # Syft Space Public URL
    public_url: HttpUrl | None = Field(
        None,
        description="Public URL for the Syft Space",
    )

    # MPP / Tempo settings
    tempo_testnet: bool = Field(
        default=True,
        description="Use Tempo testnet for MPP payments. Set to False for production (mainnet).",
    )

    # Endpoint health check settings
    heartbeat_enabled: bool = Field(
        default=True,
        description="Enable periodic endpoint health reporting to marketplaces",
    )
    health_check_interval: float = Field(
        default=30.0,
        description="Interval in seconds between endpoint health checks",
    )

    # Local chat settings
    chat_timeout_seconds: float = Field(
        default=60.0,
        description="Timeout in seconds for local chat model/dataset calls",
    )

    @field_validator("public_url", mode="before")
    @classmethod
    def validate_public_url(cls, v: HttpUrl | str | None) -> HttpUrl | None:
        if not v:
            return
        if not isinstance(v, HttpUrl):
            v = HttpUrl(v)
        return v


# Global settings instance
app_settings = AppSettings()
