"""Marketplace handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException

from syftai_space.components.marketplaces.entities import Marketplace
from syftai_space.components.marketplaces.repository import MarketplaceRepository
from syftai_space.components.marketplaces.schemas import (
    CreateMarketplaceRequest,
    MarketplaceListItem,
    MarketplaceResponse,
    UpdateMarketplaceRequest,
)
from syftai_space.components.shared.syfthub_client import SyftHubClient
from syftai_space.components.tenants.entities import Tenant
from syftai_space.config import app_settings


class MarketplaceHandler:
    """Handler for marketplace business logic."""

    def __init__(self, repository: MarketplaceRepository):
        """Initialize the marketplace handler.

        Args:
            repository: Marketplace repository
        """
        self.repository = repository

    def create_marketplace(
        self, request: CreateMarketplaceRequest, tenant: Tenant
    ) -> MarketplaceResponse:
        """Create a new marketplace.

        Args:
            request: Marketplace creation request
            tenant: Tenant context

        Returns:
            Created marketplace
        """
        url_str = str(request.url)
        syfthub_client = SyftHubClient(url_str)

        try:
            user_profile = syfthub_client.register(
                username=request.username,
                email=request.email,
                full_name=request.name,
                password=request.password,
                accounting_service_url=request.accounting_url,
                accounting_password=request.accounting_password,
            )

            # If public URL is set, update the domain
            if app_settings.public_url:
                syfthub_client.update_profile(domain=app_settings.public_url)

        except Exception as e:
            raise HTTPException(status_code=e.status_code, detail=e.message) from e

        # Check if the marketplace should be set as default
        # If the default marketplace URL is the same as the marketplace URL,
        # set it as default
        set_as_default = app_settings.default_marketplace_url == url_str

        # Create marketplace entity
        marketplace = Marketplace(
            tenant_id=tenant.id,
            name=user_profile.full_name,
            username=user_profile.username,
            url=url_str,
            email=user_profile.email,
            password=user_profile.password,
            is_default=set_as_default,
            is_active=True,
        )

        # Save to database
        created = self.repository.create(marketplace)

        return MarketplaceResponse.model_validate(created)

    def check_username_availability(self, url: str | None, username: str) -> bool:
        """Check if a username is available.
        Args:
            url: URL of the Marketplace
            username: Username to check
        Returns:
            True if username is available, False otherwise.
        """

        url = app_settings.default_marketplace_url if url is None else url
        syfthub_client = SyftHubClient(url)
        return syfthub_client._is_username_available(username)

    def list_marketplaces(
        self, tenant: Tenant, url: str | None = None
    ) -> list[MarketplaceListItem]:
        """List all marketplaces for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of marketplaces
        """
        marketplaces = self.repository.get_all(tenant.id)
        return [MarketplaceListItem.model_validate(m) for m in marketplaces]

    def get_marketplace(self, id: UUID, tenant: Tenant) -> MarketplaceResponse:
        """Get a specific marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            tenant: Tenant context

        Returns:
            Marketplace details

        Raises:
            HTTPException: If marketplace not found
        """
        marketplace = self.repository.get_by_id(id, tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return MarketplaceResponse.model_validate(marketplace)

    def update_marketplace(
        self, id: UUID, request: UpdateMarketplaceRequest, tenant: Tenant
    ) -> MarketplaceResponse:
        """Update a marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            request: Update request with fields to update
            tenant: Tenant context

        Returns:
            Updated marketplace details

        Raises:
            HTTPException: If marketplace not found
        """
        # Convert URL to string if provided
        url_str = str(request.url) if request.url else None

        updated = self.repository.update(
            id,
            tenant.id,
            name=request.name,
            url=url_str,
            email=request.email,
            password=request.password,
            username=request.username,
            is_active=request.is_active,
        )

        if not updated:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return MarketplaceResponse.model_validate(updated)

    def delete_marketplace(self, id: UUID, tenant: Tenant) -> dict:
        """Delete a marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            tenant: Tenant context

        Returns:
            Success message

        Raises:
            HTTPException: If marketplace not found or is default marketplace
        """
        # Check if marketplace exists and is not default
        marketplace = self.repository.get_by_id(id, tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        if marketplace.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the default marketplace (SyftHub)",
            )

        deleted = self.repository.delete(id, tenant.id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return {"message": f"Successfully deleted marketplace '{marketplace.name}'"}
