"""Tenant resolution middleware.

This middleware extracts tenant information from the request (header or subdomain),
validates it, and stores it in context for the duration of the request.
"""

from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from config import app_settings

from .context import clear_current_tenant, set_current_tenant
from .repository import TenantRepository


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware for resolving and validating tenant from request."""

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
            # Determine tenant based on multi-tenancy setting
            if app_settings.enable_multi_tenancy:
                tenant = await self._resolve_tenant_from_request(request)
            else:
                # Multi-tenancy disabled - use root tenant
                tenant = await self._get_default_tenant()

            if tenant is None:
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": "Default tenant not found. Database may not be initialized."
                    },
                )

            # Check if tenant is active
            if not tenant.is_active:
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Tenant '{tenant.name}' is not active"},
                )

            # Set tenant in context for this request
            set_current_tenant(tenant)
            logger.debug(f"Request processing with tenant: {tenant.name}")

            # Process request
            response = await call_next(request)

            return response

        except Exception as e:
            logger.error(f"Tenant middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Tenant resolution failed: {str(e)}"},
            )
        finally:
            # Clean up context
            clear_current_tenant()

    async def _resolve_tenant_from_request(self, request: Request):
        """Resolve tenant from request headers or subdomain.

        Args:
            request: Incoming request

        Returns:
            Tenant object if found, None otherwise
        """
        # Method 1: Check X-Tenant-Name header (primary method)
        tenant_name = request.headers.get("X-Tenant-Name")
        if tenant_name:
            tenant = self.tenant_repository.get_by_name(tenant_name)
            if tenant:
                return tenant
            else:
                # Tenant specified but not found
                return None

        # Method 2: Extract from subdomain (future enhancement)
        # host = request.headers.get("Host", "")
        # subdomain = self._extract_subdomain(host)
        # if subdomain:
        #     tenant = self.tenant_repository.get_by_domain(subdomain)
        #     if tenant:
        #         return tenant

        # No tenant specified when multi-tenancy is enabled
        return None

    async def _get_default_tenant(self):
        """Get the default tenant (used when multi-tenancy is disabled).

        Returns:
            Default tenant object
        """
        return self.tenant_repository.get_by_name(app_settings.default_tenant_name)

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
