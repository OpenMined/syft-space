"""Endpoint API routes."""

from fastapi import APIRouter, Depends

from syftai_space.components.auth.public import public_route
from syftai_space.components.endpoints.handlers import EndpointHandler
from syftai_space.components.endpoints.schemas import (
    CreateEndpointRequest,
    EndpointListItem,
    EndpointResponse,
    QueryEndpointRequest,
    QueryEndpointResponse,
)
from syftai_space.components.tenants.dependency import get_tenant_dependency
from syftai_space.components.tenants.entities import Tenant


def build_endpoint_routes(handler: EndpointHandler) -> APIRouter:
    """Build the endpoint routes.

    Args:
        handler: Endpoint handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/endpoints", tags=["endpoints"])

    def get_handler() -> EndpointHandler:
        """Dependency to get the endpoint handler."""
        return handler

    @router.post("/", response_model=EndpointResponse, status_code=201)
    async def create_endpoint(
        request: CreateEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointResponse:
        """Create a new endpoint.

        Args:
            request: Endpoint creation request
            tenant: Current tenant (injected)

        Returns:
            Created endpoint details
        """
        return handler.create_endpoint(request, tenant)

    @router.get("/", response_model=list[EndpointListItem])
    async def list_endpoints(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> list[EndpointListItem]:
        """List all endpoints.

        Args:
            tenant: Current tenant (injected)

        Returns:
            List of endpoints with summary information
        """
        return handler.list_endpoints(tenant)

    @router.get("/{slug}", response_model=EndpointResponse)
    async def get_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointResponse:
        """Get details of a specific endpoint.

        Args:
            slug: Endpoint slug
            tenant: Current tenant (injected)

        Returns:
            Endpoint details
        """
        return handler.get_endpoint(slug, tenant)

    @public_route
    @router.post("/{slug}/query", response_model=QueryEndpointResponse)
    async def query_endpoint(
        slug: str,
        request: QueryEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> QueryEndpointResponse:
        """Query an endpoint - main RAG flow (PUBLIC, no auth required).

        This is the core endpoint that orchestrates:
        - Dataset search (if configured)
        - Model chat (if configured)
        - Policy enforcement (pre/post hooks)

        Args:
            slug: Endpoint slug
            request: Query request with messages and parameters
            tenant: Current tenant (injected)

        Returns:
            Query response with summary and/or references
        """
        return handler.query_endpoint(slug, request, tenant)

    @router.delete("/{slug}", response_model=dict[str, str])
    async def delete_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete an endpoint.

        Args:
            slug: Endpoint slug
            tenant: Current tenant (injected)

        Returns:
            Success message
        """
        return handler.delete_endpoint(slug, tenant)

    return router
