"""Settings handlers for business logic."""

from fastapi import HTTPException

from syftai_space.components.marketplaces.handlers import MarketplaceHandler
from syftai_space.components.settings.schemas import PublicUrlResponse
from syftai_space.components.shared.syfthub_client import SyftHubClient
from syftai_space.components.tenants.entities import Tenant
from syftai_space.config import AppSettings


class SettingsHandler:
    """Handler for settings business logic."""

    def __init__(
        self, marketplace_handler: MarketplaceHandler, config: AppSettings
    ) -> None:
        """Initialize the settings handler.

        Args:
            marketplace_handler: Marketplace handler for syncing to SyftHub
            config: Application settings
        """
        self.marketplace_handler = marketplace_handler
        self.config = config

    def get_public_url(self) -> PublicUrlResponse:
        """Get the current public URL.

        Returns:
            Public URL response
        """
        return PublicUrlResponse(public_url=self.config.public_url)

    def update_public_url(self, tenant: Tenant, new_url: str) -> PublicUrlResponse:
        """Update the public URL.

        Updates the local config and syncs to SyftHub marketplace.

        Args:
            tenant: Tenant context
            new_url: New public URL to set

        Returns:
            Updated public URL response

        Raises:
            HTTPException: If sync to marketplace fails
        """
        # Update local config
        self.config.public_url = new_url

        # Sync to SyftHub if marketplace is configured
        try:
            marketplace = self.marketplace_handler.get_default_marketplace(tenant)
            syfthub = SyftHubClient(marketplace.url)
            syfthub.login(marketplace.email, marketplace.password)
            syfthub.update_profile(domain=new_url)
        except HTTPException as e:
            if e.status_code == 404:
                # No marketplace configured, just update local config
                pass
            else:
                raise HTTPException(
                    status_code=e.status_code,
                    detail=f"Failed to sync public URL to marketplace: {e.detail}",
                ) from e
        except Exception as e:
            raise HTTPException(
                status_code=getattr(e, "status_code", 500),
                detail=f"Failed to sync public URL to marketplace: {str(e)}",
            ) from e

        return PublicUrlResponse(public_url=new_url)
