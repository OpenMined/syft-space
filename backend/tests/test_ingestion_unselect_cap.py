"""Tests for unbounded tombstoning on unselection.

Removing a pick tombstones every ingestion job it covered. The old path loaded
jobs via ``get_by_dataset`` (default ``limit=1000``), so a directory pick that
expanded to more than 1000 files left the excess jobs COMPLETED — their vectors
never scheduled for removal. Unselection now reads all live external_ids
(unbounded) and bulk-tombstones the covered ones.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from syft_space.components.datasets.entities import Dataset
from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.manager import IngestionManager
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.shared.database import AsyncDatabase

# Larger than the old get_by_dataset default page (1000) and crossing the bulk
# tombstone's 500-id chunk boundary, so the test exercises both the removed cap
# and the chunking.
_MANY = 1100


async def _seed(
    db: AsyncDatabase,
    ds,
    tn,
    external_ids: list[str],
    status: IngestionJobStatus = IngestionJobStatus.COMPLETED,
) -> None:
    """Insert jobs directly in one commit (FKs aren't enforced in the test DB)."""
    async with db.get_session() as session:
        for ext in external_ids:
            session.add(
                IngestionJob(
                    tenant_id=tn,
                    dataset_id=ds,
                    external_id=ext,
                    fingerprint="fp",
                    status=status.value,
                )
            )
        await session.commit()


class TestActiveExternalIds:
    async def test_returns_all_beyond_default_page(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        await _seed(main_db, ds, tn, [f"f{i}" for i in range(_MANY)])

        ids = await repo.get_active_external_ids(ds, tn)
        assert len(ids) == _MANY  # no 1000-row cap

    async def test_excludes_deleted(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        await _seed(main_db, ds, tn, ["a", "b"], IngestionJobStatus.COMPLETED)
        await _seed(main_db, ds, tn, ["c"], IngestionJobStatus.DELETED)

        ids = await repo.get_active_external_ids(ds, tn)
        assert set(ids) == {"a", "b"}

    async def test_scoped_to_dataset_and_tenant(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        await _seed(main_db, ds, tn, ["mine"])
        await _seed(main_db, uuid4(), tn, ["other-ds"])
        await _seed(main_db, ds, uuid4(), ["other-tenant"])

        ids = await repo.get_active_external_ids(ds, tn)
        assert ids == ["mine"]


class TestBulkTombstone:
    async def test_tombstones_all_across_chunks(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        externals = [f"f{i}" for i in range(_MANY)]
        await _seed(main_db, ds, tn, externals)

        count = await repo.mark_deleted_by_external_ids(ds, externals)
        assert count == _MANY
        assert await repo.get_active_external_ids(ds, tn) == []

    async def test_skips_already_deleted(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        await _seed(main_db, ds, tn, ["a", "b"], IngestionJobStatus.COMPLETED)
        await _seed(main_db, ds, tn, ["c"], IngestionJobStatus.DELETED)

        # Count reflects rows actually flipped, not the already-tombstoned one.
        count = await repo.mark_deleted_by_external_ids(ds, ["a", "b", "c"])
        assert count == 2

    async def test_empty_is_noop(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        assert await repo.mark_deleted_by_external_ids(uuid4(), []) == 0


# ============== Manager-level: the actual cap bug in context ==============


class _CoverAllProvider:
    """Stand-in source provider whose picks cover every item."""

    @classmethod
    def selection_covers(cls, item_id: str, external_id: str) -> bool:
        return True


class _Binding:
    SOURCE_PROVIDER_CLS = _CoverAllProvider


class _FakeRegistry:
    def get_dataset_type(self, dtype):
        return _Binding  # KeyError-free; every dtype maps to the same binding


class TestApplyUnselectionCap:
    async def test_tombstones_all_covered_beyond_1000(self, main_db: AsyncDatabase):
        ds, tn = uuid4(), uuid4()
        await _seed(main_db, ds, tn, [f"f{i}" for i in range(_MANY)])

        dataset = Dataset(name="d", dtype="local_file", configuration={}, tenant_id=tn)
        dataset_repo = Mock(get_by_id=AsyncMock(return_value=dataset))
        mgr = IngestionManager(
            dataset_repository=dataset_repo,
            ingestion_repository=IngestionJobRepository(main_db),
            selection_repository=Mock(),
            registry=_FakeRegistry(),
        )

        count = await mgr.apply_unselection(ds, tn, ["/removed/dir"])

        assert count == _MANY
        repo = IngestionJobRepository(main_db)
        assert await repo.get_active_external_ids(ds, tn) == []
