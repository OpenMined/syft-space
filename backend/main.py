"""Main FastAPI application."""

from pathlib import Path

from fastapi import APIRouter, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

# Import explicit registration functions
from components.dataset_types import register_builtin_types as register_dataset_types

# Import registries
from components.dataset_types.registry import DATASET_TYPE_REGISTRY

# Import handlers
from components.datasets.handlers import DatasetHandler

# Import repositories
from components.datasets.repository import DatasetRepository

# Import route builders
from components.datasets.routes import build_dataset_routes
from components.endpoints.handlers import EndpointHandler
from components.endpoints.repository import EndpointRepository
from components.endpoints.routes import build_endpoint_routes
from components.model_types import register_builtin_types as register_model_types
from components.model_types.registry import MODEL_TYPE_REGISTRY
from components.models.handlers import ModelHandler
from components.models.repository import ModelRepository
from components.models.routes import build_model_routes
from components.policies.handlers import PolicyHandler
from components.policies.repository import PolicyRepository
from components.policies.routes import build_policy_routes
from components.policy_types import register_builtin_types as register_policy_types
from components.policy_types.registry import POLICY_TYPE_REGISTRY

# Import database
from components.shared.database import Database, SQLiteConfig

from .config import app_settings

# Initialize FastAPI app
app = FastAPI(
    title="Syft AI Server",
    description="Syft AI Server - RAG platform with datasets, models, endpoints, and policies",
    version="0.1.0",
    debug=app_settings.debug,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database
db_config = SQLiteConfig(app_settings.sqlite_db_path)
database = Database(db_config)

# Run database migrations (auto-applies on startup)
# If reset is requested, drop all tables first
if app_settings.reset_db:
    from sqlmodel import SQLModel

    SQLModel.metadata.drop_all(database.engine)

# Run migrations to ensure database is up to date
database.run_migrations()

# Initialize repositories
dataset_repository = DatasetRepository(database)
model_repository = ModelRepository(database)
policy_repository = PolicyRepository(database)
endpoint_repository = EndpointRepository(database)

# Explicit type registration - no import side effects
register_dataset_types(DATASET_TYPE_REGISTRY)
register_model_types(MODEL_TYPE_REGISTRY)
register_policy_types(POLICY_TYPE_REGISTRY)

# Initialize handlers
dataset_handler = DatasetHandler(DATASET_TYPE_REGISTRY, dataset_repository)
model_handler = ModelHandler(MODEL_TYPE_REGISTRY, model_repository)
policy_handler = PolicyHandler(POLICY_TYPE_REGISTRY, policy_repository)
endpoint_handler = EndpointHandler(
    endpoint_repository=endpoint_repository,
    dataset_repository=dataset_repository,
    model_repository=model_repository,
    policy_repository=policy_repository,
    dataset_registry=DATASET_TYPE_REGISTRY,
    model_registry=MODEL_TYPE_REGISTRY,
    policy_registry=POLICY_TYPE_REGISTRY,
)

# Create main API router
router = APIRouter(prefix="/api/v1")

# Include all routes
router.include_router(build_dataset_routes(dataset_handler))
router.include_router(build_model_routes(model_handler))
router.include_router(build_policy_routes(policy_handler))
router.include_router(build_endpoint_routes(endpoint_handler))


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


# Include the router in the app
app.include_router(router)

# Mount static files (if frontend exists)
# Frontend is a sibling directory to backend
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount(
        "/syftai-server",
        StaticFiles(directory=str(frontend_path), html=True, check_dir=False),
    )


@app.get("/")
async def redirect_root():
    """Redirect root to frontend or API docs."""
    if frontend_path.exists():
        return RedirectResponse(
            url="/syftai-server", status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )
    else:
        return RedirectResponse(
            url="/docs", status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
