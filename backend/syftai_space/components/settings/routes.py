"""Settings API routes."""

from fastapi import APIRouter, Depends

from syftai_space.components.settings.handlers import SettingsHandler
from syftai_space.components.settings.schemas import (
    ProxyConfigRequest,
    ProxyStatusResponse,
    PublicUrlResponse,
    UpdatePublicUrlRequest,
)
from syftai_space.components.tenants.dependency import get_tenant_dependency
from syftai_space.components.tenants.entities import Tenant

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
    def get_public_url(
        handler: SettingsHandler = Depends(get_handler),
    ) -> PublicUrlResponse:
        """Get the current public URL."""
        return handler.get_public_url()

    @router.patch("/public-url", response_model=PublicUrlResponse)
    async def update_public_url(
        request: UpdatePublicUrlRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: SettingsHandler = Depends(get_handler),
    ) -> PublicUrlResponse:
        """Update the public URL.

        Updates the local configuration and syncs to the marketplace.
        """
        return handler.update_public_url(tenant, request.public_url)

    @router.post("/proxy", response_model=ProxyStatusResponse)
    async def configure_proxy(
        request: ProxyConfigRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: SettingsHandler = Depends(get_handler),
    ) -> ProxyStatusResponse:
        """Configure the ngrok proxy tunnel.

        Connects to ngrok with the provided token and persists the configuration.
        The tunnel will automatically reconnect on app restart.
        """
        return await handler.configure_proxy(tenant, request.ngrok_token)

    @router.delete("/proxy", response_model=ProxyStatusResponse)
    async def disconnect_proxy(
        handler: SettingsHandler = Depends(get_handler),
        tenant: Tenant = Depends(get_tenant_dependency),
    ) -> ProxyStatusResponse:
        """Disconnect the ngrok proxy tunnel and clear configuration."""
        return await handler.disconnect_proxy(tenant)

    return router
