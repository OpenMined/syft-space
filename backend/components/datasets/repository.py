"""Dataset repository for database operations."""

from typing import Optional

from components.shared.database import BaseRepository, Database

from .entities import Dataset


class DatasetRepository(BaseRepository[Dataset]):
    """Repository for Dataset CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the dataset repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Dataset)

    def get_by_name(self, name: str) -> Optional[Dataset]:
        """Get a dataset by name.

        Args:
            name: Dataset name

        Returns:
            Dataset if found, None otherwise
        """
        return self.get_by_field("name", name)

    def delete_by_name(self, name: str) -> bool:
        """Delete a dataset by name.

        Args:
            name: Dataset name

        Returns:
            True if deleted, False if not found
        """
        return self.delete_by_field("name", name)

    def get_by_type(self, type_name: str) -> list[Dataset]:
        """Get all datasets of a specific type.

        Args:
            type_name: Dataset type name

        Returns:
            List of datasets
        """
        with self.db.get_session() as session:
            from sqlmodel import select

            statement = select(Dataset).where(Dataset.dtype == type_name)
            return list(session.exec(statement).all())
