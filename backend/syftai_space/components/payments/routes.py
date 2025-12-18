"""PaymentService API routes."""

from fastapi import APIRouter, Depends, Request

from syftai_space.components.payments.handlers import PaymentServiceHandler
from syftai_space.components.payments.schemas import (
    PaymentServiceResponse,
    UpdatePaymentServiceRequest,
)
from syftai_space.components.tenants.dependency import get_tenant_dependency
from syftai_space.components.tenants.entities import Tenant


def build_payment_service_routes(handler: PaymentServiceHandler) -> APIRouter:
    """Build payment service routes with the given handler.

    Args:
        handler: PaymentService handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/payments", tags=["payments"])

    @router.get(
        "",
        response_model=PaymentServiceResponse,
        summary="Get payment service config",
        description="Get payment service configuration for the current tenant. "
        "Auto-creates if not exists.",
    )
    async def get_payment_service(
        request: Request, tenant: Tenant = Depends(get_tenant_dependency)
    ) -> PaymentServiceResponse:
        """Get payment service config."""
        return handler.get_payment_service(tenant)

    @router.patch(
        "",
        response_model=PaymentServiceResponse,
        summary="Update payment service config",
        description="Update payment service configuration for the current tenant.",
    )
    async def update_payment_service(
        request: Request,
        body: UpdatePaymentServiceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
    ) -> PaymentServiceResponse:
        """Update payment service config."""
        return handler.update_payment_service(body, tenant)

    return router
