"""Settings handlers for business logic."""

from __future__ import annotations

from fastapi import HTTPException
from loguru import logger
from pydantic import HttpUrl

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.settings.schemas import (
    DiagnosticsResponse,
    ManagedResponse,
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

    async def get_managed(self) -> ManagedResponse:
        """Whether this space runs in managed mode, plus its public URL.

        Managed means a station launched this space (SYFT_CLUSTER_MANAGED_BY
        injected): the frontend then drops self-hosted onboarding affordances
        (SyftHub signup, hub-generated tunnel URL) and pre-fills the public
        URL the station assigned. The URL stays editable — only the tunnel
        flow is refused (see configure_proxy).

        Returns:
            Managed-mode response
        """
        settings = await self.settings_repository.get_settings()
        return ManagedResponse(
            managed=bool(app_settings.cluster.managed_by),
            public_url=settings.public_url,
        )

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

        # Update app settings
        app_settings.public_url = HttpUrl(url_str) if url_str else None

        # Get default marketplace
        marketplace = await self.marketplace_repository.get_default(tenant.id)

        if marketplace is not None:
            # Sync to marketplace
            await self.sync_public_url_to_marketplace(marketplace, url_str)

        # Return response
        return PublicUrlResponse(public_url=url_str)

    async def sync_public_url_to_marketplace(
        self, marketplace: Marketplace, url: str | None
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
        """Seed the public URL from SYFT_PUBLIC_URL on first boot.

        Seed-once, not override: the env only fills an empty database value.
        Once set (seeded or edited by the user), the database wins across
        restarts — otherwise a station-injected URL would silently revert
        manual edits on every pod restart.
        """
        if not app_settings.public_url:
            return

        settings = await self.settings_repository.get_settings()
        if settings.public_url:
            return

        for tenant in tenants:
            await self.update_public_url(tenant, app_settings.public_url)

    async def get_diagnostics(self) -> DiagnosticsResponse:
        """Get the current diagnostics preference.

        Returns:
            Diagnostics response
        """
        enabled = await self.settings_repository.get_diagnostics_enabled()
        return DiagnosticsResponse(enabled=enabled)

    async def update_diagnostics(self, enabled: bool) -> DiagnosticsResponse:
        """Update the diagnostics preference.

        Args:
            enabled: Whether to enable diagnostics

        Returns:
            Updated diagnostics response
        """
        await self.settings_repository.update_diagnostics_enabled(enabled)
        return DiagnosticsResponse(enabled=enabled)

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

    async def configure_proxy(self, tenant: Tenant) -> ProxyStatusResponse:
        """Configure the ngrok proxy tunnel.

        Delegates to ProxyService.connect_with_fallback() which tries stored
        credentials first and falls back to fresh ones from SyftHub.

        Args:
            tenant: Tenant context for marketplace sync

        Returns:
            Proxy status response with connection status and public URL

        Raises:
            HTTPException: If the space is managed, the proxy service is not
                configured, or the connection fails
        """
        # A managed space already has its public URL from the station; a
        # tunnel URL would be synced to the marketplace and overwrite the
        # address buyers are routed through. Manual URL edits stay allowed —
        # only this generated-URL path is refused.
        if app_settings.cluster.managed_by:
            raise HTTPException(
                status_code=409,
                detail="This space's public URL is managed for you — "
                "set a URL directly instead of generating one",
            )

        if self.proxy_service is None:
            raise HTTPException(
                status_code=404,
                detail="Ngrok proxy service not configured",
            )

        # Get default marketplace (needed for URL sync)
        marketplace = await self.marketplace_repository.get_default(tenant.id)

        if not marketplace:
            raise HTTPException(
                status_code=404,
                detail="No default marketplace configured",
            )

        try:
            public_url = await self.proxy_service.connect()
        except SyftHubError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to fetch tunnel credentials: {e.message}",
            ) from e
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
            await self.sync_public_url_to_marketplace(marketplace, None)

        return ProxyStatusResponse(connected=False, public_url=None, has_token=False)
