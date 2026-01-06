"""Settings API routes."""

from fastapi import APIRouter, Depends

from syftai_space.components.marketplaces.handlers import MarketplaceHandler
from syftai_space.components.marketplaces.repository import MarketplaceRepository
from syftai_space.components.settings.handlers import SettingsHandler
from syftai_space.components.settings.schemas import (
    PublicUrlResponse,
    UpdatePublicUrlRequest,
)
from syftai_space.components.shared.database import Database
from syftai_space.components.tenants.dependency import get_tenant_dependency
from syftai_space.components.tenants.entities import Tenant
from syftai_space.config import app_settings

router = APIRouter()


def get_settings_handler() -> SettingsHandler:
    """Get settings handler instance."""
    db = Database()
    marketplace_repo = MarketplaceRepository(db)
    marketplace_handler = MarketplaceHandler(marketplace_repo)
    return SettingsHandler(marketplace_handler, app_settings)


@router.get("/public-url", response_model=PublicUrlResponse)
def get_public_url(
    handler: SettingsHandler = Depends(get_settings_handler),
) -> PublicUrlResponse:
    """Get the current public URL."""
    return handler.get_public_url()


@router.patch("/public-url", response_model=PublicUrlResponse)
def update_public_url(
    request: UpdatePublicUrlRequest,
    tenant: Tenant = Depends(get_tenant_dependency),
    handler: SettingsHandler = Depends(get_settings_handler),
) -> PublicUrlResponse:
    """Update the public URL.

    Updates the local configuration and syncs to the marketplace.
    """
    return handler.update_public_url(tenant, request.public_url)
