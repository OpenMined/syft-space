"""Marketplace repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class MarketplaceRepository(AsyncBaseRepository[Marketplace]):
    """Repository for Marketplace CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        """Initialize the marketplace repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Marketplace)

    async def get_all(self, tenant_id: UUID) -> list[Marketplace]:
        """Get all marketplaces for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of marketplaces
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(Marketplace.tenant_id == tenant_id)
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Marketplace | None:
        """Get a marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            tenant_id: Tenant ID

        Returns:
            Marketplace if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id == id, Marketplace.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_url(self, url: str, tenant_id: UUID) -> Marketplace | None:
        """Get a marketplace by URL within a tenant.

        Args:
            url: Marketplace URL
            tenant_id: Tenant ID

        Returns:
            Marketplace if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.url == url, Marketplace.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()

    async def get_default(self, tenant_id: UUID) -> Marketplace | None:
        """Get the default marketplace for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Default marketplace if exists, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.tenant_id == tenant_id, Marketplace.is_default.is_(True)
            )
            result = await session.exec(statement)
            return result.first()

    async def get_active(self, tenant_id: UUID) -> list[Marketplace]:
        """Get all active marketplaces for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of active marketplaces
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.tenant_id == tenant_id, Marketplace.is_active.is_(True)
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_ids(self, ids: list[UUID], tenant_id: UUID) -> list[Marketplace]:
        """Get multiple marketplaces by IDs within a tenant.

        Args:
            ids: List of marketplace IDs
            tenant_id: Tenant ID

        Returns:
            List of found marketplaces
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id.in_(ids), Marketplace.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return list(result.all())

    async def update(
        self,
        id: UUID,
        tenant_id: UUID,
        *,
        name: str | None = None,
        url: str | None = None,
        email: str | None = None,
        password: str | None = None,
        is_active: bool | None = None,
        username: str | None = None,
    ) -> Marketplace | None:
        """Update a marketplace within a tenant.

        Args:
            id: Marketplace ID
            tenant_id: Tenant ID
            name: New marketplace name
            url: New marketplace URL
            email: Updated email
            password: Updated password
            is_active: Updated active status
            username: Updated username

        Returns:
            Updated marketplace if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id == id, Marketplace.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            marketplace = result.first()

            if not marketplace:
                return None

            # Update fields if provided
            if name is not None:
                marketplace.name = name
            if url is not None:
                marketplace.url = url
            if email is not None:
                marketplace.email = email
            if password is not None:
                marketplace.password = password
            if is_active is not None:
                marketplace.is_active = is_active
            if username is not None:
                marketplace.username = username
            marketplace.updated_at = datetime.now(timezone.utc)

            session.add(marketplace)
            await session.commit()
            await session.refresh(marketplace)
            return marketplace

    async def set_as_default(self, id: UUID, tenant_id: UUID) -> Marketplace | None:
        """Set a marketplace as the default for a tenant.

        Unsets any existing default marketplace and sets the specified one as default.

        Args:
            id: Marketplace ID to set as default
            tenant_id: Tenant ID

        Returns:
            Updated marketplace if found, None otherwise
        """
        async with self.db.get_session() as session:
            # Find the marketplace to set as default
            statement = select(Marketplace).where(
                Marketplace.id == id, Marketplace.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            marketplace = result.first()

            if not marketplace:
                return None

            # Unset any existing defaults for this tenant
            unset_statement = select(Marketplace).where(
                Marketplace.tenant_id == tenant_id,
                Marketplace.is_default.is_(True),
                Marketplace.id != id,
            )
            unset_result = await session.exec(unset_statement)
            for other in unset_result.all():
                other.is_default = False
                session.add(other)

            # Set this marketplace as default
            marketplace.is_default = True
            marketplace.updated_at = datetime.now(timezone.utc)
            session.add(marketplace)
            await session.commit()
            await session.refresh(marketplace)
            return marketplace

    async def delete(self, id: UUID, tenant_id: UUID) -> bool:
        """Delete a marketplace within a tenant.

        Args:
            id: Marketplace ID
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        async with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id == id, Marketplace.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            marketplace = result.first()
            if marketplace:
                await session.delete(marketplace)
                await session.commit()
                return True
            return False
