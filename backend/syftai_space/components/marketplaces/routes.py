"""Marketplace API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syftai_space.components.marketplaces.handlers import MarketplaceHandler
from syftai_space.components.marketplaces.schemas import (
    CreateMarketplaceRequest,
    MarketplaceListItem,
    MarketplaceResponse,
    UpdateMarketplaceRequest,
)
from syftai_space.components.tenants.dependency import get_tenant_dependency
from syftai_space.components.tenants.entities import Tenant


def build_marketplace_routes(handler: MarketplaceHandler) -> APIRouter:
    """Build the marketplace routes.

    Args:
        handler: Marketplace handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/marketplaces", tags=["marketplaces"])

    def get_handler() -> MarketplaceHandler:
        """Dependency to get the marketplace handler."""
        return handler

    @router.post("/", response_model=MarketplaceResponse, status_code=201)
    async def create_marketplace(
        request: CreateMarketplaceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Register a new marketplace.

        Args:
            request: Marketplace creation request with URL and credentials
            tenant: Current tenant (injected)

        Returns:
            Created marketplace details
        """
        return handler.create_marketplace(request, tenant)

    @router.get("/check-username/{username}", response_model=bool)
    async def check_username_availability(
        username: str,
        handler: MarketplaceHandler = Depends(get_handler),
        url: str | None = None,
    ) -> bool:
        """Check if a username is available.
        Args:
            username: Username to check
            handler: Marketplace handler instance
            url: URL of the Marketplace
        Returns:
            True if username is available, False otherwise.
        """
        return handler.check_username_availability(url, username)

    @router.get("/", response_model=list[MarketplaceListItem])
    async def list_marketplaces(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> list[MarketplaceListItem]:
        """List all registered marketplaces.

        Args:
            tenant: Current tenant (injected)

        Returns:
            List of marketplaces with summary information
        """
        return handler.list_marketplaces(tenant)

    @router.get("/{id}", response_model=MarketplaceResponse)
    async def get_marketplace(
        id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Get details of a specific marketplace.

        Args:
            id: Marketplace ID
            tenant: Current tenant (injected)

        Returns:
            Marketplace details (password not included)
        """
        return handler.get_marketplace(id, tenant)

    @router.patch("/{id}", response_model=MarketplaceResponse)
    async def update_marketplace(
        id: UUID,
        request: UpdateMarketplaceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Update a marketplace (partial update).

        Allows updating name, URL, email, password, and/or is_active status.
        Name and URL must remain unique per tenant.

        Args:
            id: Marketplace ID
            request: Update request with fields to update
            tenant: Current tenant (injected)

        Returns:
            Updated marketplace details

        Raises:
            422 Unprocessable Entity: If no fields provided
            404 Not Found: If marketplace not found
            409 Conflict: If new name/URL already exists
        """
        return handler.update_marketplace(id, request, tenant)

    @router.delete("/{id}", response_model=dict[str, str])
    async def delete_marketplace(
        id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a marketplace.

        Cannot delete the default marketplace (SyftHub).

        Args:
            id: Marketplace ID
            tenant: Current tenant (injected)

        Returns:
            Success message
        """
        return handler.delete_marketplace(id, tenant)

    return router
