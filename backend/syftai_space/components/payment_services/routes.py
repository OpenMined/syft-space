"""PaymentService API routes."""

from fastapi import APIRouter, Request

from syftai_space.components.payment_services.handlers import PaymentServiceHandler
from syftai_space.components.payment_services.schemas import (
    PaymentServiceResponse,
    UpdatePaymentServiceRequest,
)


def build_payment_service_routes(handler: PaymentServiceHandler) -> APIRouter:
    """Build payment service routes with the given handler.

    Args:
        handler: PaymentService handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/payment-service", tags=["payment-service"])

    @router.get(
        "",
        response_model=PaymentServiceResponse,
        summary="Get payment service config",
        description="Get payment service configuration for the current tenant. "
        "Auto-creates if not exists.",
    )
    async def get_payment_service(request: Request) -> PaymentServiceResponse:
        """Get payment service config."""
        return handler.get_payment_service(request.state.tenant)

    @router.patch(
        "",
        response_model=PaymentServiceResponse,
        summary="Update payment service config",
        description="Update payment service configuration for the current tenant.",
    )
    async def update_payment_service(
        request: Request, body: UpdatePaymentServiceRequest
    ) -> PaymentServiceResponse:
        """Update payment service config."""
        return handler.update_payment_service(body, request.state.tenant)

    return router
