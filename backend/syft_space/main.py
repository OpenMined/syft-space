"""Main FastAPI application."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Import auth components
from syft_space.components.auth.dependencies import bearer_scheme
from syft_space.components.auth.middleware import AdminKeyMiddleware
from syft_space.components.auth.public import discover_public_routes, public_route

# Import explicit registration functions
from syft_space.components.dataset_types import (
    register_builtin_types as register_dataset_types,
)

# Import registries
from syft_space.components.dataset_types.registry import DATASET_TYPE_REGISTRY

# Import handlers
from syft_space.components.datasets.handlers import DatasetHandler

# Import provisioner manager
from syft_space.components.datasets.provisioner_manager import ProvisionerManager

# Import repositories
from syft_space.components.datasets.provisioner_state_repository import (
    ProvisionerStateRepository,
)
from syft_space.components.datasets.repository import DatasetRepository

# Import route builders
from syft_space.components.datasets.routes import build_dataset_routes
from syft_space.components.endpoints.handlers import EndpointHandler
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.routes import build_endpoint_routes

# Import ingestion components
from syft_space.components.ingestion.handlers import IngestionHandler
from syft_space.components.ingestion.manager import IngestionManager
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.ingestion.routes import build_ingestion_routes
from syft_space.components.marketplaces.handlers import MarketplaceHandler
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.marketplaces.routes import build_marketplace_routes
from syft_space.components.model_types import (
    register_builtin_types as register_model_types,
)
from syft_space.components.model_types.registry import MODEL_TYPE_REGISTRY
from syft_space.components.models.handlers import ModelHandler
from syft_space.components.models.repository import ModelRepository
from syft_space.components.models.routes import build_model_routes
from syft_space.components.policies.handlers import PolicyHandler
from syft_space.components.policies.repository import PolicyRepository
from syft_space.components.policies.routes import build_policy_routes
from syft_space.components.policy_types import (
    register_builtin_types as register_policy_types,
)
from syft_space.components.policy_types.rate_limit.limiter import (
    InMemoryRateLimitStorage,
)
from syft_space.components.policy_types.rate_limit.limiter import (
    set_storage as set_rate_limit_storage,
)
from syft_space.components.policy_types.registry import POLICY_TYPE_REGISTRY
from syft_space.components.settings.handlers import SettingsHandler

# Import settings components
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.settings.routes import build_settings_routes

# Import database
from syft_space.components.shared.database import AsyncDatabase, SQLiteConfig

# Import lifecycle protocol
from syft_space.components.shared.lifecycle import LifecycleService

# Import proxy service
from syft_space.components.shared.proxy_service import ProxyService

# Import tenant components
from syft_space.components.tenants.entities import Tenant
from syft_space.components.tenants.handlers import TenantHandler
from syft_space.components.tenants.middleware import TenantMiddleware
from syft_space.components.tenants.repository import TenantRepository
from syft_space.components.tenants.routes import build_tenant_routes
from syft_space.config import app_settings


async def _sync_public_url_safe(
    handler: SettingsHandler, tenant: Tenant, url: str
) -> None:
    """Sync public URL to marketplace without blocking startup.

    This is a fire-and-forget helper that wraps the marketplace sync with
    timeout handling. If the sync fails or times out, the server continues
    starting - the sync is not critical for basic operation.

    Args:
        handler: Settings handler instance
        tenant: Tenant context
        url: Public URL to sync
    """
    try:
        await asyncio.wait_for(
            handler.update_public_url(tenant, url),
            timeout=10.0,  # 10 second timeout
        )
        logger.info("Public URL synced to marketplace successfully")
    except asyncio.TimeoutError:
        logger.warning("Marketplace sync timed out - server will continue starting")
    except Exception as e:
        logger.warning(f"Marketplace sync failed: {e} - server will continue starting")


async def _setup_tenant_and_settings(
    tenant_repo: TenantRepository,
    settings_hdlr: SettingsHandler,
) -> Tenant | None:
    """Create default tenant and initialize settings.

    Args:
        tenant_repo: Repository for tenant operations
        settings_hdlr: Handler for settings initialization

    Returns:
        The default tenant, or None if creation failed
    """
    default_tenant = await tenant_repo.get_by_name(app_settings.default_tenant_name)
    if not default_tenant:
        logger.info(f"Creating default tenant: {app_settings.default_tenant_name}")
        default_tenant = await tenant_repo.create(
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

    # Initialize settings from config (env var overwrites DB if set)
    try:
        await settings_hdlr.initialize_from_config(tenants=[default_tenant])
    except Exception as e:
        logger.error(f"⚠️  Warning: Failed to initialize settings from config: {e}")

    return default_tenant


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - handles startup and shutdown events."""
    # 1. Run database migrations
    await database.run_migrations(reset=app_settings.reset_db)

    # 2. Setup tenant and settings
    default_tenant = await _setup_tenant_and_settings(
        tenant_repository, settings_handler
    )
    app.state.default_tenant = default_tenant

    # 3. Define lifecycle services (startup order: proxy → provisioner → ingestion)
    services: list[tuple[str, LifecycleService]] = [
        ("proxy", proxy_service),
        ("provisioner", provisioner_manager),
        ("ingestion", ingestion_manager),
    ]

    # 4. Start all services
    for name, service in services:
        try:
            await service.startup()
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")

    # 5. Post-startup: Log proxy connection and update settings
    if proxy_service.is_connected():
        proxy_service.log_connection_info(app_settings.admin_api_key)
        public_url = proxy_service.get_public_url()
        if public_url and default_tenant:
            # Fire-and-forget: Don't block startup on marketplace sync
            asyncio.create_task(
                _sync_public_url_safe(settings_handler, default_tenant, public_url)
            )

    logger.info("Application started")
    yield  # Application runs here

    # 6. Shutdown all services (reverse order: ingestion → provisioner → proxy)
    for name, service in reversed(services):
        try:
            await service.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down {name}: {e}")


# Initialize FastAPI app
app = FastAPI(
    title="Syft Space",
    description="Syft Space - RAG platform with datasets, models, endpoints, and policies",
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


# Initialize database (async-only)
db_path = app_settings.sqlite_db_path.resolve()
db_config = SQLiteConfig(db_path)
database = AsyncDatabase(db_config)

# Initialize repositories
tenant_repository = TenantRepository(database)
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

# Initialize settings repository and proxy service
settings_repository = SettingsRepository(database)
proxy_service = ProxyService(settings_repository)

# Initialize settings handler with proxy service
settings_handler = SettingsHandler(
    settings_repository, marketplace_repository, proxy_service
)

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
app.state.proxy_service = proxy_service
app.state.settings_handler = settings_handler
app.state.tenant_repository = tenant_repository
app.state.default_tenant = None  # Set in lifespan after async creation

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

# Discover public routes from @public_route decorators
discover_public_routes(app)

# Add middleware (execution order is reverse of registration)
app.add_middleware(TenantMiddleware, tenant_repository=tenant_repository)
app.add_middleware(AdminKeyMiddleware)

# Mount static files (if frontend exists)
# Frontend is a sibling directory to backend
frontend_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount(
        "/frontend",
        StaticFiles(directory=str(frontend_path), html=True, check_dir=False),
    )


@app.get("/", tags=["system"])
async def redirect_root():
    """Redirect root to frontend or API docs."""
    if frontend_path.exists():
        return RedirectResponse(
            url="/frontend", status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )
    else:
        return RedirectResponse(
            url="/docs", status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
