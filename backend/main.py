from fastsyftbox import FastSyftBox
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from syft_core.config import SyftClientConfig
from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse
from components.data_sources.handlers import DataSourceHandler
from components.data_sources.registry import DATA_SOURCE_REGISTRY
from components.data_sources.routes import build_data_source_routes

# Import the data_sources package to trigger all registrations
import components.data_sources  # noqa: F401

from .config import app_settings


app = FastSyftBox(
    app_name="SyftAIServer",
    syftbox_config=SyftClientConfig.load(app_settings.syftbox_config_path),
    version="1.0.0",
    syftbox_endpoint_tags=["syftbox"],
    debug=app_settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create a router
router = APIRouter(prefix="/api/v1")

# Add the data source routes to the router
router.include_router(
    build_data_source_routes(DataSourceHandler(registry=DATA_SOURCE_REGISTRY))
)


@router.get("/health")
async def health():
    return {"status": "healthy"}


# Include the router in the app
app.include_router(router)
app.mount(
    "/syftai-server", StaticFiles(directory="frontend/dist", html=True, check_dir=False)
)


@app.get("/")
async def redirect_root():
    return RedirectResponse(
        url="/syftai-server", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
