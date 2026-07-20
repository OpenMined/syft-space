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
from syft_station.components.provision.dev import DevProvisioner
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

syfthub_client = SyftHubIdentityClient(str(app_settings.syfthub_url))
provisioner = DevProvisioner()

auth_handler = AuthHandler(syfthub_client)
setup_handler = SetupHandler(setup_repository)
space_handler = SpaceHandler(space_repository)
request_handler = RequestHandler(
    repository=request_repository,
    space_repository=space_repository,
    setup_repository=setup_repository,
    provisioner=provisioner,
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


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """Liveness/readiness probe endpoint."""
    return {"status": "ok"}


@app.get("/version", tags=["health"])
async def get_version() -> dict[str, str]:
    return {"version": pkg_version("syft-station")}


# ── Static frontend (built UI shipped in the image/wheel) ───────────────────

UI_DIR = Path(__file__).parent / "ui"

if UI_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui")
else:
    logger.info("No built frontend found (syft_station/ui) — API-only mode")
