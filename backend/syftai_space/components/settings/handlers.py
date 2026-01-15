"""Settings handlers for business logic."""

from __future__ import annotations

from fastapi import HTTPException
from loguru import logger
from pydantic import HttpUrl

from syftai_space.components.marketplaces.repository import MarketplaceRepository
from syftai_space.components.settings.repository import SettingsRepository
from syftai_space.components.settings.schemas import (
    ProxyStatusResponse,
    PublicUrlResponse,
)
from syftai_space.components.shared.proxy_service import ProxyService
from syftai_space.components.shared.syfthub_client import SyftHubClient, SyftHubError
from syftai_space.components.tenants.entities import Tenant
from syftai_space.config import app_settings


class SettingsHandler:
    """Handler for settings business logic."""

    def __init__(
        self,
        settings_repository: SettingsRepository,
        marketplace_repository: MarketplaceRepository,
        proxy_service: ProxyService | None = None,
    ) -> None:
        """Initialize the settings handler.

        Args:
            settings_repository: Repository for settings persistence
            marketplace_repository: Marketplace repository for syncing to SyftHub
            proxy_service: Optional proxy service for ngrok tunnel management
        """
        self.settings_repository = settings_repository
        self.marketplace_repository = marketplace_repository
        self.proxy_service = proxy_service

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

        # Sync to marketplace
        self.sync_public_url_to_marketplace(tenant, url_str)

        # Update app settings
        app_settings.public_url = HttpUrl(url_str) if url_str else None

        # Return response
        return PublicUrlResponse(public_url=url_str)

    def sync_public_url_to_marketplace(self, tenant: Tenant, url: str) -> None:
        """Sync public URL to marketplace (helper method).

        Args:
            tenant: Tenant context
            url: Public URL to sync
        """

        marketplace = self.marketplace_repository.get_default(tenant.id)

        # If no default marketplace is configured, do nothing
        if not marketplace:
            return

        try:
            logger.info(f"Syncing public URL {url} to marketplace {marketplace.url}")
            with SyftHubClient(str(marketplace.url)) as syfthub:
                syfthub.login(marketplace.email, marketplace.password)
                syfthub.update_profile(domain=url)
        except SyftHubError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to sync public URL to marketplace: {e.message}",
            ) from e

    def initialize_from_config(self, tenants: list[Tenant]) -> None:
        """Initialize settings from config on startup.

        If SYFT_PUBLIC_URL env var is set, it overwrites the database value.
        """
        if not app_settings.public_url:
            return

        for tenant in tenants:
            self.update_public_url(tenant, app_settings.public_url)

    async def configure_proxy(self, tenant: Tenant, token: str) -> ProxyStatusResponse:
        """Configure the ngrok proxy tunnel.

        Connects to ngrok with the provided token and persists the configuration.
        Also syncs the public URL to the marketplace.

        Args:
            tenant: Tenant context for marketplace sync
            token: Ngrok authentication token

        Returns:
            Proxy status response with connection status and public URL

        Raises:
            HTTPException: If proxy service is not configured or connection fails
        """
        if self.proxy_service is None:
            raise HTTPException(
                status_code=404,
                detail="Ngrok proxy service not configured",
            )

        try:
            public_url = await self.proxy_service.connect(token)
        except Exception as e:
            logger.error(f"Failed to connect to ngrok: {e}")
            raise HTTPException(status_code=400, detail=str(e)) from e

        self.sync_public_url_to_marketplace(tenant, public_url)
        self.proxy_service.log_connection_info(app_settings.admin_api_key)

        return ProxyStatusResponse(connected=True, public_url=public_url)

    async def disconnect_proxy(self, tenant: Tenant) -> ProxyStatusResponse:
        """Disconnect the ngrok proxy tunnel and clear configuration.

        Returns:
            Proxy status response indicating disconnected state

        Raises:
            HTTPException: If proxy service is not configured
        """
        if self.proxy_service is None:
            raise HTTPException(
                status_code=404,
                detail="Ngrok proxy service not configured",
            )

        await self.proxy_service.disconnect()
        self.sync_public_url_to_marketplace(tenant, "")
        return ProxyStatusResponse(connected=False, public_url=None)
