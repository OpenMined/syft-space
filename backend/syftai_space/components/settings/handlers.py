"""Settings handlers for business logic."""

from fastapi import HTTPException
from loguru import logger
from pydantic import HttpUrl

from syftai_space.components.marketplaces.handlers import MarketplaceHandler
from syftai_space.components.settings.repository import SettingsRepository
from syftai_space.components.settings.schemas import PublicUrlResponse
from syftai_space.components.shared.syfthub_client import SyftHubClient, SyftHubError
from syftai_space.components.tenants.entities import Tenant
from syftai_space.config import app_settings


class SettingsHandler:
    """Handler for settings business logic."""

    def __init__(
        self,
        settings_repository: SettingsRepository,
        marketplace_handler: MarketplaceHandler,
    ) -> None:
        """Initialize the settings handler.

        Args:
            settings_repository: Repository for settings persistence
            marketplace_handler: Marketplace handler for syncing to SyftHub
            config: Application settings
        """
        self.settings_repository = settings_repository
        self.marketplace_handler = marketplace_handler

    def get_public_url(self) -> PublicUrlResponse:
        """Get the current public URL from database (source of truth).

        Returns:
            Public URL response
        """
        settings = self.settings_repository.get_settings()
        return PublicUrlResponse(public_url=settings.public_url)

    def update_public_url(
        self, tenant: Tenant, new_url: HttpUrl | str
    ) -> PublicUrlResponse:
        """Update the public URL.

        Updates the database (source of truth) and syncs to SyftHub marketplace.

        Args:
            tenant: Tenant context
            new_url: New public URL to set (HttpUrl or str)

        Returns:
            Updated public URL response

        Raises:
            HTTPException: If sync to marketplace fails
        """
        # Convert to string for storage
        url_str = str(new_url) if new_url else None

        # Update database (source of truth)
        self.settings_repository.update_public_url(url_str)

        # Sync to SyftHub if marketplace is configured
        try:
            marketplace = self.marketplace_handler.get_default_marketplace(tenant)
            logger.info(
                f"Updating public URL to {url_str} for marketplace {marketplace.url}"
            )
            with SyftHubClient(str(marketplace.url)) as syfthub:
                syfthub.login(marketplace.email, marketplace.password)
                syfthub.update_profile(domain=url_str)
        except HTTPException as e:
            if e.status_code == 404:
                # No marketplace configured, just update local config
                pass
            else:
                raise
        except SyftHubError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to sync public URL to marketplace: {e.message}",
            ) from e

        app_settings.public_url = HttpUrl(url_str) if url_str else None
        return PublicUrlResponse(public_url=url_str)

    def initialize_from_config(self, tenants: list[Tenant]) -> None:
        """Initialize settings from config on startup.

        If SYFT_PUBLIC_URL env var is set, it overwrites the database value.
        """
        if not app_settings.public_url:
            return

        for tenant in tenants:
            self.update_public_url(tenant, app_settings.public_url)
