"""Settings API routes."""

from fastapi import APIRouter, Depends

from syft_space.components.settings.handlers import SettingsHandler
from syft_space.components.settings.schemas import (
    DiagnosticsResponse,
    ProxyStatusResponse,
    PublicUrlResponse,
    UpdateDiagnosticsRequest,
    UpdatePublicUrlRequest,
)
from syft_space.components.shared.sentry import set_diagnostics_enabled
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant

router = APIRouter()


def build_settings_routes(handler: SettingsHandler) -> APIRouter:
    """Build the settings routes.

    Args:
        handler: Settings handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/settings", tags=["settings"])

    def get_handler() -> SettingsHandler:
        """Dependency to get the settings handler."""
        return handler

    @router.get("/public-url", response_model=PublicUrlResponse)
    async def get_public_url(
        handler: SettingsHandler = Depends(get_handler),
    ) -> PublicUrlResponse:
        """Get the current public URL."""
        return await handler.get_public_url()

    @router.patch("/public-url", response_model=PublicUrlResponse)
    async def update_public_url(
        request: UpdatePublicUrlRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: SettingsHandler = Depends(get_handler),
    ) -> PublicUrlResponse:
        """Update the public URL.

        Updates the local configuration and syncs to the marketplace.
        """
        return await handler.update_public_url(tenant, request.public_url)

    @router.get("/diagnostics", response_model=DiagnosticsResponse)
    async def get_diagnostics(
        handler: SettingsHandler = Depends(get_handler),
    ) -> DiagnosticsResponse:
        """Get the current diagnostics preference."""
        return await handler.get_diagnostics()

    @router.patch("/diagnostics", response_model=DiagnosticsResponse)
    async def update_diagnostics(
        request: UpdateDiagnosticsRequest,
        handler: SettingsHandler = Depends(get_handler),
    ) -> DiagnosticsResponse:
        """Update the diagnostics preference."""
        result = await handler.update_diagnostics(request.enabled)
        set_diagnostics_enabled(request.enabled)
        return result

    @router.get("/proxy", response_model=ProxyStatusResponse)
    async def get_proxy_status(
        handler: SettingsHandler = Depends(get_handler),
    ) -> ProxyStatusResponse:
        """Get the current proxy tunnel status."""
        return await handler.get_proxy_status()

    @router.post("/proxy", response_model=ProxyStatusResponse)
    async def configure_proxy(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: SettingsHandler = Depends(get_handler),
    ) -> ProxyStatusResponse:
        """Configure the ngrok proxy tunnel.

        Fetches tunnel credentials from SyftHub, connects to ngrok, and persists
        the configuration. The tunnel will automatically reconnect on app restart.
        """
        return await handler.configure_proxy(tenant)

    @router.delete("/proxy", response_model=ProxyStatusResponse)
    async def disconnect_proxy(
        handler: SettingsHandler = Depends(get_handler),
        tenant: Tenant = Depends(get_tenant_dependency),
    ) -> ProxyStatusResponse:
        """Disconnect the ngrok proxy tunnel and clear configuration."""
        return await handler.disconnect_proxy(tenant)

    return router
