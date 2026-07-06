"""Tests for startup recovery of orphaned ingestion jobs.

A job only reaches IN_PROGRESS while a worker is actively ingesting it. If the
process dies mid-ingest (reload/crash/OOM) the row stays IN_PROGRESS forever,
because the processor only ever claims PENDING jobs. ``reset_orphaned_in_progress``
re-queues those on startup.
"""

from __future__ import annotations

from uuid import uuid4

from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.shared.database import AsyncDatabase


async def _make_job(
    repo: IngestionJobRepository,
    dataset_id,
    tenant_id,
    external_id: str,
    status: IngestionJobStatus,
):
    """Create a job (PENDING) and move it to the requested status."""
    job = await repo.upsert_by_external_id(
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        external_id=external_id,
        fingerprint="fp",
    )
    if status != IngestionJobStatus.PENDING:
        await repo.update_status(job.id, status)
    return job


class TestResetOrphanedInProgress:
    async def test_only_in_progress_is_requeued(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()

        stuck1 = await _make_job(repo, ds, tn, "a.csv", IngestionJobStatus.IN_PROGRESS)
        stuck2 = await _make_job(repo, ds, tn, "b.csv", IngestionJobStatus.IN_PROGRESS)
        pending = await _make_job(repo, ds, tn, "c.csv", IngestionJobStatus.PENDING)
        done = await _make_job(repo, ds, tn, "d.csv", IngestionJobStatus.COMPLETED)
        failed = await _make_job(repo, ds, tn, "e.csv", IngestionJobStatus.FAILED)

        count = await repo.reset_orphaned_in_progress()
        assert count == 2

        # The two orphans are back to PENDING with started_at cleared.
        for job in (stuck1, stuck2):
            row = await repo.get_by_external_id(ds, job.external_id)
            assert row.status == IngestionJobStatus.PENDING.value
            assert row.started_at is None

        # Everything else is untouched.
        assert (
            await repo.get_by_external_id(ds, pending.external_id)
        ).status == IngestionJobStatus.PENDING.value
        assert (
            await repo.get_by_external_id(ds, done.external_id)
        ).status == IngestionJobStatus.COMPLETED.value
        assert (
            await repo.get_by_external_id(ds, failed.external_id)
        ).status == IngestionJobStatus.FAILED.value

    async def test_noop_when_nothing_in_progress(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        assert await repo.reset_orphaned_in_progress() == 0
