"""Settings API routes."""

from fastapi import APIRouter, Depends

from syftai_space.components.settings.handlers import SettingsHandler
from syftai_space.components.settings.schemas import (
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
    async def get_public_url(
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

    return router
