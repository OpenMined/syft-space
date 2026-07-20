from pathlib import Path

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="SYFT_STATION_",
    )

    # Server settings
    host: str = Field(
        default="0.0.0.0",
        description="Host for the server to bind to",
    )
    port: int = Field(
        default=8090,
        description="Port for the server to listen on",
    )

    # Database settings
    sqlite_db_path: Path = Path("~/.syft-station/app.db").expanduser()

    # Application settings
    debug: bool = False

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Log level for all handlers (DEBUG, INFO, WARNING, ERROR)",
    )

    # Reset database settings
    reset_db: bool = Field(
        default=False,
        description="Reset the database (delete and recreate all tables)",
    )

    # Identity settings
    syfthub_url: HttpUrl = Field(
        default="https://syfthub.openmined.org",
        description="SyftHub instance used for member sign-in",
    )
    admin_email: str = Field(
        default="",
        description=(
            "Email of the station admin (must be a valid SyftHub account). "
            "Sign-ins with this email get the admin role."
        ),
    )

    # Session settings
    session_secret: str = Field(
        default="",
        description=(
            "Secret for signing session cookies. Unset: a random secret is "
            "generated at startup (sessions won't survive restarts)."
        ),
    )
    session_max_age_seconds: int = Field(
        default=7 * 24 * 3600,
        description="Session cookie lifetime in seconds",
    )
    session_cookie_secure: bool = Field(
        default=False,
        description="Mark the session cookie Secure (set true behind HTTPS)",
    )

    # Provisioning settings
    space_version: str = Field(
        default="latest",
        description="Default syft-space version offered during first-run setup",
    )

    # Kubernetes settings
    namespace: str = Field(
        default="syft-spaces",
        description="Kubernetes namespace that per-space resources are created in",
    )
    kubeconfig: str = Field(
        default="",
        description=(
            "Path to a kubeconfig file. Ignored in-cluster (a ServiceAccount "
            "is used). Empty off-cluster falls back to the default kubeconfig."
        ),
    )

    # Per-space deployment settings
    space_image: str = Field(
        default="openmined/syft-space",
        description="Container image (repo only) each space is deployed from",
    )
    ingress_class: str = Field(
        default="traefik",
        description="IngressClass routing <subdomain>.<domain> to the space",
    )
    space_pvc_size: str = Field(
        default="2Gi",
        description="Storage requested for each space's data volume",
    )
    space_cpu_request: str = Field(default="250m")
    space_cpu_limit: str = Field(default="1")
    space_memory_request: str = Field(default="512Mi")
    space_memory_limit: str = Field(default="2Gi")

    # Shared infrastructure each space connects to (in-cluster service DNS)
    chromadb_host: str = Field(
        default="chromadb",
        description="Hostname of the shared ChromaDB service",
    )
    chromadb_port: int = Field(
        default=8100,
        description="HTTP port of the shared ChromaDB service",
    )
    docling_url: str = Field(
        default="http://docling-serve:5001",
        description="URL of the shared docling-serve service",
    )
    managed_by_name: str = Field(
        default="Syft Station",
        description="Display name injected as SYFT_CLUSTER_MANAGED_BY into spaces",
    )


# Global settings instance
app_settings = AppSettings()
