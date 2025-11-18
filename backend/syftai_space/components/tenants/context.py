"""Tenant context management using contextvars.

This module provides a transport mechanism for tenant information between
middleware and FastAPI dependency injection. It should NOT be used directly
by handlers or repositories - tenant information should be passed explicitly
through function parameters.
"""

from contextvars import ContextVar
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from syftai_space.components.tenants.entities import Tenant

# Context-local variable - each request gets its own isolated copy
_tenant_context: ContextVar[Optional["Tenant"]] = ContextVar(
    "tenant_context", default=None
)


def set_current_tenant(tenant: "Tenant") -> None:
    """Set the current tenant in context.

    This should ONLY be called by middleware.

    Args:
        tenant: Tenant object to store in context
    """
    _tenant_context.set(tenant)


def get_current_tenant() -> Optional["Tenant"]:
    """Get the current tenant from context.

    This should ONLY be called by the FastAPI dependency function.

    Returns:
        Tenant if set, None otherwise
    """
    return _tenant_context.get()


def clear_current_tenant() -> None:
    """Clear the current tenant from context.

    Useful for cleanup in middleware.
    """
    _tenant_context.set(None)
