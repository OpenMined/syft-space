"""Marketplace API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_space.components.marketplaces.handlers import MarketplaceHandler
from syft_space.components.marketplaces.schemas import (
    BalanceResponse,
    ConnectMarketplaceRequest,
    MarketplaceListItem,
    MarketplaceResponse,
    RegisterMarketplaceRequest,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


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

    @router.post("/register", response_model=MarketplaceResponse, status_code=201)
    async def register_marketplace(
        request: RegisterMarketplaceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Register a new marketplace by creating a new SyftHub account.

        Args:
            request: Marketplace registration request with credentials
            tenant: Current tenant (injected)

        Returns:
            Created marketplace details
        """
        return handler.register_marketplace(request, tenant)

    @router.post("/connect", response_model=MarketplaceResponse, status_code=201)
    async def connect_marketplace(
        request: ConnectMarketplaceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Connect to an existing SyftHub account and add as marketplace.

        Args:
            request: Connection request with existing SyftHub credentials
            tenant: Current tenant (injected)

        Returns:
            Created marketplace details
        """
        return handler.connect_marketplace(request, tenant)

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

    @router.get("/balance", response_model=BalanceResponse)
    def get_balance(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> BalanceResponse:
        """Get account balance for the default marketplace.

        Validates accounting credentials before fetching balance.
        If credentials are expired, refreshes them from SyftHub.

        Args:
            tenant: Current tenant (injected)

        Returns:
            Balance information
        """
        return handler.get_balance(tenant)

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
