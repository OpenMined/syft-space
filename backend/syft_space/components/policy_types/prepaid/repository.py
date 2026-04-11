"""Repository for prepaid subscription and purchase operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select, update

from syft_space.components.policy_types.prepaid.entities import (
    PrepaidPurchase,
    PrepaidSubscription,
    PurchaseStatus,
)
from syft_space.components.shared.database import AsyncDatabase


class PrepaidRepository:
    """Repository for prepaid subscription and purchase CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        self.db = db

    # ── Subscription operations ──────────────────────────────────────

    async def get_subscription(
        self, buyer_email: str, endpoint_id: UUID
    ) -> PrepaidSubscription | None:
        """Get a subscription by buyer email and endpoint ID."""
        async with self.db.get_session() as session:
            stmt = select(PrepaidSubscription).where(
                PrepaidSubscription.buyer_email == buyer_email,
                PrepaidSubscription.endpoint_id == endpoint_id,
            )
            result = await session.exec(stmt)
            return result.first()

    async def get_subscription_by_id(
        self, subscription_id: UUID
    ) -> PrepaidSubscription | None:
        async with self.db.get_session() as session:
            return await session.get(PrepaidSubscription, subscription_id)

    async def get_or_create_subscription(
        self,
        buyer_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
    ) -> PrepaidSubscription:
        """Get existing subscription or create a new one."""
        sub = await self.get_subscription(buyer_email, endpoint_id)
        if sub:
            return sub

        sub = PrepaidSubscription(
            tenant_id=tenant_id,
            endpoint_id=endpoint_id,
            buyer_email=buyer_email,
            remaining_quota=0,
            total_purchased=0,
            total_used=0,
        )
        async with self.db.get_session() as session:
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            return sub

    async def get_subscribers_by_endpoint(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> list[PrepaidSubscription]:
        """List all subscribers for a given endpoint."""
        async with self.db.get_session() as session:
            stmt = (
                select(PrepaidSubscription)
                .where(
                    PrepaidSubscription.endpoint_id == endpoint_id,
                    PrepaidSubscription.tenant_id == tenant_id,
                )
                .order_by(PrepaidSubscription.created_at.desc())
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def decrement_quota(self, subscription_id: UUID | str) -> bool:
        """Atomically decrement remaining_quota by 1 and increment total_used.

        Returns True if a row was updated, False if the subscription was
        missing or already at zero. Concurrent-safe via a single UPDATE ... WHERE.
        """
        sub_uuid = UUID(str(subscription_id))
        async with self.db.get_session() as session:
            stmt = (
                update(PrepaidSubscription)
                .where(
                    PrepaidSubscription.id == sub_uuid,
                    PrepaidSubscription.remaining_quota > 0,
                )
                .values(
                    remaining_quota=PrepaidSubscription.remaining_quota - 1,
                    total_used=PrepaidSubscription.total_used + 1,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            return getattr(result, "rowcount", 0) > 0

    async def add_quota(
        self, subscription_id: UUID, volume: int
    ) -> PrepaidSubscription:
        """Add quota to a subscription (when a purchase is activated)."""
        async with self.db.get_session() as session:
            sub = await session.get(PrepaidSubscription, subscription_id)
            if not sub:
                raise ValueError(f"Subscription {subscription_id} not found")
            sub.remaining_quota += volume
            sub.total_purchased += volume
            sub.updated_at = datetime.now(timezone.utc)
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            return sub

    # ── Purchase operations ──────────────────────────────────────────

    async def create_purchase(self, purchase: PrepaidPurchase) -> PrepaidPurchase:
        async with self.db.get_session() as session:
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)
            return purchase

    async def get_purchase_by_id(
        self, purchase_id: UUID, tenant_id: UUID | None = None
    ) -> PrepaidPurchase | None:
        async with self.db.get_session() as session:
            purchase = await session.get(PrepaidPurchase, purchase_id)
            if purchase is None:
                return None
            if tenant_id is not None and purchase.tenant_id != tenant_id:
                return None
            return purchase

    async def get_purchase_by_payment_ref(
        self, payment_reference: str
    ) -> PrepaidPurchase | None:
        async with self.db.get_session() as session:
            stmt = select(PrepaidPurchase).where(
                PrepaidPurchase.payment_reference == payment_reference
            )
            result = await session.exec(stmt)
            return result.first()

    async def get_purchases_by_endpoint(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> list[PrepaidPurchase]:
        """List all purchases for an endpoint (seller view)."""
        async with self.db.get_session() as session:
            stmt = (
                select(PrepaidPurchase)
                .where(
                    PrepaidPurchase.endpoint_id == endpoint_id,
                    PrepaidPurchase.tenant_id == tenant_id,
                )
                .order_by(PrepaidPurchase.created_at.desc())
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def get_purchases_by_buyer(
        self, buyer_email: str, endpoint_id: UUID
    ) -> list[PrepaidPurchase]:
        """List purchases for a specific buyer on an endpoint."""
        async with self.db.get_session() as session:
            stmt = (
                select(PrepaidPurchase)
                .where(
                    PrepaidPurchase.buyer_email == buyer_email,
                    PrepaidPurchase.endpoint_id == endpoint_id,
                )
                .order_by(PrepaidPurchase.created_at.desc())
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def activate_purchase(
        self, purchase_id: UUID
    ) -> PrepaidPurchase:
        """Mark a purchase as activated and add quota to subscription."""
        async with self.db.get_session() as session:
            purchase = await session.get(PrepaidPurchase, purchase_id)
            if not purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            if purchase.status == PurchaseStatus.ACTIVATED:
                raise ValueError("Purchase already activated")

            purchase.status = PurchaseStatus.ACTIVATED
            purchase.activated_at = datetime.now(timezone.utc)
            session.add(purchase)

            # Add quota to subscription
            sub = await session.get(PrepaidSubscription, purchase.subscription_id)
            if not sub:
                raise ValueError(
                    f"Subscription {purchase.subscription_id} not found"
                )
            sub.remaining_quota += purchase.volume
            sub.total_purchased += purchase.volume
            sub.updated_at = datetime.now(timezone.utc)
            session.add(sub)

            await session.commit()
            await session.refresh(purchase)
            return purchase

    async def update_purchase_status(
        self, purchase_id: UUID, status: PurchaseStatus
    ) -> PrepaidPurchase:
        async with self.db.get_session() as session:
            purchase = await session.get(PrepaidPurchase, purchase_id)
            if not purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            purchase.status = status
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)
            return purchase
