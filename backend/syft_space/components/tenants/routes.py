"""Tenant API routes."""

from fastapi import APIRouter

from syft_space.components.tenants.handlers import TenantHandler
from syft_space.components.tenants.schemas import (
    CreateTenantRequest,
    TenantListItem,
    TenantResponse,
)


def build_tenant_routes(handler: TenantHandler) -> APIRouter:
    """Build tenant routes with dependency-injected handler.

    Args:
        handler: Tenant handler instance

    Returns:
        Configured router
    """
    router = APIRouter(prefix="/tenants", tags=["tenants"])

    @router.post("", response_model=TenantResponse, status_code=201)
    async def create_tenant(request: CreateTenantRequest) -> TenantResponse:
        """Create a new tenant.

        Only available when multi-tenancy is enabled.
        """
        return await handler.create_tenant(request)

    @router.get("", response_model=list[TenantListItem])
    async def list_tenants() -> list[TenantListItem]:
        """List all tenants."""
        return await handler.list_tenants()

    @router.get("/{name}", response_model=TenantResponse)
    async def get_tenant(name: str) -> TenantResponse:
        """Get tenant details by name."""
        return await handler.get_tenant(name)

    return router
