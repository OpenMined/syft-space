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
    cors_origins: str = Field(
        default="",
        description=(
            "Extra browser origins allowed by CORS, comma-separated. The "
            "SyftHub origin is always allowed (its frontend calls the buyer "
            "credits routes from the browser); use this only when the hub is "
            "browsed at a different address than the station dials it. The "
            "k3d dev loop doesn't need it — syfthub.localhost resolves both "
            "in browsers and in-cluster (justfile cluster-dns)."
        ),
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
    provisioner: str = Field(
        default="mock",
        description="Which provisioner to use: 'mock' (no cluster) or 'k8s' (real).",
    )
    namespace: str = Field(
        default="syft-spaces",
        description="Kubernetes namespace that per-space resources are created in",
    )
    provision_timeout_seconds: int = Field(
        default=300,
        description="How long to wait for a space Deployment to become available",
    )
    provision_poll_interval_seconds: float = Field(
        default=3.0,
        description="Interval between Deployment-readiness checks while provisioning",
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
    space_scheme: str = Field(
        default="https",
        description=(
            "Scheme of the public space URLs the station mints "
            "(<scheme>://<subdomain>.<domain>). Prod terminates TLS at the "
            "ingress; dev has no certs and sets http."
        ),
    )
    image_registry: str = Field(
        default="ghcr.io",
        description=(
            "Registry hosting the space image; used to list the available "
            "tags shown in the version picker"
        ),
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
    space_host_mount: bool = Field(
        default=False,
        description=(
            "Mount the cluster node's /mnt/host-home directory into every "
            "space, read-only at /root/host-home — inside the container's "
            "home, where the space's dataset file browser is rooted. What "
            "spaces see is whatever the cluster runtime maps to that node "
            "path (the k3d dev cluster maps $HOME there at creation)."
        ),
    )

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
    credits_url: str = Field(
        default="http://syft-station:8090",
        description=(
            "URL spaces use to reach the station credits API (their Secret's "
            "SYFT_CLUSTER_CREDITS_URL). Default = the in-cluster Service; "
            "host-run dev overrides it (e.g. http://host.k3d.internal:8090)."
        ),
    )
    public_url: str = Field(
        default="",
        description=(
            "The station's public base URL — its own ingress host (their "
            "Secret's SYFT_CLUSTER_PUBLIC_URL), minted into every space so "
            "buyers reach the station's checkout/balance routes. This is the "
            "station's host, NOT the spaces' parent domain: the two differ "
            "when spaces use a subdomain prefix. Injected from the chart's "
            "ingress host; the dev loops set it to the host-run address. "
            "Distinct from credits_url, the internal space→station path. Empty "
            "→ endpoints publish bundles but no buyer URLs."
        ),
    )

    # Payment providers
    xendit_api_url: str = Field(
        default="https://api.xendit.co",
        description="Xendit API base URL (overridable for tests)",
    )
    stripe_api_url: str = Field(
        default="https://api.stripe.com",
        description="Stripe API base URL (overridable for tests)",
    )


app_settings = AppSettings()
