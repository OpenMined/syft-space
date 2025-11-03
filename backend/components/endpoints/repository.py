"""Endpoint repository for database operations."""

from typing import Optional
from uuid import UUID

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

    def get_by_slug(self, slug: str) -> Optional[Endpoint]:
        """Get an endpoint by slug.

        Args:
            slug: Endpoint slug

        Returns:
            Endpoint if found, None otherwise
        """
        return self.get_by_field("slug", slug)

    def delete_by_slug(self, slug: str) -> bool:
        """Delete an endpoint by slug.

        Args:
            slug: Endpoint slug

        Returns:
            True if deleted, False if not found
        """
        return self.delete_by_field("slug", slug)

    def get_by_dataset_id(self, dataset_id: UUID) -> list[Endpoint]:
        """Get all endpoints using a specific dataset.

        Args:
            dataset_id: Dataset UUID

        Returns:
            List of endpoints
        """
        with self.db.get_session() as session:
            from sqlmodel import select

            statement = select(Endpoint).where(Endpoint.dataset_id == dataset_id)
            return list(session.exec(statement).all())

    def get_by_model_id(self, model_id: UUID) -> list[Endpoint]:
        """Get all endpoints using a specific model.

        Args:
            model_id: Model UUID

        Returns:
            List of endpoints
        """
        with self.db.get_session() as session:
            from sqlmodel import select

            statement = select(Endpoint).where(Endpoint.model_id == model_id)
            return list(session.exec(statement).all())
