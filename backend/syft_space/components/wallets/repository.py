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

    async def get_by_ids(self, ids: list[UUID], tenant_id: UUID) -> list[Wallet]:
        """Get multiple wallets by IDs within a tenant (single query)."""
        if not ids:
            return []
        async with self.db.get_session() as session:
            statement = (
                select(Wallet)
                .where(Wallet.id.in_(ids), Wallet.tenant_id == tenant_id)
                .distinct()
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_type(
        self, wallet_type: str, tenant_id: UUID, is_active: bool = True
    ) -> list[Wallet]:
        """Get all wallets of a specific type for a tenant."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(
                Wallet.wallet_type == wallet_type,
                Wallet.tenant_id == tenant_id,
                Wallet.is_active == is_active,
            )
            result = await session.exec(statement)
            return list(result.all())

    async def create_wallet(
        self,
        *,
        tenant_id: UUID,
        wallet_type: str,
        name: str,
        currency: str,
        country: str | None,
        configuration: dict,
    ) -> Wallet:
        """Create a new wallet."""
        wallet = Wallet(
            tenant_id=tenant_id,
            wallet_type=wallet_type,
            name=name,
            currency=currency,
            country=country,
            configuration=configuration,
        )
        return await self.create(wallet)

    async def get_by_type_and_currency(
        self, wallet_type: str, currency: str, tenant_id: UUID
    ) -> Wallet | None:
        """Lookup the unique wallet for (tenant, type, currency)."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(
                Wallet.wallet_type == wallet_type,
                Wallet.currency == currency,
                Wallet.tenant_id == tenant_id,
            )
            result = await session.exec(statement)
            return result.first()

    async def delete_wallet(self, id: UUID, tenant_id: UUID) -> bool:
        """Delete a wallet by ID within a tenant."""
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

    async def update_configuration(
        self, id: UUID, tenant_id: UUID, configuration: dict
    ) -> Wallet | None:
        """Update a wallet's configuration."""
        async with self.db.get_session() as session:
            statement = select(Wallet).where(
                Wallet.id == id, Wallet.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            wallet = result.first()
            if not wallet:
                return None
            wallet.configuration = configuration
            wallet.updated_at = datetime.now(timezone.utc)
            session.add(wallet)
            await session.commit()
            await session.refresh(wallet)
            return wallet
