"""Tests that DELETED tombstones stay out of counts and default listings.

A source ``deleted`` event flips a job to DELETED rather than removing the row,
so the external_id<->vector mapping survives. Those tombstones must not show up
as real work: they are excluded entirely from the stats (no count, no total) and
from the default job listing, but remain queryable via an explicit status filter.
"""

from __future__ import annotations

from uuid import uuid4

from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.shared.database import AsyncDatabase


async def _seed(db: AsyncDatabase, ds, tn, by_status: dict[IngestionJobStatus, int]):
    """Insert ``count`` jobs per status directly in one commit."""
    async with db.get_session() as session:
        n = 0
        for status, count in by_status.items():
            for _ in range(count):
                session.add(
                    IngestionJob(
                        tenant_id=tn,
                        dataset_id=ds,
                        external_id=f"e{n}",
                        fingerprint="fp",
                        status=status.value,
                    )
                )
                n += 1
        await session.commit()


class TestStatsExcludeDeleted:
    async def test_total_excludes_deleted(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        await _seed(
            main_db,
            ds,
            tn,
            {
                IngestionJobStatus.COMPLETED: 3,
                IngestionJobStatus.FAILED: 1,
                IngestionJobStatus.DELETED: 5,
            },
        )

        stats = await repo.get_stats_by_dataset(ds, tn)
        assert stats["total"] == 4  # 3 completed + 1 failed, NOT the 5 deleted
        assert stats["completed"] == 3
        assert stats["failed"] == 1
        assert stats["deleted"] == 0  # tombstones filtered out of the query


class TestListingExcludesDeleted:
    async def test_default_listing_omits_deleted(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        await _seed(
            main_db,
            ds,
            tn,
            {IngestionJobStatus.COMPLETED: 2, IngestionJobStatus.DELETED: 3},
        )

        jobs = await repo.get_by_dataset(ds, tn)
        assert len(jobs) == 2
        assert all(j.status != IngestionJobStatus.DELETED.value for j in jobs)

    async def test_explicit_filter_can_still_query_deleted(
        self, main_db: AsyncDatabase
    ):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        await _seed(
            main_db,
            ds,
            tn,
            {IngestionJobStatus.COMPLETED: 2, IngestionJobStatus.DELETED: 3},
        )

        deleted = await repo.get_by_dataset(
            ds, tn, status_filter=[IngestionJobStatus.DELETED]
        )
        assert len(deleted) == 3
        assert all(j.status == IngestionJobStatus.DELETED.value for j in deleted)
