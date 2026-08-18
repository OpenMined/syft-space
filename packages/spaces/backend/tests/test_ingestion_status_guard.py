"""Tests for the optimistic ``expected_status`` guard on ``update_status``.

A worker marks a job COMPLETED only if the row is still the IN_PROGRESS job it
claimed. If a concurrent edit re-queued the row to PENDING (new fingerprint) or
an unselect tombstoned it to DELETED while the worker ingested, a blind
COMPLETED write would silently drop that newer state — the guard prevents it.
"""

from __future__ import annotations

from uuid import uuid4

from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.shared.database import AsyncDatabase


class TestUpdateStatusGuard:
    async def test_guard_matches_applies_write(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await repo.upsert_by_external_id(
            tenant_id=tn, dataset_id=ds, external_id="a.pdf", fingerprint="fp1"
        )
        await repo.update_status(job.id, IngestionJobStatus.IN_PROGRESS)

        updated = await repo.update_status(
            job.id,
            IngestionJobStatus.COMPLETED,
            expected_status=IngestionJobStatus.IN_PROGRESS,
        )
        assert updated is not None
        assert updated.status == IngestionJobStatus.COMPLETED.value

    async def test_requeued_row_is_not_completed(self, main_db: AsyncDatabase):
        """The lost-update race: an edit re-queues the row mid-ingest."""
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await repo.upsert_by_external_id(
            tenant_id=tn, dataset_id=ds, external_id="a.pdf", fingerprint="fp1"
        )
        await repo.update_status(job.id, IngestionJobStatus.IN_PROGRESS)

        # Concurrent edit while the worker ingests fp1: the scanner re-upserts
        # with a new fingerprint, resetting the row to PENDING/fp2.
        await repo.upsert_by_external_id(
            tenant_id=tn, dataset_id=ds, external_id="a.pdf", fingerprint="fp2"
        )

        # Worker finishes fp1 and tries to complete — guard must refuse.
        result = await repo.update_status(
            job.id,
            IngestionJobStatus.COMPLETED,
            expected_status=IngestionJobStatus.IN_PROGRESS,
        )
        assert result is None

        row = await repo.get_by_external_id(ds, "a.pdf")
        assert row.status == IngestionJobStatus.PENDING.value
        assert row.fingerprint == "fp2"

    async def test_tombstoned_row_is_not_completed(self, main_db: AsyncDatabase):
        """An unselect tombstones the row to DELETED mid-ingest."""
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await repo.upsert_by_external_id(
            tenant_id=tn, dataset_id=ds, external_id="a.pdf", fingerprint="fp1"
        )
        await repo.update_status(job.id, IngestionJobStatus.IN_PROGRESS)

        await repo.mark_deleted_by_external_id(ds, "a.pdf")

        result = await repo.update_status(
            job.id,
            IngestionJobStatus.COMPLETED,
            expected_status=IngestionJobStatus.IN_PROGRESS,
        )
        assert result is None

        row = await repo.get_by_external_id(ds, "a.pdf")
        assert row.status == IngestionJobStatus.DELETED.value

    async def test_guarded_fail_refused_when_row_requeued(self, main_db: AsyncDatabase):
        """A failed ingest of old content must not clobber a re-queued row."""
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await repo.upsert_by_external_id(
            tenant_id=tn, dataset_id=ds, external_id="a.pdf", fingerprint="fp1"
        )
        await repo.update_status(job.id, IngestionJobStatus.IN_PROGRESS)
        await repo.upsert_by_external_id(
            tenant_id=tn, dataset_id=ds, external_id="a.pdf", fingerprint="fp2"
        )

        result = await repo.update_status(
            job.id,
            IngestionJobStatus.FAILED,
            "boom",
            expected_status=IngestionJobStatus.IN_PROGRESS,
        )
        assert result is None
        row = await repo.get_by_external_id(ds, "a.pdf")
        assert row.status == IngestionJobStatus.PENDING.value

    async def test_no_guard_still_writes_unconditionally(self, main_db: AsyncDatabase):
        """Callers that omit expected_status keep the blind-write behaviour.

        This is the pre-claim FAILED path: a job that errors before it is
        claimed is still PENDING and must be failed outright, not left to retry.
        """
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await repo.upsert_by_external_id(
            tenant_id=tn, dataset_id=ds, external_id="a.pdf", fingerprint="fp1"
        )
        updated = await repo.update_status(job.id, IngestionJobStatus.FAILED, "boom")
        assert updated.status == IngestionJobStatus.FAILED.value
