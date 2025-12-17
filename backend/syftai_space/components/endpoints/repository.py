"""Endpoint repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select

from syftai_space.components.endpoints.entities import Endpoint
from syftai_space.components.shared.database import BaseRepository, Database


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
            statement = (
                select(Endpoint)
                .where(Endpoint.tenant_id == tenant_id)
                .options(selectinload(Endpoint.model), selectinload(Endpoint.dataset))
            )
            return list(session.exec(statement).all())

    def get_by_id(self, id: int, tenant_id: UUID) -> Endpoint | None:
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

    def get_by_slug(self, slug: str, tenant_id: UUID) -> Endpoint | None:
        """Get an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant_id: Tenant ID

        Returns:
            Endpoint if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = (
                select(Endpoint)
                .where(Endpoint.slug == slug, Endpoint.tenant_id == tenant_id)
                .options(selectinload(Endpoint.model), selectinload(Endpoint.dataset))
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

    def add_publication(
        self, endpoint_id: UUID, marketplace_id: UUID, tenant_id: UUID
    ) -> Endpoint | None:
        """Add a marketplace ID to endpoint's published_to list.

        Args:
            endpoint_id: Endpoint ID
            marketplace_id: Marketplace ID to add
            tenant_id: Tenant ID

        Returns:
            Updated endpoint if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.id == endpoint_id, Endpoint.tenant_id == tenant_id
            )
            endpoint = session.exec(statement).first()
            if not endpoint:
                return None

            marketplace_id_str = str(marketplace_id)
            if marketplace_id_str not in endpoint.published_to:
                endpoint.published_to = [*endpoint.published_to, marketplace_id_str]
                endpoint.updated_at = datetime.now(timezone.utc)
                session.add(endpoint)
                session.commit()
                session.refresh(endpoint)

            return endpoint

    def remove_publication(
        self, endpoint_id: UUID, marketplace_id: UUID, tenant_id: UUID
    ) -> Endpoint | None:
        """Remove a marketplace ID from endpoint's published_to list.

        Args:
            endpoint_id: Endpoint ID
            marketplace_id: Marketplace ID to remove
            tenant_id: Tenant ID

        Returns:
            Updated endpoint if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.id == endpoint_id, Endpoint.tenant_id == tenant_id
            )
            endpoint = session.exec(statement).first()
            if not endpoint:
                return None

            marketplace_id_str = str(marketplace_id)
            if marketplace_id_str in endpoint.published_to:
                endpoint.published_to = [
                    mid for mid in endpoint.published_to if mid != marketplace_id_str
                ]
                endpoint.updated_at = datetime.now(timezone.utc)
                session.add(endpoint)
                session.commit()
                session.refresh(endpoint)

            return endpoint
