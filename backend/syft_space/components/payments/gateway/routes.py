"""Gateway payment routes — provider-agnostic invoice and bundle reads."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from syft_space.components.payments.gateway.dependencies import (
    get_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler
from syft_space.components.payments.gateway.schemas import (
    BundleUsageResponse,
    InvoiceResponse,
)
from syft_space.components.payments.gateway.xendit.routes import build_xendit_routes
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_gateway_routes(
    handler: PaymentHandler,
    get_verified_sender_email: get_verified_sender_email_dependency,
) -> APIRouter:
    """Build gateway payment routes under /gateway.

    Composes provider-agnostic reads + provider-specific sub-routers.
    """
    router = APIRouter(prefix="/gateway", tags=["payments", "gateway"])

    def get_handler() -> PaymentHandler:
        return handler

    @router.get(
        "/invoices/endpoint/{endpoint_slug}", response_model=list[InvoiceResponse]
    )
    async def get_invoices_by_endpoint(
        endpoint_slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> list[InvoiceResponse]:
        """Get all invoices for an endpoint."""
        return await handler.get_invoices_by_endpoint(endpoint_slug, tenant)

    @router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
    async def get_invoice(
        invoice_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Get invoice details and current status."""
        return await handler.get_invoice(invoice_id, tenant)

    @router.get("/bundles", response_model=list[BundleUsageResponse])
    async def get_all_bundle_usages(
        endpoint_slug: str = Query(..., description="Endpoint slug"),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> list[BundleUsageResponse]:
        """Get all bundle usages for an endpoint (admin view)."""
        return await handler.get_all_bundle_usages(endpoint_slug, tenant)

    @router.get("/bundles/{endpoint_slug}", response_model=BundleUsageResponse)
    async def get_bundle_usage(
        endpoint_slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        user_email: str = Depends(get_verified_sender_email),
        handler: PaymentHandler = Depends(get_handler),
    ) -> BundleUsageResponse:
        """Get user's bundle balance for an endpoint (PUBLIC, requires satellite token)."""
        return await handler.get_bundle_usage(endpoint_slug, user_email, tenant)

    # Provider-specific sub-routers
    router.include_router(build_xendit_routes(handler, get_verified_sender_email))

    return router
