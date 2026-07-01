"""Repository for dataset selection rows (normalized picker selection).

The selection list for a dataset lives here as one row per selected item,
replacing the list that previously sat inside the dataset ``configuration``
blob. Modelling it as rows makes concurrent add/remove atomic and dedup a
``UNIQUE(dataset_id, item_id)`` constraint rather than app-level logic.

Phase 1: this repository is additive and not yet wired into ingestion or the
API — it exists so the table has a typed access layer and test coverage.
"""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from syft_space.components.datasets.entities import DatasetSelection
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class DatasetSelectionRepository(AsyncBaseRepository[DatasetSelection]):
    """CRUD for ``dataset_selection`` rows."""

    def __init__(self, db: AsyncDatabase):
        """Initialize the dataset selection repository.

        Args:
            db: Database instance
        """
        super().__init__(db, DatasetSelection)

    async def add(
        self,
        dataset_id: UUID,
        item_id: str,
        description: str | None = None,
    ) -> bool:
        """Add one selection, ignoring duplicates.

        Dedup is enforced by the ``UNIQUE(dataset_id, item_id)`` constraint:
        a duplicate insert is caught and reported as "not added" rather than
        raised, so callers can treat add as idempotent.

        Args:
            dataset_id: Owning dataset
            item_id: Picker id-space identifier (path | ``{post_type}:{id}``)
            description: Optional user-provided description

        Returns:
            True if a new row was inserted, False if it already existed.
        """
        async with self.db.get_session() as session:
            session.add(
                DatasetSelection(
                    dataset_id=dataset_id,
                    item_id=item_id,
                    description=description,
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    async def remove(self, dataset_id: UUID, item_id: str) -> bool:
        """Remove one selection.

        Args:
            dataset_id: Owning dataset
            item_id: Item to remove

        Returns:
            True if a row was deleted, False if it was not present.
        """
        async with self.db.get_session() as session:
            statement = select(DatasetSelection).where(
                DatasetSelection.dataset_id == dataset_id,
                DatasetSelection.item_id == item_id,
            )
            result = await session.exec(statement)
            obj = result.first()
            if obj is None:
                return False
            await session.delete(obj)
            await session.commit()
            return True

    async def list_for_dataset(self, dataset_id: UUID) -> list[DatasetSelection]:
        """List a dataset's selections, oldest first.

        Args:
            dataset_id: Owning dataset

        Returns:
            Selection rows ordered by ``added_at``.
        """
        async with self.db.get_session() as session:
            statement = (
                select(DatasetSelection)
                .where(DatasetSelection.dataset_id == dataset_id)
                .order_by(DatasetSelection.added_at)
            )
            result = await session.exec(statement)
            return list(result.all())
