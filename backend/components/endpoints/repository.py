"""Endpoint repository for database operations."""

from typing import Optional
from uuid import UUID

from sqlmodel import select

from components.shared.database import BaseRepository, Database

from .entities import Endpoint


class EndpointRepository(BaseRepository[Endpoint]):
    """Repository for Endpoint CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the endpoint repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Endpoint)

    def get_all(self, tenant_id: UUID) -> list[Endpoint]:
        """Get all endpoints for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of endpoints
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(Endpoint.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_by_id(self, id: int, tenant_id: UUID) -> Optional[Endpoint]:
        """Get an endpoint by ID within a tenant.

        Args:
            id: Endpoint ID
            tenant_id: Tenant ID

        Returns:
            Endpoint if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.id == id, Endpoint.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def get_by_slug(self, slug: str, tenant_id: UUID) -> Optional[Endpoint]:
        """Get an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant_id: Tenant ID

        Returns:
            Endpoint if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.slug == slug, Endpoint.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def delete_by_slug(self, slug: str, tenant_id: UUID) -> bool:
        """Delete an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.slug == slug, Endpoint.tenant_id == tenant_id
            )
            obj = session.exec(statement).first()
            if obj:
                session.delete(obj)
                session.commit()
                return True
            return False

    def get_by_dataset_id(self, dataset_id: UUID, tenant_id: UUID) -> list[Endpoint]:
        """Get all endpoints using a specific dataset within a tenant.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant ID

        Returns:
            List of endpoints
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.dataset_id == dataset_id, Endpoint.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())

    def get_by_model_id(self, model_id: UUID, tenant_id: UUID) -> list[Endpoint]:
        """Get all endpoints using a specific model within a tenant.

        Args:
            model_id: Model UUID
            tenant_id: Tenant ID

        Returns:
            List of endpoints
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.model_id == model_id, Endpoint.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())
