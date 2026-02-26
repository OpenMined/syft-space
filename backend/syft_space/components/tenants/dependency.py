"""FastAPI dependency for tenant injection.

This dependency should be used by routes that need tenant-scoped access.
Routes that don't need tenant context (e.g., tenant management, health checks)
simply don't use this dependency in their function signature.
"""

from fastapi import HTTPException, Request
from loguru import logger

from syft_space.components.tenants.context import get_current_tenant
from syft_space.components.tenants.entities import Tenant
from syft_space.config import app_settings


def get_tenant_dependency(request: Request) -> Tenant:
    """FastAPI dependency for tenant-scoped routes.

    When multi-tenancy is enabled, this enforces that the X-Tenant-Name header
    was explicitly provided. Routes that don't use this dependency (like tenant
    management or health checks) work without the header.

    Usage:
        @router.get("/datasets/")
        async def list_datasets(tenant: Tenant = Depends(get_tenant_dependency)):
            # This route REQUIRES X-Tenant-Name header when multi-tenancy is ON
            ...

    Args:
        request: FastAPI request object

    Returns:
        Tenant object from context

    Raises:
        HTTPException: If tenant context is not set, or if tenant header
            is required but not provided
    """
    tenant = get_current_tenant()
    if tenant is None:
        logger.error(
            "Tenant context not set. Middleware may not be configured correctly."
        )
        raise HTTPException(
            status_code=500,
            detail="Tenant context not set. Middleware may not be configured correctly.",
        )

    # If multi-tenancy is enabled, enforce that a tenant header was provided
    # for tenant-scoped routes (don't use this dependency for tenant_agnostic routes)
    if app_settings.enable_multi_tenancy:
        tenant_header = request.headers.get("X-Tenant-Name")
        if not tenant_header:
            raise HTTPException(
                status_code=400,
                detail="X-Tenant-Name header is required for this endpoint when multi-tenancy is enabled",
            )

    return tenant
