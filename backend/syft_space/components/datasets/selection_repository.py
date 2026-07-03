"""Repository for dataset selection rows (normalized picker selection).

The selection list for a dataset lives here as one row per selected item,
replacing the list that previously sat inside the dataset ``configuration``
blob. Modelling it as rows makes concurrent add/remove atomic and dedup a
``UNIQUE(dataset_id, item_id)`` constraint rather than app-level logic.

This is the single owner of ``dataset_selection`` queries: ingestion reads
the scope from here, the selection API pages/lists rows through it, and the
endpoint list composes selection counts via ``count_by_datasets`` — so no
other repository joins into this table.
"""

from uuid import UUID

from sqlalchemy import func
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

    async def list_page(
        self, dataset_id: UUID, limit: int, offset: int
    ) -> list[DatasetSelection]:
        """A page of a dataset's selections, oldest first.

        Args:
            dataset_id: Owning dataset
            limit: Maximum rows to return
            offset: Rows to skip

        Returns:
            Selection rows ordered by ``added_at``, sliced to the page.
        """
        async with self.db.get_session() as session:
            statement = (
                select(DatasetSelection)
                .where(DatasetSelection.dataset_id == dataset_id)
                .order_by(DatasetSelection.added_at)
                .offset(offset)
                .limit(limit)
            )
            result = await session.exec(statement)
            return list(result.all())

    async def count_for_dataset(self, dataset_id: UUID) -> int:
        """Count a dataset's selections.

        Args:
            dataset_id: Owning dataset

        Returns:
            Total number of selection rows.
        """
        async with self.db.get_session() as session:
            statement = select(func.count()).where(
                DatasetSelection.dataset_id == dataset_id
            )
            result = await session.exec(statement)
            return int(result.one())

    async def count_by_datasets(self, dataset_ids: list[UUID]) -> dict[UUID, int]:
        """Count selections for several datasets in one grouped query.

        Lets callers (e.g. the endpoint list) show a selection count without
        loading any selection rows — the count is computed in the database.
        Datasets with no selections are absent from the result; callers should
        default those to zero.

        Args:
            dataset_ids: Datasets to count

        Returns:
            ``{dataset_id: count}`` for datasets that have at least one row.
        """
        if not dataset_ids:
            return {}
        async with self.db.get_session() as session:
            statement = (
                select(DatasetSelection.dataset_id, func.count())
                .where(DatasetSelection.dataset_id.in_(dataset_ids))
                .group_by(DatasetSelection.dataset_id)
            )
            result = await session.exec(statement)
            return {row[0]: int(row[1]) for row in result.all()}

    async def list_ids_for_dataset(self, dataset_id: UUID) -> list[str]:
        """List a dataset's selected item ids, oldest first.

        Ids only (no descriptions/timestamps) — cheap to return in full for
        the picker's pre-selection, which needs the complete set, not a page.

        Args:
            dataset_id: Owning dataset

        Returns:
            ``item_id`` values ordered by ``added_at``.
        """
        async with self.db.get_session() as session:
            statement = (
                select(DatasetSelection.item_id)
                .where(DatasetSelection.dataset_id == dataset_id)
                .order_by(DatasetSelection.added_at)
            )
            result = await session.exec(statement)
            return list(result.all())
