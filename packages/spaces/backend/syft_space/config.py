from pathlib import Path
from uuid import UUID

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClusterSettings(BaseSettings):
    """Managed-wallet settings, populated from the ``SYFT_CLUSTER_*`` env.

    Injected into a space's Secret by the station it runs on. All grouped
    here so the wallet config lives in one place: ``app_settings.cluster.*``.
    Its own env prefix keeps each field a flat name (``credits_url``, not a
    delimiter-split ``credits.url``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="SYFT_CLUSTER_",
    )

    credits_url: HttpUrl | None = Field(
        default=None,
        description=(
            "Base URL of the cluster credits service. Set (with the token) "
            "to seed the managed cluster wallet at startup. Internal "
            "space→station debit path only."
        ),
    )
    credits_token: str = Field(
        default="",
        description="Per-space service token for the cluster credits API",
    )
    credits_currency: str = Field(
        default="USD",
        description="Currency of the cluster credits wallet",
    )
    credits_wallet_id: UUID | None = Field(
        default=None,
        description=(
            "Id of the managed wallet on the station. Adopted as this space's "
            "cluster wallet id so every space on the wallet shares one id — a "
            "marketplace groups them as a single balance."
        ),
    )
    public_url: HttpUrl | None = Field(
        default=None,
        description=(
            "Public base URL of the station. Published on paid endpoints so "
            "buyers reach the station's checkout/balance routes (credits_url "
            "is for space→station debits only)."
        ),
    )
    wallet_owner: int | None = Field(
        default=None,
        description=(
            "SyftHub user id of the station wallet's owner. Published on "
            "paid endpoints (as wallet_owner) so the hub mints buyer tokens "
            "for this user's audience and attributes/groups the station's "
            "spaces."
        ),
    )
    bundles: list[dict] | None = Field(
        default=None,
        description=(
            "Purchase catalog for the managed wallet, as JSON "
            '[{"name": …, "amount": …}, …]. Injected by the station (which '
            "prices bundle purchases from the same table); when absent the "
            "static per-currency catalog is published instead."
        ),
    )
    managed_by: str = Field(
        default="",
        description=(
            "Display name of the managing station, injected as "
            "SYFT_CLUSTER_MANAGED_BY into every station-launched space. "
            "Non-empty means this space runs in managed mode (self-hosted "
            "onboarding affordances are trimmed); display fallbacks apply "
            "at the use site."
        ),
    )

    @field_validator("credits_url", "public_url", mode="before")
    @classmethod
    def validate_optional_url(cls, v: HttpUrl | str | None) -> HttpUrl | None:
        if not v:
            return None
        if not isinstance(v, HttpUrl):
            v = HttpUrl(v)
        return v


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
    sqlite_db_path: Path = Path(
        "~/.syft-space/app.db"
    ).expanduser()  # Default path for SQLite database
    analytics_db_path: Path = Path(
        "~/.syft-space/analytics.db"
    ).expanduser()  # Separate DB for analytics event log

    # Application settings
    debug: bool = False

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Log level for all handlers (DEBUG, INFO, WARNING, ERROR)",
    )
    log_file: str = Field(
        default="~/.syft-space/logs/syft-space-server.log",
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

    # Xendit settings
    xendit_api_url: HttpUrl = Field(
        default="https://api.xendit.co",
        description="Xendit API base URL",
    )

    # Stripe settings
    stripe_api_url: HttpUrl = Field(
        default="https://api.stripe.com",
        description="Stripe API base URL",
    )

    # MPP / Tempo settings
    tempo_testnet: bool = Field(
        default=True,
        description="Use Tempo testnet for MPP payments. Set to False for production (mainnet).",
    )

    # ChromaDB settings (defaults match the local subprocess setup)
    chromadb_host: str = Field(
        default="localhost",
        description="ChromaDB server host",
    )
    chromadb_http_port: int = Field(
        default=8100,
        description="ChromaDB server HTTP port",
    )
    chromadb_database: str = Field(
        default="default_database",
        description="ChromaDB database holding this space's collections",
    )
    chromadb_ssl: bool = Field(
        default=False,
        description="Connect to ChromaDB over TLS",
    )
    chromadb_provision: bool = Field(
        default=True,
        description=(
            "Spawn a local ChromaDB subprocess. Set to False to use an "
            "externally managed server (its database is ensured at startup)."
        ),
    )

    # Docling settings
    docling_serve_url: HttpUrl | None = Field(
        default=None,
        description=(
            "URL of an externally managed docling-serve instance. Unset: "
            "documents are converted in-process with the docling library."
        ),
    )

    # Syft Cluster credits (managed wallet) settings — grouped under one
    # sub-model so all of it is reachable as app_settings.cluster.*
    cluster: ClusterSettings = Field(default_factory=ClusterSettings)

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

    @field_validator("public_url", "docling_serve_url", mode="before")
    @classmethod
    def validate_optional_url(cls, v: HttpUrl | str | None) -> HttpUrl | None:
        if not v:
            return
        if not isinstance(v, HttpUrl):
            v = HttpUrl(v)
        return v


# Global settings instance
app_settings = AppSettings()
