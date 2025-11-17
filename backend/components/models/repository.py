"""Model repository for database operations."""

from typing import Optional
from uuid import UUID

from sqlmodel import select

from components.shared.database import BaseRepository, Database

from .entities import Model


class ModelRepository(BaseRepository[Model]):
    """Repository for Model CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the model repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Model)

    def get_all(self, tenant_id: UUID) -> list[Model]:
        """Get all models for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of models
        """
        with self.db.get_session() as session:
            statement = select(Model).where(Model.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_by_id(self, id: int, tenant_id: UUID) -> Optional[Model]:
        """Get a model by ID within a tenant.

        Args:
            id: Model ID
            tenant_id: Tenant ID

        Returns:
            Model if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Model).where(
                Model.id == id, Model.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def get_by_name(self, name: str, tenant_id: UUID) -> Optional[Model]:
        """Get a model by name within a tenant.

        Args:
            name: Model name
            tenant_id: Tenant ID

        Returns:
            Model if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Model).where(
                Model.name == name, Model.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def delete_by_name(self, name: str, tenant_id: UUID) -> bool:
        """Delete a model by name within a tenant.

        Args:
            name: Model name
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            statement = select(Model).where(
                Model.name == name, Model.tenant_id == tenant_id
            )
            obj = session.exec(statement).first()
            if obj:
                session.delete(obj)
                session.commit()
                return True
            return False

    def get_by_type(self, type_name: str, tenant_id: UUID) -> list[Model]:
        """Get all models of a specific type within a tenant.

        Args:
            type_name: Model type name
            tenant_id: Tenant ID

        Returns:
            List of models
        """
        with self.db.get_session() as session:
            statement = select(Model).where(
                Model.dtype == type_name, Model.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())
