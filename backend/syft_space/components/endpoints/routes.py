"""Endpoint API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from syft_space.components.auth.dependencies import get_verified_user_email
from syft_space.components.auth.public import public_route
from syft_space.components.endpoints.handlers import EndpointHandler
from syft_space.components.endpoints.publish_handler import PublishEndpointHandler
from syft_space.components.endpoints.query_handler import QueryEndpointHandler
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


def build_endpoint_routes(
    handler: EndpointHandler,
    query_handler: QueryEndpointHandler,
    publish_handler: PublishEndpointHandler,
) -> APIRouter:
    """Build the endpoint routes."""
    router = APIRouter(prefix="/endpoints", tags=["endpoints"])

    def get_handler() -> EndpointHandler:
        return handler

    def get_query_handler() -> QueryEndpointHandler:
        return query_handler

    def get_publish_handler() -> PublishEndpointHandler:
        return publish_handler

    async def get_verified_sender_email(
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PublishEndpointHandler = Depends(get_publish_handler),
    ) -> str:
        """Get verified sender email from SyftHub token."""
        marketplace = await handler.marketplace_repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(status_code=400, detail="No marketplace configured")
        return await get_verified_user_email(request, marketplace)

    # ── CRUD routes (EndpointHandler) ────────────────────────────

    @router.post("/", response_model=EndpointCreateResponse, status_code=201)
    async def create_endpoint(
        request: CreateEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointCreateResponse:
        return await handler.create_endpoint(request, tenant)

    @router.get("/", response_model=list[EndpointListItem])
    async def list_endpoints(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> list[EndpointListItem]:
        return await handler.list_endpoints(tenant)

    @router.get("/{slug}", response_model=EndpointDetailResponse)
    async def get_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointDetailResponse:
        return await handler.get_endpoint(slug, tenant)

    @router.patch("/{slug}", response_model=EndpointDetailResponse)
    async def update_endpoint(
        slug: str,
        request: UpdateEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointDetailResponse:
        return await handler.update_endpoint(slug, request, tenant)

    @router.post("/{slug}/archive", response_model=EndpointDetailResponse)
    async def archive_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointDetailResponse:
        return await handler.archive_endpoint(slug, tenant)

    @router.post("/{slug}/unarchive", response_model=EndpointDetailResponse)
    async def unarchive_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> EndpointDetailResponse:
        return await handler.unarchive_endpoint(slug, tenant)

    @router.delete("/{slug}", response_model=dict[str, str])
    async def delete_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: EndpointHandler = Depends(get_handler),
    ) -> dict[str, str]:
        return await handler.delete_endpoint(slug, tenant)

    # ── Query route (QueryEndpointHandler) ───────────────────────

    @public_route
    @router.post("/{slug}/query", response_model=QueryEndpointResponse)
    async def query_endpoint(
        slug: str,
        request: QueryEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        sender_email: str = Depends(get_verified_sender_email),
        handler: QueryEndpointHandler = Depends(get_query_handler),
        x_payment: str | None = Header(None, alias="X-Payment", max_length=10000),
    ) -> QueryEndpointResponse | JSONResponse:
        """Query an endpoint - main RAG flow (PUBLIC, requires SyftHub token)."""
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

        if payment_receipt:
            return JSONResponse(
                status_code=200,
                content=response.model_dump(),
                headers={"Payment-Receipt": payment_receipt},
            )

        return response

    @router.post("/{slug}/preview", response_model=QueryEndpointResponse)
    async def preview_endpoint(
        slug: str,
        request: QueryEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PublishEndpointHandler = Depends(get_publish_handler),
        qhandler: QueryEndpointHandler = Depends(get_query_handler),
    ) -> QueryEndpointResponse | JSONResponse:
        """Preview an endpoint as the space owner (admin auth, full policy pipeline).

        Identical to /query but uses admin auth so the owner can test exactly
        what external users experience — policies, filters, and all.
        """
        marketplace = await handler.marketplace_repository.get_default(tenant.id)
        sender_email = marketplace.email if marketplace else "owner@localhost.local"

        auth_request = AuthenticatedQueryRequest.from_request(request, sender_email)

        try:
            response, payment_receipt = await qhandler.query_endpoint(
                slug, auth_request, tenant, x_payment=None
            )
        except PaymentRequiredError as e:
            return JSONResponse(
                status_code=402,
                content={"detail": e.description or "Payment required"},
                headers={"WWW-Authenticate": e.www_authenticate},
            )

        if payment_receipt:
            return JSONResponse(
                status_code=200,
                content=response.model_dump(),
                headers={"Payment-Receipt": payment_receipt},
            )

        return response

    # ── Publish routes (PublishEndpointHandler) ──────────────────

    @router.post("/validate-slug", response_model=SlugAvailabilityResponse)
    async def validate_slug(
        request: SlugAvailabilityRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PublishEndpointHandler = Depends(get_publish_handler),
    ) -> SlugAvailabilityResponse:
        return await handler.check_slug_availability(
            request.slug,
            request.marketplace_ids,
            request.check_all_marketplaces,
            tenant,
        )

    @router.post("/{slug}/publish", response_model=PublishEndpointResponse)
    async def publish_endpoint(
        slug: str,
        request: PublishEndpointRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PublishEndpointHandler = Depends(get_publish_handler),
    ) -> PublishEndpointResponse:
        return await handler.publish_endpoint(
            slug, request.marketplace_ids, request.publish_to_all_marketplaces, tenant
        )

    @router.delete("/{slug}/unpublish", response_model=list[UnpublishResult])
    async def unpublish_endpoint(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PublishEndpointHandler = Depends(get_publish_handler),
    ) -> list[UnpublishResult]:
        return await handler.unpublish_endpoint(slug, tenant)

    return router
