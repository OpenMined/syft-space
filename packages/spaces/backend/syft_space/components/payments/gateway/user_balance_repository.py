"""UserBalance repository — materialized money balance per (tenant, wallet, user).

Session-bound: every method runs against the session passed at construction
time. Repos do not commit; the owning PaymentLedger commits or rolls back.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from syft_space.components.payments.gateway.entities import UserBalance


class UserBalanceRepository:
    """Queries and atomic mutations for UserBalance rows.

    All writes are non-committing — the PaymentLedger that owns the session
    decides when to commit, ensuring multi-repo writes form one transaction.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_wallet(
        self,
        user_email: str,
        wallet_id: UUID,
        tenant_id: UUID,
    ) -> UserBalance | None:
        """Get a user's balance for a specific wallet."""
        statement = select(UserBalance).where(
            UserBalance.user_email == user_email,
            UserBalance.wallet_id == wallet_id,
            UserBalance.tenant_id == tenant_id,
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_wallet_id(
        self, wallet_id: UUID, tenant_id: UUID
    ) -> list[UserBalance]:
        """Get all balances for a wallet (admin view)."""
        statement = select(UserBalance).where(
            UserBalance.wallet_id == wallet_id,
            UserBalance.tenant_id == tenant_id,
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def upsert_credit(
        self,
        tenant_id: UUID,
        wallet_id: UUID,
        user_email: str,
        amount: float,
    ) -> UserBalance:
        """Add money to a user's balance for this wallet. Creates row if missing."""
        existing = await self.get_by_user_wallet(user_email, wallet_id, tenant_id)
        now = datetime.now(timezone.utc)

        if existing:
            existing.balance += amount
            existing.updated_at = now
            self.session.add(existing)
            return existing

        balance = UserBalance(
            tenant_id=tenant_id,
            wallet_id=wallet_id,
            user_email=user_email,
            balance=amount,
            created_at=now,
            updated_at=now,
        )
        self.session.add(balance)
        return balance

    async def atomic_deduct(
        self,
        user_email: str,
        wallet_id: UUID,
        tenant_id: UUID,
        amount: float,
    ) -> bool:
        """Atomically deduct from balance. Returns False if insufficient.

        Uses UPDATE ... WHERE balance >= amount for race-free check + decrement.
        """
        stmt = (
            update(UserBalance)
            .where(
                UserBalance.user_email == user_email,
                UserBalance.wallet_id == wallet_id,
                UserBalance.tenant_id == tenant_id,
                UserBalance.balance >= amount,
            )
            .values(
                balance=UserBalance.balance - amount,
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0

    async def atomic_restore(
        self,
        user_email: str,
        wallet_id: UUID,
        tenant_id: UUID,
        amount: float,
    ) -> None:
        """Atomically restore money (cancellation)."""
        stmt = (
            update(UserBalance)
            .where(
                UserBalance.user_email == user_email,
                UserBalance.wallet_id == wallet_id,
                UserBalance.tenant_id == tenant_id,
            )
            .values(
                balance=UserBalance.balance + amount,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.exec(stmt)

    async def has_nonzero_balance_by_wallet(
        self, wallet_id: UUID, tenant_id: UUID
    ) -> bool:
        """Check if any user has a positive balance for this wallet."""
        statement = select(UserBalance).where(
            UserBalance.wallet_id == wallet_id,
            UserBalance.tenant_id == tenant_id,
            UserBalance.balance > 0,
        )
        result = await self.session.exec(statement)
        return result.first() is not None
