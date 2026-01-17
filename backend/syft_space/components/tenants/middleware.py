"""Tenant resolution middleware.

This middleware extracts tenant information from the request (header or subdomain),
validates it, and stores it in context for the duration of the request.

The middleware ALWAYS sets a tenant in context (either from X-Tenant-Name header or root tenant).
Route-specific header validation happens in get_tenant_dependency() for routes that need it.
"""

from collections.abc import Callable

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from syft_space.components.tenants.context import (
    clear_current_tenant,
    set_current_tenant,
)
from syft_space.components.tenants.entities import Tenant
from syft_space.components.tenants.repository import TenantRepository
from syft_space.config import app_settings


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware for resolving tenant from request.

    This middleware ALWAYS sets a tenant in context (from header or root).
    Routes that need to enforce tenant header use get_tenant_dependency().
    Routes that don't need tenant context simply don't use the dependency.
    """

    def __init__(self, app, tenant_repository: TenantRepository):
        """Initialize tenant middleware.

        Args:
            app: FastAPI application
            tenant_repository: Repository for tenant lookups
        """
        super().__init__(app)
        self.tenant_repository = tenant_repository

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and inject tenant into context.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from downstream handlers
        """
        try:
            # Resolve tenant from request or use default
            if app_settings.enable_multi_tenancy:
                tenant_name = request.headers.get("X-Tenant-Name")
                if tenant_name:
                    # Tenant header provided - must be valid
                    tenant = await self.tenant_repository.get_by_name(tenant_name)
                    if tenant is None:
                        return Response(
                            status_code=404,
                            content=f'{{"detail":"Tenant \'{tenant_name}\' not found"}}',
                            media_type="application/json",
                        )
                else:
                    # No header provided - use root tenant
                    # Route-specific validation will happen in dependency
                    tenant = await self._get_default_tenant()
            else:
                # Multi-tenancy disabled - always use root tenant
                tenant = await self._get_default_tenant()

            # Validate tenant exists
            if tenant is None:
                return Response(
                    status_code=500,
                    content='{"detail":"Default tenant not found. Database may not be initialized."}',
                    media_type="application/json",
                )

            # Check if tenant is active
            if not tenant.is_active:
                return Response(
                    status_code=403,
                    content=f'{{"detail":"Tenant \'{tenant.name}\' is not active"}}',
                    media_type="application/json",
                )

            # Set tenant in context for this request
            set_current_tenant(tenant)

            # Process request
            response = await call_next(request)

            return response
        except Exception as e:
            logger.exception(
                f"Unhandled error on {request.method} {request.url.path}: {e}"
            )
            raise
        finally:
            # Clean up context
            clear_current_tenant()

    async def _get_default_tenant(self) -> Tenant | None:
        """Get the default tenant (used when multi-tenancy is disabled).

        Returns:
            Default tenant object
        """
        return await self.tenant_repository.get_by_name(
            app_settings.default_tenant_name
        )

    def _extract_subdomain(self, host: str) -> str:
        """Extract subdomain from host header.

        Args:
            host: Host header value (e.g., "acme.example.com:8080")

        Returns:
            Subdomain if present, empty string otherwise
        """
        # Remove port if present
        host = host.split(":")[0]

        # Split by dots
        parts = host.split(".")

        # If there are more than 2 parts, first part is subdomain
        # e.g., "acme.example.com" -> "acme"
        if len(parts) > 2:
            return parts[0]

        return ""
