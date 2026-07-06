"""Tests for the retry cap on ``upsert_by_external_id``.

Sources re-emit their items on every poll/re-scan, and each re-emit resets a
non-terminal job back to PENDING. Without a cap, a permanently-failing item
would retry forever. ``upsert_by_external_id`` stops re-queuing an *unchanged*
item once it has failed ``MAX_INGEST_RETRIES`` times; a changed fingerprint
(edited content) resets the budget.
"""

from __future__ import annotations

from uuid import uuid4

from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.repository import (
    MAX_INGEST_RETRIES,
    IngestionJobRepository,
)
from syft_space.components.shared.database import AsyncDatabase


async def _fail_once(repo: IngestionJobRepository, job_id) -> None:
    """Drive a job through one processing attempt that fails (bumps retry_count)."""
    await repo.update_status(job_id, IngestionJobStatus.IN_PROGRESS)
    await repo.update_status(
        job_id,
        IngestionJobStatus.FAILED,
        "boom",
        expected_status=IngestionJobStatus.IN_PROGRESS,
    )


async def _upsert(repo: IngestionJobRepository, ds, tn, ext="a.pdf", fp="fp1"):
    return await repo.upsert_by_external_id(
        tenant_id=tn, dataset_id=ds, external_id=ext, fingerprint=fp
    )


class TestRetryCap:
    async def test_failed_under_budget_is_requeued(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await _upsert(repo, ds, tn)
        await _fail_once(repo, job.id)  # retry_count -> 1

        requeued = await _upsert(repo, ds, tn)  # unchanged, 1 < MAX
        assert requeued.status == IngestionJobStatus.PENDING.value
        assert requeued.retry_count == 1  # preserved, accumulating toward cap

    async def test_failed_at_budget_is_not_requeued(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await _upsert(repo, ds, tn)

        # Fail it exactly MAX_INGEST_RETRIES times, re-queuing between attempts.
        for _ in range(MAX_INGEST_RETRIES):
            row = await _upsert(repo, ds, tn)
            assert row.status == IngestionJobStatus.PENDING.value
            await _fail_once(repo, job.id)

        # The next re-emit (same fingerprint) must not re-queue it.
        capped = await _upsert(repo, ds, tn)
        assert capped.status == IngestionJobStatus.FAILED.value
        assert capped.retry_count == MAX_INGEST_RETRIES

    async def test_changed_fingerprint_resets_budget(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await _upsert(repo, ds, tn, fp="fp1")
        for _ in range(MAX_INGEST_RETRIES):
            await _upsert(repo, ds, tn, fp="fp1")
            await _fail_once(repo, job.id)

        # Confirm it is capped on the old content.
        capped = await _upsert(repo, ds, tn, fp="fp1")
        assert capped.status == IngestionJobStatus.FAILED.value

        # Edited content (new fingerprint) gets a fresh budget and re-queues.
        edited = await _upsert(repo, ds, tn, fp="fp2")
        assert edited.status == IngestionJobStatus.PENDING.value
        assert edited.retry_count == 0

    async def test_completed_unchanged_is_skipped(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await _upsert(repo, ds, tn)
        await repo.update_status(job.id, IngestionJobStatus.IN_PROGRESS)
        await repo.update_status(
            job.id,
            IngestionJobStatus.COMPLETED,
            expected_status=IngestionJobStatus.IN_PROGRESS,
        )

        again = await _upsert(repo, ds, tn)  # same fp, COMPLETED
        assert again.status == IngestionJobStatus.COMPLETED.value

    async def test_completed_changed_is_requeued(self, main_db: AsyncDatabase):
        repo = IngestionJobRepository(main_db)
        ds, tn = uuid4(), uuid4()
        job = await _upsert(repo, ds, tn, fp="fp1")
        await repo.update_status(job.id, IngestionJobStatus.IN_PROGRESS)
        await repo.update_status(
            job.id,
            IngestionJobStatus.COMPLETED,
            expected_status=IngestionJobStatus.IN_PROGRESS,
        )

        edited = await _upsert(repo, ds, tn, fp="fp2")  # changed content
        assert edited.status == IngestionJobStatus.PENDING.value
