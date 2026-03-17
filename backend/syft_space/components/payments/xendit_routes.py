"""Xendit-specific payment routes."""

from fastapi import APIRouter, Depends

from syft_space.components.payments.handlers import PaymentHandler
from syft_space.components.payments.schemas import (
    CreateInvoiceRequest,
    InvoiceResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_xendit_payment_routes(handler: PaymentHandler) -> APIRouter:
    """Build Xendit-specific payment routes under /payments/xendit/."""
    router = APIRouter(prefix="/payments/xendit", tags=["payments", "xendit"])

    def get_handler() -> PaymentHandler:
        return handler

    @router.post("/invoices", response_model=InvoiceResponse, status_code=201)
    async def create_xendit_invoice(
        request_data: CreateInvoiceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Create an invoice via Xendit to purchase a bundle tier."""
        return await handler.create_invoice("xendit", request_data, tenant)

    return router
