"""Wallet repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select

from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase
from syft_space.components.wallets.entities import Wallet


class WalletRepository(AsyncBaseRepository[Wallet]):
    """Repository for Wallet CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Wallet)

    async def get_all(self, tenant_id: UUID) -> list[Wallet]:
        """Get all wallets for a tenant."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(Wallet.tenant_id == tenant_id)
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Wallet | None:
        """Get a wallet by ID within a tenant."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(
                Wallet.id == id, Wallet.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_type(self, wallet_type: str, tenant_id: UUID) -> Wallet | None:
        """Get a wallet by type within a tenant (unique per tenant)."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(
                Wallet.wallet_type == wallet_type, Wallet.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()

    async def delete(self, id: UUID, tenant_id: UUID) -> bool:
        """Delete a wallet within a tenant."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(
                Wallet.id == id, Wallet.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            wallet = result.first()
            if wallet:
                await session.delete(wallet)
                await session.commit()
                return True
            return False

    async def update_credentials(
        self,
        id: UUID,
        tenant_id: UUID,
        credentials: dict,
    ) -> Wallet | None:
        """Update wallet credentials."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(
                Wallet.id == id, Wallet.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            wallet = result.first()
            if not wallet:
                return None
            wallet.credentials = credentials
            wallet.updated_at = datetime.now(timezone.utc)
            session.add(wallet)
            await session.commit()
            await session.refresh(wallet)
            return wallet
