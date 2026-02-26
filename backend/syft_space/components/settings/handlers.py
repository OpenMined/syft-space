"""Settings handlers for business logic."""

from __future__ import annotations

from fastapi import HTTPException
from loguru import logger
from pydantic import HttpUrl

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.settings.schemas import (
    ProxyStatusResponse,
    PublicUrlResponse,
)
from syft_space.components.shared.proxy_service import ProxyService
from syft_space.components.shared.syfthub_client import SyftHubClient, SyftHubError
from syft_space.components.tenants.entities import Tenant
from syft_space.config import app_settings


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

    async def get_public_url(self) -> PublicUrlResponse:
        """Get the current public URL from database (source of truth).

        Returns:
            Public URL response
        """
        settings = await self.settings_repository.get_settings()
        return PublicUrlResponse(public_url=settings.public_url)

    async def update_public_url(
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
        await self.settings_repository.update_public_url(url_str)

        # Get default marketplace
        marketplace = await self.marketplace_repository.get_default(tenant.id)

        if marketplace is not None:
            # Sync to marketplace
            await self.sync_public_url_to_marketplace(marketplace, url_str)

        # Update app settings
        app_settings.public_url = HttpUrl(url_str) if url_str else None

        # Return response
        return PublicUrlResponse(public_url=url_str)

    async def sync_public_url_to_marketplace(
        self, marketplace: Marketplace, url: str
    ) -> None:
        """Sync public URL to marketplace (helper method).

        Args:
            marketplace: Marketplace to sync to
            url: Public URL to sync
        """

        try:
            logger.info(f"Syncing public URL {url} to marketplace {marketplace.url}")
            async with SyftHubClient(str(marketplace.url)) as syfthub:
                await syfthub.login(marketplace.email, marketplace.password)
                await syfthub.update_profile(domain=url)
        except SyftHubError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to sync public URL to marketplace: {e.message}",
            ) from e

    async def initialize_from_config(self, tenants: list[Tenant]) -> None:
        """Initialize settings from config on startup.

        If SYFT_PUBLIC_URL env var is set, it overwrites the database value.
        """
        if not app_settings.public_url:
            return

        for tenant in tenants:
            await self.update_public_url(tenant, app_settings.public_url)

    async def get_proxy_status(self) -> ProxyStatusResponse:
        """Get the current proxy tunnel status.

        Returns:
            Proxy status response with connection status, public URL, and token presence
        """
        if self.proxy_service is None:
            return ProxyStatusResponse(
                connected=False, public_url=None, has_token=False
            )

        has_token = bool(await self.settings_repository.get_ngrok_token())
        return ProxyStatusResponse(
            connected=self.proxy_service.is_connected(),
            public_url=self.proxy_service.get_public_url(),
            has_token=has_token,
        )

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

        # Get default marketplace
        marketplace = await self.marketplace_repository.get_default(tenant.id)

        if not marketplace:
            raise HTTPException(
                status_code=404,
                detail="No default marketplace configured",
            )

        try:
            public_url = await self.proxy_service.connect(token, marketplace.username)
        except Exception as e:
            logger.exception(f"Failed to connect to ngrok: {e}")
            raise HTTPException(status_code=400, detail=str(e)) from e

        await self.sync_public_url_to_marketplace(marketplace, public_url)
        self.proxy_service.log_connection_info()

        return ProxyStatusResponse(
            connected=True, public_url=public_url, has_token=True
        )

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

        marketplace = await self.marketplace_repository.get_default(tenant.id)

        await self.proxy_service.disconnect()
        if marketplace is not None:
            await self.sync_public_url_to_marketplace(marketplace, "")

        return ProxyStatusResponse(connected=False, public_url=None, has_token=False)
