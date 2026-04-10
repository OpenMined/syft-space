"""Prepaid policy handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException

from syft_space.components.policies.repository import PolicyRepository
from syft_space.components.policy_types.prepaid.entities import (
    PrepaidPurchase,
    PurchaseStatus,
)
from syft_space.components.policy_types.prepaid.repository import PrepaidRepository
from syft_space.components.policy_types.prepaid.schemas import (
    PrepaidEndpointStats,
    PrepaidPurchaseResponse,
    PrepaidQuotaResponse,
    PrepaidSubscriberDetail,
    PrepaidSubscriptionResponse,
)
from syft_space.components.tenants.entities import Tenant


class PrepaidHandler:
    """Handler for prepaid subscription business logic."""

    def __init__(
        self,
        prepaid_repository: PrepaidRepository,
        policy_repository: PolicyRepository,
    ):
        self.prepaid_repo = prepaid_repository
        self.policy_repo = policy_repository

    async def get_endpoint_subscribers(
        self, endpoint_id: UUID, tenant: Tenant
    ) -> list[PrepaidSubscriptionResponse]:
        """List all subscribers for an endpoint (seller admin view)."""
        subs = await self.prepaid_repo.get_subscribers_by_endpoint(
            endpoint_id, tenant.id
        )
        return [PrepaidSubscriptionResponse.model_validate(s) for s in subs]

    async def get_endpoint_stats(
        self, endpoint_id: UUID, tenant: Tenant
    ) -> PrepaidEndpointStats:
        """Get aggregated prepaid stats for an endpoint."""
        subs = await self.prepaid_repo.get_subscribers_by_endpoint(
            endpoint_id, tenant.id
        )
        purchases = await self.prepaid_repo.get_purchases_by_endpoint(
            endpoint_id, tenant.id
        )

        total_revenue = sum(
            p.price
            for p in purchases
            if p.status == PurchaseStatus.ACTIVATED
        )
        currency = purchases[0].currency if purchases else "USD"

        return PrepaidEndpointStats(
            endpoint_id=endpoint_id,
            total_subscribers=len(subs),
            total_active_quota=sum(s.remaining_quota for s in subs),
            total_purchased=sum(s.total_purchased for s in subs),
            total_used=sum(s.total_used for s in subs),
            total_revenue=total_revenue,
            currency=currency,
            subscribers=[
                PrepaidSubscriptionResponse.model_validate(s) for s in subs
            ],
        )

    async def get_subscriber_detail(
        self, endpoint_id: UUID, buyer_email: str, tenant: Tenant
    ) -> PrepaidSubscriberDetail:
        """Get detailed subscriber info with purchase history."""
        sub = await self.prepaid_repo.get_subscription(buyer_email, endpoint_id)
        if not sub:
            raise HTTPException(
                status_code=404,
                detail=f"No subscription found for {buyer_email}",
            )

        purchases = await self.prepaid_repo.get_purchases_by_buyer(
            buyer_email, endpoint_id
        )

        return PrepaidSubscriberDetail(
            subscription=PrepaidSubscriptionResponse.model_validate(sub),
            purchases=[
                PrepaidPurchaseResponse.model_validate(p) for p in purchases
            ],
        )

    async def get_endpoint_purchases(
        self, endpoint_id: UUID, tenant: Tenant
    ) -> list[PrepaidPurchaseResponse]:
        """List all purchases for an endpoint."""
        purchases = await self.prepaid_repo.get_purchases_by_endpoint(
            endpoint_id, tenant.id
        )
        return [PrepaidPurchaseResponse.model_validate(p) for p in purchases]

    async def activate_purchase(
        self, purchase_id: UUID, tenant: Tenant
    ) -> PrepaidPurchaseResponse:
        """Manually activate a purchase (admin action)."""
        purchase = await self.prepaid_repo.get_purchase_by_id(purchase_id)
        if not purchase:
            raise HTTPException(
                status_code=404, detail="Purchase not found"
            )
        if purchase.tenant_id != tenant.id:
            raise HTTPException(
                status_code=404, detail="Purchase not found"
            )
        if purchase.status == PurchaseStatus.ACTIVATED:
            raise HTTPException(
                status_code=400, detail="Purchase already activated"
            )

        activated = await self.prepaid_repo.activate_purchase(purchase_id)
        return PrepaidPurchaseResponse.model_validate(activated)

    async def get_buyer_quota(
        self, endpoint_id: UUID, buyer_email: str
    ) -> PrepaidQuotaResponse:
        """Get buyer's remaining quota for an endpoint."""
        sub = await self.prepaid_repo.get_subscription(buyer_email, endpoint_id)
        if not sub:
            return PrepaidQuotaResponse(
                endpoint_id=endpoint_id,
                remaining_quota=0,
                total_purchased=0,
                total_used=0,
                is_active=False,
            )

        return PrepaidQuotaResponse(
            endpoint_id=endpoint_id,
            remaining_quota=sub.remaining_quota,
            total_purchased=sub.total_purchased,
            total_used=sub.total_used,
            is_active=sub.is_active,
        )

    async def create_manual_purchase(
        self,
        endpoint_id: UUID,
        buyer_email: str,
        volume: int,
        price: float,
        currency: str,
        unit: str,
        tenant: Tenant,
        auto_activate: bool = True,
    ) -> PrepaidPurchaseResponse:
        """Create a manual purchase and optionally auto-activate it.

        Used for admin-initiated bundle grants or testing.
        """
        sub = await self.prepaid_repo.get_or_create_subscription(
            buyer_email=buyer_email,
            endpoint_id=endpoint_id,
            tenant_id=tenant.id,
        )

        purchase = PrepaidPurchase(
            tenant_id=tenant.id,
            subscription_id=sub.id,
            endpoint_id=endpoint_id,
            buyer_email=buyer_email,
            volume=volume,
            price=price,
            currency=currency,
            unit=unit,
            status=PurchaseStatus.PENDING,
            payment_provider="manual",
        )

        created = await self.prepaid_repo.create_purchase(purchase)

        if auto_activate:
            created = await self.prepaid_repo.activate_purchase(created.id)

        return PrepaidPurchaseResponse.model_validate(created)
