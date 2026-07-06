"""Main FastAPI application."""

import os

# Disable ChromaDB's PostHog telemetry — transitive dependency, no user consent.
# Must be set before any chromadb import.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

import syft_space.components.shared.logging_config  # noqa: F401, I001

# Import analytics components
from syft_space.components.analytics.collector import QueryEventCollector
from syft_space.components.analytics.entities import QueryEventStatus
from syft_space.components.analytics.handlers import AnalyticsHandler
from syft_space.components.analytics.migrations import run_analytics_migrations
from syft_space.components.analytics.repository import QueryEventRepository
from syft_space.components.analytics.routes import build_analytics_routes
from syft_space.components.analytics.text_processing import extract_user_query

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
from syft_space.components.datasets.selection_repository import (
    DatasetSelectionRepository,
)

# Import endpoint heartbeat manager
from syft_space.components.endpoints.endpoint_heartbeat_manager import (
    EndpointHeartbeatManager,
)
from syft_space.components.endpoints.handlers import EndpointHandler
from syft_space.components.endpoints.interfaces import (
    QueryOutcome,
    QueryOutcomeEvent,
)
from syft_space.components.endpoints.publish_handler import PublishEndpointHandler
from syft_space.components.endpoints.query_handler import QueryEndpointHandler
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.routes import build_endpoint_routes

# Import feedback components
from syft_space.components.feedback.handlers import FeedbackHandler
from syft_space.components.feedback.routes import build_feedback_routes

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

# Import payment components
from syft_space.components.payments.gateway.balance_service import BalanceService
from syft_space.components.payments.gateway.dependencies import (
    make_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler
from syft_space.components.payments.gateway.payment_ledger import PaymentLedger
from syft_space.components.payments.gateway.stripe.gateway import StripeGateway
from syft_space.components.payments.gateway.xendit.gateway import XenditGateway
from syft_space.components.payments.mpp.handlers import MppPaymentHandler
from syft_space.components.payments.routes import build_payment_routes
from syft_space.components.policies.capability_checker import CapabilityChecker
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

# Import async utilities
from syft_space.components.shared.async_utils import run_after_event

# Import database
from syft_space.components.shared.database import AsyncDatabase, SQLiteConfig

# Import lifecycle protocol
from syft_space.components.shared.lifecycle import LifecycleService

# Import proxy service
from syft_space.components.shared.proxy_service import ProxyService
from syft_space.components.shared.sentry import init_sentry, set_diagnostics_enabled
from syft_space.components.shared.syfthub_client import SyftHubClient
from syft_space.components.sources import register_builtin_sources
from syft_space.components.sources.local_file.local_file_watcher import (
    get_local_file_watcher,
)

# Import tenant components
from syft_space.components.tenants.entities import Tenant
from syft_space.components.tenants.handlers import TenantHandler
from syft_space.components.tenants.middleware import TenantMiddleware
from syft_space.components.tenants.repository import TenantRepository
from syft_space.components.tenants.routes import build_tenant_routes
from syft_space.components.vector_stores import register_builtin_vector_stores

# Import wallet components
from syft_space.components.wallets.gateway.stripe.provider import StripeWalletProvider
from syft_space.components.wallets.gateway.xendit.provider import XenditWalletProvider
from syft_space.components.wallets.handlers import WalletHandler
from syft_space.components.wallets.mpp.provider import MppWalletProvider
from syft_space.components.wallets.repository import WalletRepository
from syft_space.components.wallets.routes import build_wallet_routes
from syft_space.config import app_settings


async def _sync_public_url_safe(
    handler: SettingsHandler,
    tenant: Tenant,
    proxy_service: ProxyService,
) -> None:
    """Sync public URL to marketplace without blocking startup.

    This is a fire-and-forget helper that wraps the marketplace sync with
    timeout handling. If the sync fails or times out, the server continues
    starting - the sync is not critical for basic operation.

    Args:
        handler: Settings handler instance
        tenant: Tenant context
        proxy_service: Proxy service to check connection and get URL
    """
    try:
        if not proxy_service.is_connected():
            logger.debug("Proxy not connected, skipping public URL sync")
            return

        public_url = proxy_service.get_public_url()
        if not public_url:
            logger.debug("No public URL available, skipping sync")
            return

        await asyncio.wait_for(
            handler.update_public_url(tenant, public_url),
            timeout=10.0,  # 10 second timeout
        )
        logger.info("Public URL synced to marketplace successfully")
    except asyncio.TimeoutError:
        logger.warning("Marketplace sync timed out - server will continue starting")
    except Exception as e:
        logger.warning(f"Marketplace sync failed: {e} - server will continue starting")


async def _sync_endpoints_safe(handler: PublishEndpointHandler, tenant: Tenant) -> None:
    """Sync published endpoints to marketplaces without blocking startup.

    This is a fire-and-forget helper that syncs all published endpoints to their
    respective marketplaces. If the sync fails or times out, the server continues
    operating - eventual consistency is achieved via frontend publish calls.

    Args:
        handler: Endpoint handler instance
        tenant: Tenant context
    """
    try:
        results = await asyncio.wait_for(
            handler.sync_endpoints_to_marketplaces(tenant),
            timeout=60.0,  # 60 second timeout for multi-marketplace sync
        )
        if results:
            total = sum(len(slugs) for slugs in results.values())
            logger.info(
                f"Startup endpoint sync completed: {total} endpoints to {len(results)} marketplaces"
            )
        else:
            logger.debug("No published endpoints to sync on startup")
    except asyncio.TimeoutError:
        logger.warning("Endpoint sync timed out - server will continue running")
    except Exception as e:
        logger.warning(f"Endpoint sync failed: {e} - server will continue running")


async def _warmup_dataset_types(handler: DatasetHandler) -> None:
    """Warm up dataset type imports in background to avoid first-request latency."""
    try:
        # Run in a thread to avoid blocking the event loop during heavy imports
        await asyncio.to_thread(handler.list_dataset_types)
        logger.info("Dataset type warm-up complete")
    except Exception as e:
        logger.warning(f"Dataset type warm-up failed: {e}")


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
        logger.exception(f"Failed to initialize settings from config: {e}")

    return default_tenant


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - handles startup and shutdown events."""
    # 0. Initialize Sentry (events gated by diagnostics setting)
    init_sentry(debug=app_settings.debug)

    # 1. Run database migrations
    await database.run_migrations(reset=app_settings.reset_db)

    # 1.1. Run analytics database migrations (separate SQLite file)
    await run_analytics_migrations(
        analytics_database.engine, reset=app_settings.reset_db
    )

    # 2. Setup tenant and settings
    default_tenant = await _setup_tenant_and_settings(
        tenant_repository, settings_handler
    )
    app.state.default_tenant = default_tenant

    # 2.1. Load diagnostics preference for Sentry gating
    try:
        diagnostics = await settings_handler.get_diagnostics()
        set_diagnostics_enabled(diagnostics.enabled)
    except Exception as e:
        logger.warning(f"Failed to load diagnostics preference: {e}")

    # 3. Define lifecycle services (startup order: proxy → provisioner →
    # local_file_watcher → ingestion → endpoint_heartbeat). Watcher must
    # come before ingestion so the shared Observer is owned by a service
    # whose shutdown ordering guarantees it joins after all source tasks.
    local_file_watcher = get_local_file_watcher()
    services: list[tuple[str, LifecycleService]] = [
        ("proxy", proxy_service),
        ("provisioner", provisioner_manager),
        ("local_file_watcher", local_file_watcher),
        ("ingestion", ingestion_manager),
        ("endpoint_heartbeat", endpoint_heartbeat_manager),
    ]

    # 3.1. Set tenant for endpoint heartbeat manager
    if default_tenant:
        endpoint_heartbeat_manager.set_tenant(default_tenant)

    # 3.2. Set credentials provider for proxy auto-connect retry
    if default_tenant:

        async def _fetch_tunnel_credentials() -> tuple[str, str]:
            marketplace = await marketplace_repository.get_default(default_tenant.id)
            if not marketplace:
                raise RuntimeError("No default marketplace configured")
            async with SyftHubClient(str(marketplace.url)) as client:
                await client.login(marketplace.email, marketplace.password)
                creds = await client.get_tunnel_credentials()
            return (creds.auth_token, creds.domain)

        proxy_service.set_credentials_provider(_fetch_tunnel_credentials)

    # 4. Create coordination event for provisioner → ingestion ordering
    # This event ensures ingestion waits for provisioners to be ready
    provisioner_ready_event = asyncio.Event()
    provisioner_manager.set_startup_complete_event(provisioner_ready_event)
    ingestion_manager.set_provisioner_ready_event(provisioner_ready_event)

    # 4.1. Create coordination event for proxy → sync tasks ordering
    # This event ensures sync tasks wait for proxy connection attempt to complete
    proxy_ready_event = asyncio.Event()
    proxy_service.set_ready_event(proxy_ready_event)

    # 5. Start all services
    for name, service in services:
        try:
            await service.startup()
        except Exception as e:
            logger.exception(f"Failed to start {name}: {e}")

    # 6. Fire-and-forget sync tasks (wait for proxy to be ready first)
    if default_tenant:
        # Sync public URL to marketplace
        asyncio.create_task(
            run_after_event(
                proxy_ready_event,
                _sync_public_url_safe,
                settings_handler,
                default_tenant,
                proxy_service,
            )
        )

        # Sync endpoints to marketplaces
        asyncio.create_task(
            run_after_event(
                proxy_ready_event,
                _sync_endpoints_safe,
                publish_endpoint_handler,
                default_tenant,
            )
        )

    # 7. Fire-and-forget: Warm dataset type imports (no proxy dependency)
    logger.info("Starting dataset type warm-up in background")
    asyncio.create_task(_warmup_dataset_types(dataset_handler))

    yield  # Application runs here

    # 8. Shutdown all services (reverse order: ingestion → provisioner → proxy)
    for name, service in reversed(services):
        try:
            await service.shutdown()
        except Exception as e:
            logger.exception(f"Error shutting down {name}: {e}")

    # 8.1. Drain any in-flight analytics capture tasks. Bounded so a slow
    # SQLite write doesn't hang shutdown; events past the timeout are dropped
    # (logged by the collector if they raise).
    if _pending_event_tasks:
        await asyncio.wait(
            _pending_event_tasks,
            timeout=5.0,
            return_when=asyncio.ALL_COMPLETED,
        )

    # 9. Dispose database engines (close all pooled connections)
    await database.dispose()
    await analytics_database.dispose()


# Initialize FastAPI app
app = FastAPI(
    title="Syft Space",
    description="Syft Space - RAG platform with datasets, models, endpoints, and policies",
    version="0.1.0",
    debug=app_settings.debug,
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)


# Initialize database (async-only)
db_path = app_settings.sqlite_db_path.resolve()
db_config = SQLiteConfig(db_path)
database = AsyncDatabase(db_config)

# Initialize analytics database (separate SQLite file)
analytics_db_path = app_settings.analytics_db_path.resolve()
analytics_db_config = SQLiteConfig(analytics_db_path, enable_foreign_keys=False)
analytics_database = AsyncDatabase(analytics_db_config)

# Initialize analytics repository and collector
event_repository = QueryEventRepository(analytics_database)
event_collector = QueryEventCollector(event_repository)

# Initialize repositories
tenant_repository = TenantRepository(database)
dataset_repository = DatasetRepository(database)
provisioner_state_repository = ProvisionerStateRepository(database)
model_repository = ModelRepository(database)
policy_repository = PolicyRepository(database)
endpoint_repository = EndpointRepository(database)
ingestion_job_repository = IngestionJobRepository(database)
dataset_selection_repository = DatasetSelectionRepository(database)
marketplace_repository = MarketplaceRepository(database)
wallet_repository = WalletRepository(database)

# Explicit type registration - no import side effects
logger.info("Registering sources ...")
register_builtin_sources()
logger.info("Registering vector stores ...")
register_builtin_vector_stores()
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
    DATASET_TYPE_REGISTRY,
    dataset_repository,
    provisioner_state_repository,
    endpoint_repository=endpoint_repository,
    selection_repository=dataset_selection_repository,
)
model_handler = ModelHandler(MODEL_TYPE_REGISTRY, model_repository)
capability_checker = CapabilityChecker(
    wallet_lookup=wallet_repository,
    endpoint_lookup=endpoint_repository,
    endpoint_policy_query=policy_repository,
)
policy_handler = PolicyHandler(
    POLICY_TYPE_REGISTRY, policy_repository, capability_checker
)
marketplace_handler = MarketplaceHandler(marketplace_repository)

# Initialize wallet handler with providers (Clean Architecture: concrete adapters injected here)
wallet_providers = {
    "mpp": MppWalletProvider(),
    "xendit": XenditWalletProvider(),
    "stripe": StripeWalletProvider(),
}

# Initialize payment handlers
mpp_payment_handler = MppPaymentHandler(wallet_repository=wallet_repository)


# Initialize gateway payment components.
# PaymentLedger is the unit-of-work that hands the three payment repos a
# shared session. Each business operation borrows a fresh ledger.
def payment_ledger_factory() -> PaymentLedger:
    return PaymentLedger(database)


balance_service = BalanceService(payment_ledger_factory)
gateway_payment_handler = PaymentHandler(
    balance_service=balance_service,
    payment_ledger_factory=payment_ledger_factory,
    wallet_repository=wallet_repository,
    endpoint_repository=endpoint_repository,
    gateways={"xendit": XenditGateway(), "stripe": StripeGateway()},
)
get_verified_sender_email = make_verified_sender_email_dependency(
    marketplace_repository
)


# Wallet deletion guard (dependency inversion — wallets don't import payments).
# Returns an error string if the wallet has live balance or pending invoices.
async def check_wallet_deletable(wallet_id, tenant_id) -> str | None:
    async with payment_ledger_factory() as ledger:
        if await ledger.invoices.has_pending_by_wallet_id(wallet_id, tenant_id):
            return (
                "Cannot delete wallet with pending invoices. "
                "Wait for them to settle or pass force=true."
            )
        if await ledger.balances.has_nonzero_balance_by_wallet(wallet_id, tenant_id):
            return (
                "Cannot delete wallet while users have remaining balance. "
                "Refund users or pass force=true."
            )
    return None


wallet_handler = WalletHandler(
    repository=wallet_repository,
    providers=wallet_providers,
    deletion_check=check_wallet_deletable,
)

# Initialize settings repository and proxy service
settings_repository = SettingsRepository(database)
proxy_service = ProxyService(settings_repository)


# Endpoint deletion check — wallet-scoped balance no longer hangs off endpoints,
# so the only block is pending invoices that *originated* from this endpoint.
async def check_endpoint_deletable(endpoint_id, tenant_id) -> str | None:
    return None


# Analytics adapter (dependency inversion — endpoints doesn't import analytics).
# Translates a domain QueryOutcomeEvent into an analytics row + cost lines and
# fires the capture in the background. The set + done-callback holds task
# references against GC; the lifespan drains in-flight tasks on shutdown.
_OUTCOME_TO_STATUS = {
    QueryOutcome.SUCCESS: QueryEventStatus.SUCCESS,
    QueryOutcome.NOT_FOUND: QueryEventStatus.NOT_FOUND,
    QueryOutcome.NOT_PUBLISHED: QueryEventStatus.NOT_PUBLISHED,
    QueryOutcome.PAYMENT_REQUIRED: QueryEventStatus.PAYMENT_REQUIRED,
    QueryOutcome.POLICY_VIOLATION: QueryEventStatus.POLICY_VIOLATION,
    QueryOutcome.INTERNAL_ERROR: QueryEventStatus.INTERNAL_ERROR,
}
_pending_event_tasks: set[asyncio.Task] = set()


def _cost_lines_from_response(
    response: dict | None,
) -> list[tuple[str, float, str]]:
    """Extract a single (component, amount, currency) tuple from the
    response's top-level cost/currency.

    Returns an empty list when no charge applied (free tier, failed
    request, etc.). The "component" column is kept as "query" for the
    analytics table even though we no longer break costs down by
    response component — one row per query is the canonical record.
    """
    if not response:
        return []
    cost = response.get("cost")
    currency = response.get("currency")
    if cost is None or currency is None:
        return []
    return [("query", float(cost), str(currency))]


async def report_query_event(event: QueryOutcomeEvent) -> None:
    """Fire-and-forget the analytics capture.

    All translation work runs inside the task body so the request handler's
    awaited path does only task scheduling.
    """

    async def _capture() -> None:
        response_dict = event.response.model_dump() if event.response else None
        cost_lines = (
            _cost_lines_from_response(response_dict)
            if event.outcome == QueryOutcome.SUCCESS
            else []
        )
        query_text = extract_user_query(event.messages)[:4000]
        await event_collector.capture(
            tenant_id=event.tenant_id,
            endpoint_id=event.endpoint_id,
            endpoint_slug=event.endpoint_slug,
            dataset_id=event.dataset_id,
            user_email=event.user_email,
            status=_OUTCOME_TO_STATUS[event.outcome].value,
            query_text=query_text,
            cost_lines=cost_lines,
        )

    task = asyncio.create_task(_capture())
    _pending_event_tasks.add(task)
    task.add_done_callback(_pending_event_tasks.discard)


endpoint_handler = EndpointHandler(
    endpoint_repository=endpoint_repository,
    dataset_repository=dataset_repository,
    model_repository=model_repository,
    selection_repository=dataset_selection_repository,
    deletion_check=check_endpoint_deletable,
)
query_endpoint_handler = QueryEndpointHandler(
    endpoint_repository=endpoint_repository,
    dataset_repository=dataset_repository,
    model_repository=model_repository,
    policy_repository=policy_repository,
    dataset_registry=DATASET_TYPE_REGISTRY,
    model_registry=MODEL_TYPE_REGISTRY,
    policy_registry=POLICY_TYPE_REGISTRY,
    wallet_repository=wallet_repository,
    balance_service=balance_service,
    event_reporter=report_query_event,
    marketplace_repository=marketplace_repository,
)
publish_endpoint_handler = PublishEndpointHandler(
    endpoint_repository=endpoint_repository,
    marketplace_repository=marketplace_repository,
    dataset_repository=dataset_repository,
    model_repository=model_repository,
    dataset_registry=DATASET_TYPE_REGISTRY,
    model_registry=MODEL_TYPE_REGISTRY,
    wallet_repository=wallet_repository,
    wallet_providers=wallet_providers,
)
tenant_handler = TenantHandler(tenant_repository)

# Initialize analytics handler (cross-database: analytics DB + main DB)
analytics_handler = AnalyticsHandler(
    query_event_repository=event_repository,
    endpoint_repository=endpoint_repository,
)

# Initialize settings handler with proxy service
settings_handler = SettingsHandler(
    settings_repository, marketplace_repository, proxy_service
)
feedback_handler = FeedbackHandler(marketplace_repository)

# Initialize ingestion manager and handler
ingestion_manager = IngestionManager(
    dataset_repository=dataset_repository,
    ingestion_repository=ingestion_job_repository,
    selection_repository=dataset_selection_repository,
    registry=DATASET_TYPE_REGISTRY,
)
ingestion_handler = IngestionHandler(
    ingestion_manager=ingestion_manager,
    dataset_repository=dataset_repository,
)

# Initialize lifecycle managers (independent, ordered in lifespan)
provisioner_manager = ProvisionerManager(dataset_handler)
endpoint_heartbeat_manager = EndpointHeartbeatManager(
    health_checker=publish_endpoint_handler,
    marketplace_repository=marketplace_repository,
    settings_repository=settings_repository,
    enabled=app_settings.heartbeat_enabled,
    check_interval=app_settings.health_check_interval,
)
app.state.provisioner_manager = provisioner_manager
app.state.ingestion_manager = ingestion_manager
app.state.proxy_service = proxy_service
app.state.endpoint_heartbeat_manager = endpoint_heartbeat_manager
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
router.include_router(
    build_endpoint_routes(
        endpoint_handler,
        query_endpoint_handler,
        publish_endpoint_handler,
    )
)
router.include_router(build_tenant_routes(tenant_handler))
router.include_router(build_ingestion_routes(ingestion_handler))
router.include_router(build_marketplace_routes(marketplace_handler))
router.include_router(build_settings_routes(settings_handler))
router.include_router(build_feedback_routes(feedback_handler))
router.include_router(build_wallet_routes(wallet_handler))
router.include_router(
    build_payment_routes(
        mpp_handler=mpp_payment_handler,
        gateway_handler=gateway_payment_handler,
        get_verified_sender_email=get_verified_sender_email,
    )
)
router.include_router(build_analytics_routes(analytics_handler))


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8080",
        "https://syfthub.openmined.org",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_origin_regex=r"^https://[\w-]+\.syfthub\.ngrok\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    uvicorn.run(app, host=app_settings.host, port=app_settings.port)
