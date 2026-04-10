"""Prepaid policy API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from syft_space.components.policy_types.prepaid.handlers import PrepaidHandler
from syft_space.components.policy_types.prepaid.schemas import (
    PrepaidEndpointStats,
    PrepaidPurchaseResponse,
    PrepaidQuotaResponse,
    PrepaidSubscriberDetail,
    PrepaidSubscriptionResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


class CreateManualPurchaseRequest(BaseModel):
    """Request to create a manual purchase (admin action)."""

    buyer_email: EmailStr = Field(..., description="Buyer's email address")
    volume: int = Field(..., gt=0, description="Number of units to grant")
    price: float = Field(default=0.0, ge=0, description="Price (for record-keeping)")
    currency: str = Field(default="USD", description="Currency")
    unit: str = Field(default="request", description="Unit type")
    auto_activate: bool = Field(
        default=True, description="Automatically activate the purchase"
    )


class ActivatePurchaseRequest(BaseModel):
    """Request to activate a pending purchase."""

    purchase_id: UUID = Field(..., description="Purchase ID to activate")


def build_prepaid_routes(handler: PrepaidHandler) -> APIRouter:
    """Build prepaid policy routes."""
    router = APIRouter(prefix="/prepaid", tags=["prepaid"])

    def get_handler() -> PrepaidHandler:
        return handler

    @router.get(
        "/endpoints/{endpoint_id}/subscribers",
        response_model=list[PrepaidSubscriptionResponse],
    )
    async def list_subscribers(
        endpoint_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PrepaidHandler = Depends(get_handler),
    ) -> list[PrepaidSubscriptionResponse]:
        """List all subscribers for an endpoint (seller admin view)."""
        return await handler.get_endpoint_subscribers(endpoint_id, tenant)

    @router.get(
        "/endpoints/{endpoint_id}/stats",
        response_model=PrepaidEndpointStats,
    )
    async def get_endpoint_stats(
        endpoint_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PrepaidHandler = Depends(get_handler),
    ) -> PrepaidEndpointStats:
        """Get aggregated prepaid stats for an endpoint."""
        return await handler.get_endpoint_stats(endpoint_id, tenant)

    @router.get(
        "/endpoints/{endpoint_id}/subscribers/{buyer_email}",
        response_model=PrepaidSubscriberDetail,
    )
    async def get_subscriber_detail(
        endpoint_id: UUID,
        buyer_email: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PrepaidHandler = Depends(get_handler),
    ) -> PrepaidSubscriberDetail:
        """Get detailed info for a specific subscriber."""
        return await handler.get_subscriber_detail(
            endpoint_id, buyer_email, tenant
        )

    @router.get(
        "/endpoints/{endpoint_id}/purchases",
        response_model=list[PrepaidPurchaseResponse],
    )
    async def list_purchases(
        endpoint_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PrepaidHandler = Depends(get_handler),
    ) -> list[PrepaidPurchaseResponse]:
        """List all purchases for an endpoint."""
        return await handler.get_endpoint_purchases(endpoint_id, tenant)

    @router.post(
        "/endpoints/{endpoint_id}/purchases",
        response_model=PrepaidPurchaseResponse,
        status_code=201,
    )
    async def create_manual_purchase(
        endpoint_id: UUID,
        request: CreateManualPurchaseRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PrepaidHandler = Depends(get_handler),
    ) -> PrepaidPurchaseResponse:
        """Create a manual purchase (admin action)."""
        return await handler.create_manual_purchase(
            endpoint_id=endpoint_id,
            buyer_email=request.buyer_email,
            volume=request.volume,
            price=request.price,
            currency=request.currency,
            unit=request.unit,
            tenant=tenant,
            auto_activate=request.auto_activate,
        )

    @router.post(
        "/purchases/{purchase_id}/activate",
        response_model=PrepaidPurchaseResponse,
    )
    async def activate_purchase(
        purchase_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PrepaidHandler = Depends(get_handler),
    ) -> PrepaidPurchaseResponse:
        """Activate a pending purchase (admin action)."""
        return await handler.activate_purchase(purchase_id, tenant)

    @router.get(
        "/endpoints/{endpoint_id}/quota",
        response_model=PrepaidQuotaResponse,
    )
    async def get_buyer_quota(
        endpoint_id: UUID,
        buyer_email: str,
        handler: PrepaidHandler = Depends(get_handler),
    ) -> PrepaidQuotaResponse:
        """Check remaining quota for a buyer on an endpoint."""
        return await handler.get_buyer_quota(endpoint_id, buyer_email)

    return router
