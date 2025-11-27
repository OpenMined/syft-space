"""Dataset repository for database operations."""

from typing import Optional
from uuid import UUID

from sqlmodel import select

from syftai_space.components.datasets.entities import Dataset, ProvisionerState
from syftai_space.components.shared.database import BaseRepository, Database


class DatasetRepository(BaseRepository[Dataset]):
    """Repository for Dataset CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the dataset repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Dataset)

    def get_all(self, tenant_id: UUID) -> list[Dataset]:
        """Get all datasets for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of datasets
        """
        with self.db.get_session() as session:
            statement = select(Dataset).where(Dataset.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_by_id(self, id: int, tenant_id: UUID) -> Optional[Dataset]:
        """Get a dataset by ID within a tenant.

        Args:
            id: Dataset ID
            tenant_id: Tenant ID

        Returns:
            Dataset if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Dataset).where(
                Dataset.id == id, Dataset.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def get_by_name(self, name: str, tenant_id: UUID) -> Optional[Dataset]:
        """Get a dataset by name within a tenant.

        Args:
            name: Dataset name
            tenant_id: Tenant ID

        Returns:
            Dataset if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Dataset).where(
                Dataset.name == name, Dataset.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def delete_by_name(self, name: str, tenant_id: UUID) -> bool:
        """Delete a dataset by name within a tenant.

        Args:
            name: Dataset name
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            statement = select(Dataset).where(
                Dataset.name == name, Dataset.tenant_id == tenant_id
            )
            obj = session.exec(statement).first()
            if obj:
                session.delete(obj)
                session.commit()
                return True
            return False

    def get_by_type(self, type_name: str, tenant_id: UUID) -> list[Dataset]:
        """Get all datasets of a specific type within a tenant.

        Args:
            type_name: Dataset type name
            tenant_id: Tenant ID

        Returns:
            List of datasets
        """
        with self.db.get_session() as session:
            statement = select(Dataset).where(
                Dataset.dtype == type_name, Dataset.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())

    def get_all_with_provisioners(self) -> list[Dataset]:
        """Get all datasets that have provisioner state across all tenants.

        Returns:
            List of datasets with provisioner_state relationship
        """
        with self.db.get_session() as session:
            # Join with provisioner_states table to get datasets with provisioners
            statement = select(Dataset).join(
                ProvisionerState, Dataset.id == ProvisionerState.dataset_id
            )
            return list(session.exec(statement).all())
