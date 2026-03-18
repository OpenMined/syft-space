"""Xendit-specific payment routes."""

from fastapi import APIRouter, Depends, HTTPException, Request

from syft_space.components.auth.dependencies import get_verified_user_email
from syft_space.components.auth.public import public_route
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.payments.handlers import PaymentHandler
from syft_space.components.payments.schemas import (
    CreateInvoiceRequest,
    InvoiceResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_xendit_payment_routes(
    handler: PaymentHandler,
    marketplace_repository: MarketplaceRepository,
) -> APIRouter:
    """Build Xendit-specific payment routes under /payments/xendit/."""
    router = APIRouter(prefix="/payments/xendit", tags=["payments", "xendit"])

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

    @public_route
    @router.post("/invoices", response_model=InvoiceResponse, status_code=201)
    async def create_xendit_invoice(
        request_data: CreateInvoiceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        user_email: str = Depends(get_verified_sender_email),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Create an invoice via Xendit (PUBLIC, requires satellite token)."""
        return await handler.create_invoice("xendit", request_data, tenant, user_email)

    return router
