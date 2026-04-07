"""Shared dependencies for gateway payment routes."""

from collections.abc import Callable, Coroutine

from fastapi import Depends, HTTPException, Request

from syft_space.components.auth.dependencies import get_verified_user_email
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant

# Type alias for the dependency callable used by route builders
get_verified_sender_email_dependency = Callable[..., Coroutine[None, None, str]]


def make_verified_sender_email_dependency(
    marketplace_repository: MarketplaceRepository,
) -> get_verified_sender_email_dependency:
    """Create a FastAPI dependency that extracts verified user email from satellite token."""

    async def get_verified_sender_email(
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
    ) -> str:
        marketplace = await marketplace_repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(status_code=400, detail="No marketplace configured")
        return await get_verified_user_email(request, marketplace)

    return get_verified_sender_email
