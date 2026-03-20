"""Endpoint API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from syft_space.components.auth.dependencies import get_verified_user_email
from syft_space.components.auth.public import public_route
from syft_space.components.endpoints.handlers import EndpointHandler
from syft_space.components.endpoints.schemas import (
    AuthenticatedQueryRequest,
    CreateEndpointRequest,
    EndpointCreateResponse,
    EndpointDetailResponse,
    EndpointListItem,
    PublishEndpointRequest,
    PublishEndpointResponse,
    QueryEndpointRequest,
    QueryEndpointResponse,
    SlugAvailabilityRequest,
    SlugAvailabilityResponse,
    UnpublishResult,
    UpdateEndpointRequest,
)
from syft_space.components.policy_types.interfaces import PaymentRequiredError
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


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

    async def get_verified_sender_email(
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> str:
        """Get verified sender email from SyftHub token.

        Args:
            request: FastAPI request object
            tenant: Current tenant (injected)
            handler: Endpoint handler (injected)

        Returns:
            Verified sender email from SyftHub token

        Raises:
            HTTPException: If no marketplace configured or token invalid
        """
        marketplace = await handler.marketplace_repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(status_code=400, detail="No marketplace configured")

        return await get_verified_user_email(request, marketplace)

    @router.post("/", response_model=EndpointCreateResponse, status_code=201)
    async def create_endpoint(
        request: CreateEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointCreateResponse:
        """Create a new endpoint.

        Args:
            request: Endpoint creation request
            tenant: Current tenant (injected)

        Returns:
            Created endpoint details
        """
        return await handler.create_endpoint(request, tenant)

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
        return await handler.list_endpoints(tenant)

    @router.post("/validate-slug", response_model=SlugAvailabilityResponse)
    async def validate_slug(
        request: SlugAvailabilityRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> SlugAvailabilityResponse:
        """Validate if a slug is available locally and optionally on marketplaces.

        This endpoint allows checking slug uniqueness before creating an endpoint.
        - If neither marketplace_ids nor check_all_marketplaces is provided, only checks locally (fast)
        - If check_all_marketplaces is True, checks all active marketplaces
        - If marketplace_ids is provided, checks only those specific marketplaces

        Args:
            request: Slug and optional marketplace options
            tenant: Current tenant (injected)

        Returns:
            Availability status for local and each requested marketplace
        """
        return await handler.check_slug_availability(
            request.slug,
            request.marketplace_ids,
            request.check_all_marketplaces,
            tenant,
        )

    @router.get("/{slug}", response_model=EndpointDetailResponse)
    async def get_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointDetailResponse:
        """Get details of a specific endpoint.

        Args:
            slug: Endpoint slug
            tenant: Current tenant (injected)

        Returns:
            Endpoint details
        """
        return await handler.get_endpoint(slug, tenant)

    @router.patch("/{slug}", response_model=EndpointDetailResponse)
    async def update_endpoint(
        slug: str,
        request: UpdateEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointDetailResponse:
        """Update an endpoint's metadata.

        Allows partial updates to name, summary, and description.

        Args:
            slug: Endpoint slug
            request: Update request with fields to update
            tenant: Current tenant (injected)

        Returns:
            Updated endpoint details
        """
        return await handler.update_endpoint(slug, request, tenant)

    @public_route
    @router.post("/{slug}/query", response_model=QueryEndpointResponse)
    async def query_endpoint(
        slug: str,
        request: QueryEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        sender_email: str = Depends(get_verified_sender_email),
        handler: EndpointHandler = Depends(get_handler),
        x_payment: str | None = Header(None, alias="X-Payment"),
    ) -> QueryEndpointResponse | JSONResponse:
        """Query an endpoint - main RAG flow (PUBLIC, requires SyftHub token).

        This is the core endpoint that orchestrates:
        - Dataset search (if configured)
        - Model chat (if configured)
        - Policy enforcement (pre/post hooks)
        - MPP payment flow (X-Payment header / HTTP 402)

        Args:
            slug: Endpoint slug
            request: Query request with messages and parameters
            tenant: Current tenant (injected)
            sender_email: Verified sender email from SyftHub token (injected)
            handler: Endpoint handler (injected)
            x_payment: MPP payment credential from X-Payment header (optional)

        Returns:
            Query response with summary and/or references, or 402 if payment required
        """
        # Create authenticated request with verified sender email
        auth_request = AuthenticatedQueryRequest.from_request(request, sender_email)

        try:
            response, payment_receipt = await handler.query_endpoint(
                slug, auth_request, tenant, x_payment=x_payment
            )
        except PaymentRequiredError as e:
            return JSONResponse(
                status_code=402,
                content={"detail": e.description or "Payment required"},
                headers={"WWW-Authenticate": e.www_authenticate},
            )

        # If there's a payment receipt, include it in the response header
        if payment_receipt:
            return JSONResponse(
                status_code=200,
                content=response.model_dump(),
                headers={"Payment-Receipt": payment_receipt},
            )

        return response

    @router.post("/{slug}/publish", response_model=PublishEndpointResponse)
    async def publish_endpoint(
        slug: str,
        request: PublishEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> PublishEndpointResponse:
        """Publish an endpoint to one or more marketplaces.

        Args:
            slug: Endpoint slug
            request: Publish request with marketplace IDs or publish_to_all_marketplaces flag
            tenant: Current tenant (injected)

        Returns:
            Publish results for each marketplace
        """
        return await handler.publish_endpoint(
            slug,
            request.marketplace_ids,
            request.publish_to_all_marketplaces,
            tenant,
        )

    @router.delete("/{slug}/unpublish", response_model=list[UnpublishResult])
    async def unpublish_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> list[UnpublishResult]:
        """Unpublish an endpoint.
        Args:
            slug: Endpoint slug
            tenant: Current tenant (injected)
            handler: Endpoint handler (injected)
        Returns:
            Unpublish results for each marketplace
        Raises:
            HTTPException: If endpoint not found or marketplace not found
            HTTPException: If endpoint is not published
        """
        return await handler.unpublish_endpoint(slug, tenant)

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
        return await handler.delete_endpoint(slug, tenant)

    return router
