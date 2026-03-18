"""Generic payment API routes (provider-agnostic)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from syft_space.components.auth.dependencies import get_verified_user_email
from syft_space.components.auth.public import public_route
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.payments.handlers import PaymentHandler
from syft_space.components.payments.schemas import (
    BundleUsageResponse,
    InvoiceResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_payment_routes(
    handler: PaymentHandler,
    marketplace_repository: MarketplaceRepository,
) -> APIRouter:
    """Build generic payment routes.

    Provider-specific routes (e.g., Xendit invoice creation) live in
    their own route modules under /payments/{provider}/.
    """
    router = APIRouter(prefix="/payments", tags=["payments"])

    def get_handler() -> PaymentHandler:
        return handler

    async def get_verified_sender_email(
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
    ) -> str:
        """Extract verified user email from satellite token."""
        marketplace = await marketplace_repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(status_code=400, detail="No marketplace configured")
        return await get_verified_user_email(request, marketplace)

    @router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
    async def get_invoice(
        invoice_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Get invoice details and current status."""
        return await handler.get_invoice(invoice_id, tenant)

    @public_route
    @router.get("/bundles/{endpoint_slug}", response_model=BundleUsageResponse)
    async def get_bundle_usage(
        endpoint_slug: str,
        unit_type: str = Query(default="requests", description="Unit type to check"),
        tenant: Tenant = Depends(get_tenant_dependency),
        user_email: str = Depends(get_verified_sender_email),
        handler: PaymentHandler = Depends(get_handler),
    ) -> BundleUsageResponse:
        """Get user's bundle balance for an endpoint (PUBLIC, requires satellite token)."""
        return await handler.get_bundle_usage(
            endpoint_slug, user_email, tenant, unit_type
        )

    return router
