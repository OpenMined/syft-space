"""Main FastAPI application."""

from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

import syft_station.components.shared.logging_config  # noqa: F401, I001
from syft_station.components.auth.handlers import AuthHandler
from syft_station.components.auth.routes import build_auth_routes
from syft_station.components.auth.syfthub import SyftHubIdentityClient
from syft_station.components.credits.gateway.xendit import XenditGateway
from syft_station.components.credits.handlers import (
    CheckoutHandler,
    CreditsHandler,
    WalletAdminHandler,
    WebhookHandler,
)
from syft_station.components.credits.provisioning import (
    SpaceCreditsService,
    WalletRollout,
)
from syft_station.components.credits.repository import (
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.routes import build_credits_routes
from syft_station.components.images.handlers import ImageHandler
from syft_station.components.images.registry import ImageRegistryClient
from syft_station.components.images.routes import build_image_routes
from syft_station.components.provision.interfaces import Provisioner
from syft_station.components.provision.mock import MockProvisioner
from syft_station.components.requests.handlers import RequestHandler
from syft_station.components.requests.repository import RequestRepository
from syft_station.components.requests.routes import build_request_routes
from syft_station.components.setup.handlers import SetupHandler
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.setup.routes import build_setup_routes
from syft_station.components.shared.database import AsyncDatabase, SQLiteConfig
from syft_station.components.spaces.handlers import SpaceHandler
from syft_station.components.spaces.repository import SpaceRepository
from syft_station.components.spaces.routes import build_space_routes
from syft_station.config import app_settings

# ── Wiring ──────────────────────────────────────────────────────────────────

database = AsyncDatabase(SQLiteConfig(app_settings.sqlite_db_path))

setup_repository = SetupRepository(database)
request_repository = RequestRepository(database)
space_repository = SpaceRepository(database)
wallet_repository = WalletRepository(database)
credit_token_repository = SpaceCreditTokenRepository(database)

syfthub_client = SyftHubIdentityClient(str(app_settings.syfthub_url))


def _build_provisioner() -> Provisioner:
    """Pick the provisioner from config: real Kubernetes or the mock."""
    if app_settings.provisioner == "k8s":
        # Imported lazily so mock/test runs never need a cluster or its client.
        from syft_station.components.provision.k8s import K8sProvisioner
        from syft_station.components.provision.kube import KubeClient

        logger.info("Using the Kubernetes provisioner")
        kube = KubeClient.from_env(app_settings.kubeconfig)
        return K8sProvisioner(kube, app_settings)

    logger.info("Using the mock provisioner (no Kubernetes)")
    return MockProvisioner()


provisioner = _build_provisioner()

registry_client = ImageRegistryClient(
    app_settings.image_registry, app_settings.space_image
)

auth_handler = AuthHandler(syfthub_client)
image_handler = ImageHandler(registry_client)
payment_gateways = {
    XenditGateway.PROVIDER_NAME: XenditGateway(app_settings.xendit_api_url),
}

credits_handler = CreditsHandler(database, wallet_repository, credit_token_repository)
space_credits_service = SpaceCreditsService(
    wallet_repository, credit_token_repository, app_settings.credits_url
)
wallet_rollout = WalletRollout(space_repository, provisioner, space_credits_service)
wallet_admin_handler = WalletAdminHandler(
    wallet_repository, payment_gateways, wallet_rollout
)
checkout_handler = CheckoutHandler(database, wallet_repository, payment_gateways)
webhook_handler = WebhookHandler(database, wallet_repository, payment_gateways)
setup_handler = SetupHandler(setup_repository)
space_handler = SpaceHandler(space_repository, provisioner)
request_handler = RequestHandler(
    repository=request_repository,
    space_repository=space_repository,
    setup_repository=setup_repository,
    provisioner=provisioner,
    credits=space_credits_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    await database.run_migrations(reset=app_settings.reset_db)
    await setup_repository.get_config()  # ensure the singleton row exists

    if not app_settings.admin_email:
        logger.warning(
            "SYFT_STATION_ADMIN_EMAIL is unset — every sign-in gets the "
            "member role; no one can administer this station"
        )

    # Probe the cluster once at startup (k8s provisioner only). A failure is
    # logged, not fatal — the station still serves; provisioning shows the
    # error when attempted.
    check_connection = getattr(provisioner, "check_connection", None)
    if check_connection is not None:
        try:
            cluster_version = await check_connection()
            logger.info(f"Connected to Kubernetes {cluster_version}")
        except Exception as e:
            logger.error(f"Kubernetes cluster is not reachable at startup: {e}")

    yield

    await request_handler.wait_for_provisioning()
    await database.dispose()


app = FastAPI(title="Syft Station", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_auth_routes(auth_handler), prefix="/api/v1")
app.include_router(build_setup_routes(setup_handler), prefix="/api/v1")
app.include_router(build_request_routes(request_handler), prefix="/api/v1")
app.include_router(build_space_routes(space_handler), prefix="/api/v1")
app.include_router(build_image_routes(image_handler), prefix="/api/v1")
app.include_router(
    build_credits_routes(
        credits_handler, wallet_admin_handler, checkout_handler, webhook_handler
    ),
    prefix="/api/v1",
)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """Liveness/readiness probe endpoint."""
    return {"status": "ok"}


@app.get("/version", tags=["health"])
async def get_version() -> dict[str, str]:
    return {"version": pkg_version("syft-station")}


# ── Static frontend ─────────────────────────────────────────────────────────
# Prod ships the built UI inside the package (syft_station/ui — the Dockerfile
# copies it there). Dev builds to the sibling frontend/dist and serves it in
# place, the same way syft-space does (`just build-ui` = plain `vite build`, no
# relocation). Packaged copy wins when present.
_PACKAGED_UI = Path(__file__).parent / "ui"
_DEV_UI = Path(__file__).parent.parent.parent / "frontend" / "dist"
UI_DIR = _PACKAGED_UI if _PACKAGED_UI.is_dir() else _DEV_UI

if UI_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui")
else:
    logger.info("No built frontend found (syft_station/ui) — API-only mode")
