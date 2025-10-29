from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse
from components.datasets.handlers import DatasetHandler
from components.datasets.registry import DATASET_TYPE_REGISTRY
from components.datasets.routes import build_dataset_routes

# Import the data_sources package to trigger all registrations
import components.datasets  # noqa: F401

from .config import app_settings


app = FastAPI(
    title="Syft AI Server",
    description="Syft AI Server is a server for the Syft AI platform.",
    version="0.1.0",
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

# Add the dataset routes to the router
router.include_router(
    build_dataset_routes(DatasetHandler(registry=DATASET_TYPE_REGISTRY))
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
