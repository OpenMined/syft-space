"""Bundle usage repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlmodel import select

from syft_space.components.payments.gateway.entities import BundleUsage
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class BundleUsageRepository(AsyncBaseRepository[BundleUsage]):
    """Repository for BundleUsage CRUD and atomic operations."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, BundleUsage)

    async def get_by_user_endpoint(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
    ) -> BundleUsage | None:
        """Get bundle usage for a specific user and endpoint."""
        async with self.db.get_session() as session:
            statement = select(BundleUsage).where(
                BundleUsage.user_email == user_email,
                BundleUsage.endpoint_id == endpoint_id,
                BundleUsage.tenant_id == tenant_id,
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_endpoint_id(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> list[BundleUsage]:
        """Get all bundle usages for an endpoint."""
        async with self.db.get_session() as session:
            statement = select(BundleUsage).where(
                BundleUsage.endpoint_id == endpoint_id,
                BundleUsage.tenant_id == tenant_id,
            )
            result = await session.exec(statement)
            return list(result.all())

    async def upsert_add_balance(
        self,
        tenant_id: UUID,
        endpoint_id: UUID,
        user_email: str,
        amount: float,
    ) -> BundleUsage:
        """Add money to a user's balance. Creates row if it doesn't exist."""
        async with self.db.get_session() as session:
            existing = await self.get_by_user_endpoint(
                user_email, endpoint_id, tenant_id
            )
            now = datetime.now(timezone.utc)

            if existing:
                existing.remaining_balance += amount
                existing.total_deposited += amount
                existing.updated_at = now
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                usage = BundleUsage(
                    tenant_id=tenant_id,
                    endpoint_id=endpoint_id,
                    user_email=user_email,
                    remaining_balance=amount,
                    total_deposited=amount,
                    created_at=now,
                    updated_at=now,
                )
                session.add(usage)
                await session.commit()
                await session.refresh(usage)
                return usage

    async def atomic_deduct(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        amount: float,
    ) -> bool:
        """Atomically deduct money. Returns False if insufficient balance.

        Uses UPDATE ... WHERE remaining_balance >= amount for atomicity.
        """
        async with self.db.get_session() as session:
            stmt = (
                update(BundleUsage)
                .where(
                    BundleUsage.user_email == user_email,
                    BundleUsage.endpoint_id == endpoint_id,
                    BundleUsage.tenant_id == tenant_id,
                    BundleUsage.remaining_balance >= amount,
                )
                .values(
                    remaining_balance=BundleUsage.remaining_balance - amount,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            result = await session.exec(stmt)
            await session.commit()
            return result.rowcount > 0

    async def atomic_restore(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        amount: float,
    ) -> None:
        """Atomically restore money (settle refund or cancel rollback)."""
        async with self.db.get_session() as session:
            stmt = (
                update(BundleUsage)
                .where(
                    BundleUsage.user_email == user_email,
                    BundleUsage.endpoint_id == endpoint_id,
                    BundleUsage.tenant_id == tenant_id,
                )
                .values(
                    remaining_balance=BundleUsage.remaining_balance + amount,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.exec(stmt)
            await session.commit()

    async def has_nonzero_balance_by_endpoint_id(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> bool:
        """Check if any users have remaining balance for an endpoint."""
        async with self.db.get_session() as session:
            statement = select(BundleUsage).where(
                BundleUsage.endpoint_id == endpoint_id,
                BundleUsage.tenant_id == tenant_id,
                BundleUsage.remaining_balance > 0,
            )
            result = await session.exec(statement)
            return result.first() is not None
