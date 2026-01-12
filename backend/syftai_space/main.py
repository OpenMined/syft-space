"""Main FastAPI application."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Import auth components
from syftai_space.components.auth.dependencies import bearer_scheme
from syftai_space.components.auth.middleware import AdminKeyMiddleware
from syftai_space.components.auth.public import public_route

# Import explicit registration functions
from syftai_space.components.dataset_types import (
    register_builtin_types as register_dataset_types,
)

# Import registries
from syftai_space.components.dataset_types.registry import DATASET_TYPE_REGISTRY

# Import handlers
from syftai_space.components.datasets.handlers import DatasetHandler

# Import provisioner manager
from syftai_space.components.datasets.provisioner_manager import ProvisionerManager

# Import repositories
from syftai_space.components.datasets.provisioner_state_repository import (
    ProvisionerStateRepository,
)
from syftai_space.components.datasets.repository import DatasetRepository

# Import route builders
from syftai_space.components.datasets.routes import build_dataset_routes
from syftai_space.components.endpoints.handlers import EndpointHandler
from syftai_space.components.endpoints.repository import EndpointRepository
from syftai_space.components.endpoints.routes import build_endpoint_routes

# Import ingestion components
from syftai_space.components.ingestion.handlers import IngestionHandler
from syftai_space.components.ingestion.manager import IngestionManager
from syftai_space.components.ingestion.repository import IngestionJobRepository
from syftai_space.components.ingestion.routes import build_ingestion_routes
from syftai_space.components.marketplaces.handlers import MarketplaceHandler
from syftai_space.components.marketplaces.repository import MarketplaceRepository
from syftai_space.components.marketplaces.routes import build_marketplace_routes
from syftai_space.components.model_types import (
    register_builtin_types as register_model_types,
)
from syftai_space.components.model_types.registry import MODEL_TYPE_REGISTRY
from syftai_space.components.models.handlers import ModelHandler
from syftai_space.components.models.repository import ModelRepository
from syftai_space.components.models.routes import build_model_routes
from syftai_space.components.policies.handlers import PolicyHandler
from syftai_space.components.policies.repository import PolicyRepository
from syftai_space.components.policies.routes import build_policy_routes
from syftai_space.components.policy_types import (
    register_builtin_types as register_policy_types,
)
from syftai_space.components.policy_types.rate_limit.limiter import (
    InMemoryRateLimitStorage,
)
from syftai_space.components.policy_types.rate_limit.limiter import (
    set_storage as set_rate_limit_storage,
)
from syftai_space.components.policy_types.registry import POLICY_TYPE_REGISTRY
from syftai_space.components.settings.handlers import SettingsHandler

# Import settings components
from syftai_space.components.settings.routes import build_settings_routes

# Import database
from syftai_space.components.shared.database import Database, SQLiteConfig

# Import tenant components
from syftai_space.components.tenants.entities import Tenant
from syftai_space.components.tenants.handlers import TenantHandler
from syftai_space.components.tenants.middleware import TenantMiddleware
from syftai_space.components.tenants.repository import TenantRepository
from syftai_space.components.tenants.routes import build_tenant_routes
from syftai_space.config import app_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - handles startup and shutdown events."""
    # Startup: Initialize ngrok if enabled
    listener = None
    if app_settings.use_ngrok:
        try:
            import ngrok

            # Set auth token if provided
            ngrok.set_auth_token(app_settings.ngrok_auth_token)

            # Get the port from environment variable or default
            port = int(os.getenv("SYFTAI_PORT", "8080"))

            # Start ngrok tunnel
            listener = await ngrok.forward(port)
            public_url = listener.url()

            logger.info("\n" + "=" * 70)
            logger.info("🚀 Ngrok tunnel established!")
            logger.info(f"📡 Public URL: {public_url}")
            logger.info(f"🔗 Local URL: http://localhost:{port}")
            logger.info("=" * 70 + "\n")
            app_settings.public_url = public_url

        except Exception as e:
            logger.error(f"⚠️  Warning: Failed to start ngrok tunnel: {e}")
            logger.error("   Continuing without ngrok...\n")

    # Startup order: provisioners first, then ingestion
    provisioner_manager: ProvisionerManager = getattr(
        app.state, "provisioner_manager", None
    )
    ingestion_manager: IngestionManager = getattr(app.state, "ingestion_manager", None)

    if provisioner_manager:
        try:
            await provisioner_manager.startup()
        except Exception as e:
            logger.error(f"Failed to start provisioners: {e}")

    if ingestion_manager:
        try:
            await ingestion_manager.startup()
        except Exception as e:
            logger.error(f"Failed to start ingestion manager: {e}")

    yield  # Application runs here

    # Shutdown order: ingestion first, then provisioners
    if ingestion_manager:
        try:
            await ingestion_manager.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down ingestion manager: {e}")

    if provisioner_manager:
        try:
            await provisioner_manager.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down provisioners: {e}")

    # Shutdown: Clean up ngrok if it was started
    if listener:
        try:
            await listener.close()
            logger.info("✅ Ngrok tunnel closed")
        except Exception as e:
            logger.error(f"⚠️  Warning: Error closing ngrok tunnel: {e}")


# Initialize FastAPI app
app = FastAPI(
    title="Syft AI Server",
    description="Syft AI Server - RAG platform with datasets, models, endpoints, and policies",
    version="0.1.0",
    debug=app_settings.debug,
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
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
db_path = app_settings.sqlite_db_path.resolve()
db_config = SQLiteConfig(db_path)
database = Database(db_config)

# Run database migrations, optionally resetting the database
database.run_migrations(reset=app_settings.reset_db)


# Initialize tenant repository and create default tenant
tenant_repository = TenantRepository(database)
default_tenant = tenant_repository.get_by_name(app_settings.default_tenant_name)
if not default_tenant:
    logger.info(f"Creating default tenant: {app_settings.default_tenant_name}")
    default_tenant = tenant_repository.create(
        Tenant(
            name=app_settings.default_tenant_name,
            display_name="Root Tenant",
            is_active=True,
            meta={"description": "Default root tenant"},
        )
    )
    logger.info(f"Default tenant created with ID: {default_tenant.id}")
else:
    logger.info(f"Default tenant already exists: {default_tenant.name}")

# Initialize repositories
dataset_repository = DatasetRepository(database)
provisioner_state_repository = ProvisionerStateRepository(database)
model_repository = ModelRepository(database)
policy_repository = PolicyRepository(database)
endpoint_repository = EndpointRepository(database)
ingestion_job_repository = IngestionJobRepository(database)
marketplace_repository = MarketplaceRepository(database)

# Explicit type registration - no import side effects
logger.info("Registering dataset types ...")
register_dataset_types(DATASET_TYPE_REGISTRY)
logger.info("Registering model types ...")
register_model_types(MODEL_TYPE_REGISTRY)
logger.info("Registering policy types ...")
register_policy_types(POLICY_TYPE_REGISTRY)

# Configure rate limiter storage (in-memory, can swap to Redis later)
logger.info("Initializing rate limiter storage ...")
set_rate_limit_storage(InMemoryRateLimitStorage())

# Initialize handlers
dataset_handler = DatasetHandler(
    DATASET_TYPE_REGISTRY, dataset_repository, provisioner_state_repository
)
model_handler = ModelHandler(MODEL_TYPE_REGISTRY, model_repository)
policy_handler = PolicyHandler(POLICY_TYPE_REGISTRY, policy_repository)
marketplace_handler = MarketplaceHandler(marketplace_repository)
endpoint_handler = EndpointHandler(
    endpoint_repository=endpoint_repository,
    dataset_repository=dataset_repository,
    model_repository=model_repository,
    policy_repository=policy_repository,
    dataset_registry=DATASET_TYPE_REGISTRY,
    model_registry=MODEL_TYPE_REGISTRY,
    policy_registry=POLICY_TYPE_REGISTRY,
    marketplace_repository=marketplace_repository,
)
tenant_handler = TenantHandler(tenant_repository)
settings_handler = SettingsHandler(marketplace_handler, app_settings)

# Initialize ingestion manager and handler
ingestion_manager = IngestionManager(
    dataset_repository=dataset_repository,
    ingestion_repository=ingestion_job_repository,
    registry=DATASET_TYPE_REGISTRY,
)
ingestion_handler = IngestionHandler(
    ingestion_manager=ingestion_manager,
    dataset_repository=dataset_repository,
)

# Initialize lifecycle managers (independent, ordered in lifespan)
provisioner_manager = ProvisionerManager(dataset_handler)
app.state.provisioner_manager = provisioner_manager
app.state.ingestion_manager = ingestion_manager

# Add tenant middleware (after CORS, before routes)
app.add_middleware(TenantMiddleware, tenant_repository=tenant_repository)

# Add admin key middleware (runs before tenant middleware)
# Middleware execution order is reverse of registration order
app.add_middleware(AdminKeyMiddleware)

# Create main API router with bearer auth for OpenAPI docs
# Actual auth is handled by AdminKeyMiddleware
router = APIRouter(prefix="/api/v1", dependencies=[Depends(bearer_scheme)])

# Include all routes
router.include_router(build_dataset_routes(dataset_handler, ingestion_manager))
router.include_router(build_model_routes(model_handler))
router.include_router(build_policy_routes(policy_handler))
router.include_router(build_endpoint_routes(endpoint_handler))
router.include_router(build_tenant_routes(tenant_handler))
router.include_router(build_ingestion_routes(ingestion_handler))
router.include_router(build_marketplace_routes(marketplace_handler))
router.include_router(build_settings_routes(settings_handler))


@public_route
@router.get("/health", tags=["system"])
async def health():
    """Health check endpoint (PUBLIC, no auth required)."""
    return {"status": "healthy", "version": "0.1.0"}


# Include the router in the app
app.include_router(router)

# Mount static files (if frontend exists)
# Frontend is a sibling directory to backend
frontend_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount(
        "/syftai-server",
        StaticFiles(directory=str(frontend_path), html=True, check_dir=False),
    )


@app.get("/", tags=["system"])
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
