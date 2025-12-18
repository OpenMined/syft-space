"""PaymentService handlers for business logic."""

from fastapi import HTTPException

from syftai_space.components.payment_services.repository import PaymentServiceRepository
from syftai_space.components.payment_services.schemas import (
    PaymentServiceResponse,
    UpdatePaymentServiceRequest,
)
from syftai_space.components.tenants.entities import Tenant


class PaymentServiceHandler:
    """Handler for payment service business logic."""

    def __init__(self, repository: PaymentServiceRepository):
        """Initialize the payment service handler.

        Args:
            repository: PaymentService repository
        """
        self.repository = repository

    def get_payment_service(self, tenant: Tenant) -> PaymentServiceResponse:
        """Get payment service config for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            Payment service config

        Raises:
            HTTPException: If payment service not found for tenant
        """
        payment_service = self.repository.get_by_tenant(tenant.id)
        if not payment_service:
            raise HTTPException(
                status_code=404,
                detail="Payment service not configured for this tenant",
            )
        return PaymentServiceResponse.model_validate(payment_service)

    def update_payment_service(
        self, request: UpdatePaymentServiceRequest, tenant: Tenant
    ) -> PaymentServiceResponse:
        """Update payment service config for a tenant.

        Args:
            request: Update request with fields to update
            tenant: Tenant context

        Returns:
            Updated payment service config

        Raises:
            HTTPException: If payment service not found for tenant
        """
        url_str = str(request.url) if request.url else None

        updated = self.repository.update(
            tenant.id,
            url=url_str,
            email=request.email,
            password=request.password,
        )

        if not updated:
            raise HTTPException(
                status_code=404,
                detail="Payment service not configured for this tenant",
            )

        return PaymentServiceResponse.model_validate(updated)
