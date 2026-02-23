"""Dataset repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select

from syft_space.components.datasets.entities import Dataset
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class DatasetRepository(AsyncBaseRepository[Dataset]):
    """Repository for Dataset CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        """Initialize the dataset repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Dataset)

    async def create(self, obj: Dataset) -> Dataset:
        """Create a dataset and ensure endpoints relationship is accessible.

        Args:
            obj: Dataset entity to create

        Returns:
            Created dataset with endpoints relationship accessible
        """
        async with self.db.get_session() as session:
            session.add(obj)
            obj_id = obj.id
            await session.commit()
            # Reload object with endpoints eagerly loaded
            result = await session.exec(
                select(Dataset)
                .where(Dataset.id == obj_id)
                .options(selectinload(Dataset.endpoints))
            )
            reloaded = result.first()
            return reloaded if reloaded else obj

    async def get_all(self, tenant_id: UUID) -> list[Dataset]:
        """Get all datasets for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of datasets with endpoints eagerly loaded
        """
        async with self.db.get_session() as session:
            statement = (
                select(Dataset)
                .where(Dataset.tenant_id == tenant_id)
                .options(selectinload(Dataset.endpoints))
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Dataset | None:
        """Get a dataset by ID within a tenant.

        Includes tenant_id check for authorization - use this for API handlers.

        Args:
            id: Dataset UUID
            tenant_id: Tenant UUID (authorization check)

        Returns:
            Dataset with endpoints eagerly loaded if found or unauthorized, None otherwise
        """
        async with self.db.get_session() as session:
            statement = (
                select(Dataset)
                .where(Dataset.id == id, Dataset.tenant_id == tenant_id)
                .options(selectinload(Dataset.endpoints))
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_name(self, name: str, tenant_id: UUID) -> Dataset | None:
        """Get a dataset by name within a tenant.

        Args:
            name: Dataset name
            tenant_id: Tenant ID

        Returns:
            Dataset with endpoints eagerly loaded if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = (
                select(Dataset)
                .where(Dataset.name == name, Dataset.tenant_id == tenant_id)
                .options(selectinload(Dataset.endpoints))
            )
            result = await session.exec(statement)
            return result.first()

    async def delete_by_name(self, name: str, tenant_id: UUID) -> bool:
        """Delete a dataset by name within a tenant.

        Endpoints attached to this dataset are automatically cascade deleted
        by the database foreign key constraint.

        Args:
            name: Dataset name
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        async with self.db.get_session() as session:
            statement = (
                select(Dataset)
                .where(Dataset.name == name, Dataset.tenant_id == tenant_id)
                .options(selectinload(Dataset.endpoints))
                .with_for_update()
            )
            result = await session.exec(statement)
            obj = result.first()
            if obj:
                await session.delete(obj)
                await session.commit()
                return True
            return False

    async def get_by_type(self, type_name: str, tenant_id: UUID) -> list[Dataset]:
        """Get all datasets of a specific type within a tenant.

        Args:
            type_name: Dataset type name
            tenant_id: Tenant ID

        Returns:
            List of datasets with endpoints eagerly loaded
        """
        async with self.db.get_session() as session:
            statement = (
                select(Dataset)
                .where(Dataset.dtype == type_name, Dataset.tenant_id == tenant_id)
                .options(selectinload(Dataset.endpoints))
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_all_with_provisioner_state_id(self) -> list[Dataset]:
        """Get all datasets that have a provisioner state ID set.

        Returns:
            List of datasets with provisioner_state_id not null
        """
        async with self.db.get_session() as session:
            statement = select(Dataset).where(Dataset.provisioner_state_id.isnot(None))
            result = await session.exec(statement)
            return list(result.all())

    async def update_by_name(
        self,
        name: str,
        tenant_id: UUID,
        *,
        name_new: str | None = None,
        summary: str | None = None,
        tags: str | None = None,
    ) -> Dataset | None:
        """Update a dataset by name within a tenant.

        Uses SELECT FOR UPDATE locking to prevent race conditions when updating
        the name. If name is being changed, it's updated first with proper locking,
        then other fields are updated in the same transaction.

        Args:
            name: Current dataset name
            tenant_id: Tenant ID
            name_new: New dataset name (must be unique per tenant)
            summary: Updated summary
            tags: Updated tags

        Returns:
            Updated dataset if found, None otherwise

        Raises:
            ValueError: If name is being changed and new name already exists
            IntegrityError: If database unique constraint is violated (race condition)
        """
        async with self.db.get_session() as session:
            # Load dataset by current name WITH LOCK to prevent concurrent modifications
            # This ensures no other transaction can modify/delete this dataset
            dataset_stmt = (
                select(Dataset)
                .where(Dataset.name == name, Dataset.tenant_id == tenant_id)
                .with_for_update()
            )
            result = await session.exec(dataset_stmt)
            dataset = result.first()

            if not dataset:
                return None

            # Handle name update first with proper locking if it's being changed
            if name_new is not None and name_new != dataset.name:
                # Lock any existing dataset with the new name to prevent concurrent updates
                # This ensures atomicity: we check AND update in the same locked transaction
                existing_stmt = (
                    select(Dataset)
                    .where(
                        Dataset.name == name_new,
                        Dataset.tenant_id == tenant_id,
                        Dataset.id != dataset.id,  # Exclude current dataset
                    )
                    .with_for_update(
                        nowait=True
                    )  # Fail fast if locked by another transaction
                )
                existing_result = await session.exec(existing_stmt)
                existing = existing_result.first()

                if existing:
                    raise ValueError(
                        f"Dataset '{name_new}' already exists for this tenant"
                    )

                # Update name atomically within the locked transaction
                dataset.name = name_new

            # Apply updates to other fields if provided
            if summary is not None:
                dataset.summary = summary
            if tags is not None:
                dataset.tags = tags

            # Update timestamp
            dataset.updated_at = datetime.now(timezone.utc)

            # Save all changes in single commit
            session.add(dataset)
            dataset_id = dataset.id
            try:
                await session.commit()
                # Reload dataset with endpoints eagerly loaded before returning
                reload_result = await session.exec(
                    select(Dataset)
                    .where(Dataset.id == dataset_id)
                    .options(selectinload(Dataset.endpoints))
                )
                reloaded = reload_result.first()
                return reloaded if reloaded else dataset
            except IntegrityError as e:
                await session.rollback()
                # Re-raise as ValueError for consistent error handling
                raise ValueError(
                    "Unique constraint violation: dataset name may already exist"
                ) from e
