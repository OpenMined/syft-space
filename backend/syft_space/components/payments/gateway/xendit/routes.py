"""Xendit-specific payment and webhook routes."""

from fastapi import APIRouter, Depends, Header, Request

from syft_space.components.payments.gateway.dependencies import (
    get_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler
from syft_space.components.payments.gateway.schemas import (
    CreateInvoiceRequest,
    InvoiceResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_xendit_routes(
    handler: PaymentHandler,
    get_verified_sender_email: get_verified_sender_email_dependency,
) -> APIRouter:
    """Build all Xendit routes (payment + webhook) under /xendit."""
    router = APIRouter(prefix="/xendit", tags=["payments", "xendit"])

    def get_handler() -> PaymentHandler:
        return handler

    @router.post("/invoices", response_model=InvoiceResponse, status_code=201)
    async def create_xendit_invoice(
        request_data: CreateInvoiceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        user_email: str = Depends(get_verified_sender_email),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Create an invoice via Xendit (PUBLIC, requires satellite token)."""
        return await handler.create_invoice("xendit", request_data, tenant, user_email)

    @router.post("/webhooks")
    async def xendit_webhook(
        request: Request,
        x_callback_token: str = Header(..., alias="x-callback-token"),
    ) -> dict:
        """Xendit payment webhook (PUBLIC, no admin auth).

        Xendit sends payment status updates to this endpoint.
        Verified via x-callback-token header.
        """
        body = await request.json()
        return await handler.handle_webhook("xendit", body, x_callback_token)

    return router
