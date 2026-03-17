"""Generic payment API routes (provider-agnostic)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from syft_space.components.payments.handlers import PaymentHandler
from syft_space.components.payments.schemas import (
    BundleUsageResponse,
    InvoiceResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_payment_routes(handler: PaymentHandler) -> APIRouter:
    """Build generic payment routes.

    Provider-specific routes (e.g., Xendit invoice creation) live in
    their own route modules under /payments/{provider}/.
    """
    router = APIRouter(prefix="/payments", tags=["payments"])

    def get_handler() -> PaymentHandler:
        return handler

    @router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
    async def get_invoice(
        invoice_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Get invoice details and current status."""
        return await handler.get_invoice(invoice_id, tenant)

    @router.get("/bundles/{endpoint_slug}", response_model=BundleUsageResponse)
    async def get_bundle_usage(
        endpoint_slug: str,
        user_email: str = Query(..., description="User email to check balance for"),
        unit_type: str = Query(default="requests", description="Unit type to check"),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> BundleUsageResponse:
        """Get a user's bundle balance for an endpoint."""
        return await handler.get_bundle_usage(
            endpoint_slug, user_email, tenant, unit_type
        )

    return router
