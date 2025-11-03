"""Model repository for database operations."""

from typing import Optional

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

    def get_by_name(self, name: str) -> Optional[Model]:
        """Get a model by name.

        Args:
            name: Model name

        Returns:
            Model if found, None otherwise
        """
        return self.get_by_field("name", name)

    def delete_by_name(self, name: str) -> bool:
        """Delete a model by name.

        Args:
            name: Model name

        Returns:
            True if deleted, False if not found
        """
        return self.delete_by_field("name", name)

    def get_by_type(self, type_name: str) -> list[Model]:
        """Get all models of a specific type.

        Args:
            type_name: Model type name

        Returns:
            List of models
        """
        with self.db.get_session() as session:
            from sqlmodel import select

            statement = select(Model).where(Model.dtype == type_name)
            return list(session.exec(statement).all())
