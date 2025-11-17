"""FastAPI dependency for tenant injection.

This module bridges between the middleware (which sets tenant in context)
and the route handlers (which need tenant as a parameter).
"""

from fastapi import HTTPException

from .context import get_current_tenant
from .entities import Tenant


def get_tenant_dependency() -> Tenant:
    """FastAPI dependency that extracts tenant from context.

    This is the ONLY place that should call get_current_tenant().
    Acts as bridge between middleware and dependency injection.

    Returns:
        Tenant object from context

    Raises:
        HTTPException: If tenant context is not set (middleware error)
    """
    tenant = get_current_tenant()
    if tenant is None:
        raise HTTPException(
            status_code=500,
            detail="Tenant context not set. Middleware may not be configured correctly.",
        )
    return tenant
