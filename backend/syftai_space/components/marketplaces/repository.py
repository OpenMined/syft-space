"""Marketplace repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select

from syftai_space.components.marketplaces.entities import Marketplace
from syftai_space.components.shared.database import BaseRepository, Database


class MarketplaceRepository(BaseRepository[Marketplace]):
    """Repository for Marketplace CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the marketplace repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Marketplace)

    def get_all(self, tenant_id: UUID) -> list[Marketplace]:
        """Get all marketplaces for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of marketplaces
        """
        with self.db.get_session() as session:
            statement = select(Marketplace).where(Marketplace.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_by_id(self, id: UUID, tenant_id: UUID) -> Marketplace | None:
        """Get a marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            tenant_id: Tenant ID

        Returns:
            Marketplace if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id == id, Marketplace.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def get_default(self, tenant_id: UUID) -> Marketplace | None:
        """Get the default marketplace for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Default marketplace if exists, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.tenant_id == tenant_id, Marketplace.is_default.is_(True)
            )
            return session.exec(statement).first()

    def get_active(self, tenant_id: UUID) -> list[Marketplace]:
        """Get all active marketplaces for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of active marketplaces
        """
        with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.tenant_id == tenant_id, Marketplace.is_active.is_(True)
            )
            return list(session.exec(statement).all())

    def get_by_ids(self, ids: list[UUID], tenant_id: UUID) -> list[Marketplace]:
        """Get multiple marketplaces by IDs within a tenant.

        Args:
            ids: List of marketplace IDs
            tenant_id: Tenant ID

        Returns:
            List of found marketplaces
        """
        with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id.in_(ids), Marketplace.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())

    def update(
        self,
        id: UUID,
        tenant_id: UUID,
        *,
        name: str | None = None,
        url: str | None = None,
        email: str | None = None,
        password: str | None = None,
        is_active: bool | None = None,
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

        Returns:
            Updated marketplace if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id == id, Marketplace.tenant_id == tenant_id
            )
            marketplace = session.exec(statement).first()

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

            marketplace.updated_at = datetime.now(timezone.utc)

            session.add(marketplace)
            session.commit()
            session.refresh(marketplace)
            return marketplace

    def delete(self, id: UUID, tenant_id: UUID) -> bool:
        """Delete a marketplace within a tenant.

        Args:
            id: Marketplace ID
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            statement = select(Marketplace).where(
                Marketplace.id == id, Marketplace.tenant_id == tenant_id
            )
            marketplace = session.exec(statement).first()
            if marketplace:
                session.delete(marketplace)
                session.commit()
                return True
            return False
