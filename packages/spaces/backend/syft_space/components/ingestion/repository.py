"""Repository for IngestionJob database operations."""

from datetime import datetime, timezone
from uuid import UUID

from loguru import logger
from sqlalchemy import func
from sqlmodel import select

from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase

# How many times an unchanged item may fail before we stop re-queuing it.
# Sources re-emit their items (WordPress polls on an interval, filesystem
# streams re-scan on restart), and each re-emit would otherwise reset a FAILED
# job to PENDING and retry it forever. This caps the automatic retries so a
# poison item (malformed/unsupported content) settles as FAILED, while
# transient failures still get a few attempts. A changed fingerprint resets the
# count, so edited content gets a fresh budget.
MAX_INGEST_RETRIES = 3


class IngestionJobRepository(AsyncBaseRepository[IngestionJob]):
    """Repository for IngestionJob CRUD operations.

    Key operations:
    - upsert_by_external_id(): Create or update job by source-unique id
      (for source change-stream events)
    - get_by_external_id(): Lookup by source-unique id
    - get_pending_jobs(): Get jobs ready for processing
    - get_by_dataset(): Get all jobs for a dataset
    - update_status(): Update job status with timestamps
    - get_stats_by_dataset(): Get aggregated statistics
    - cancel_pending_by_dataset(): Cancel all pending jobs for a dataset
    - mark_deleted_by_external_id(): Tombstone a job on a source deleted event
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize the ingestion job repository.

        Args:
            db: Database instance
        """
        super().__init__(db, IngestionJob)

    async def upsert_by_external_id(
        self,
        *,
        tenant_id: UUID,
        dataset_id: UUID,
        external_id: str,
        fingerprint: str,
    ) -> IngestionJob:
        """Create or update an ingestion job by source-unique id.

        The fingerprint is an opaque string the source owns (see
        ``BaseSource.fingerprint``); the repository only compares it for
        equality. Same fingerprint means the item is unchanged.

        Logic:
        - Unchanged AND COMPLETED → skip (already ingested).
        - Unchanged AND FAILED past its retry budget → skip. Sources re-emit
          items on every poll/re-scan; without this a permanently-failing item
          would reset to PENDING and retry forever (see ``MAX_INGEST_RETRIES``).
        - Otherwise → (re)queue as PENDING. A changed fingerprint also resets
          the retry budget, since it is effectively new content.
        - No existing row → create PENDING.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.external_id == external_id,
                )
            )
            existing = result.first()

            now = datetime.now(timezone.utc)

            if existing:
                unchanged = existing.fingerprint == fingerprint
                settled = existing.status == IngestionJobStatus.COMPLETED.value or (
                    existing.status == IngestionJobStatus.FAILED.value
                    and existing.retry_count >= MAX_INGEST_RETRIES
                )
                if unchanged and settled:
                    # Already done, or a poison item that exhausted its retries.
                    # Don't re-queue — this is what stops the source's re-emit
                    # loop from retrying the same content indefinitely.
                    logger.info(
                        f"Item {external_id} not re-queued "
                        f"(status={existing.status}, fingerprint unchanged)"
                    )
                    return existing

                existing.fingerprint = fingerprint
                existing.status = IngestionJobStatus.PENDING.value
                existing.error_message = None
                existing.updated_at = now
                existing.started_at = None
                existing.completed_at = None
                if not unchanged:
                    # New content — give it a fresh retry budget. On unchanged
                    # content retry_count is preserved so repeated failures
                    # accumulate toward MAX_INGEST_RETRIES.
                    existing.retry_count = 0

                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                job = IngestionJob(
                    tenant_id=tenant_id,
                    dataset_id=dataset_id,
                    external_id=external_id,
                    fingerprint=fingerprint,
                    status=IngestionJobStatus.PENDING.value,
                    created_at=now,
                    updated_at=now,
                )
                session.add(job)
                await session.commit()
                await session.refresh(job)
                return job

    async def get_completed_fingerprints(self, dataset_id: UUID) -> dict[str, str]:
        """Map of ``external_id -> fingerprint`` for a dataset's COMPLETED jobs.

        Loaded once at stream start as an in-memory skip-map: an event whose
        fingerprint matches its map entry is dropped without a per-item
        query. Only COMPLETED rows are safe to skip from a snapshot — a
        completed job never regresses on its own, and a changed item
        produces a different fingerprint that misses the map and falls
        through to ``upsert_by_external_id``'s fresh check.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob.external_id, IngestionJob.fingerprint).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.status == IngestionJobStatus.COMPLETED.value,
                )
            )
            return dict(result.all())

    async def get_by_external_id(
        self, dataset_id: UUID, external_id: str
    ) -> IngestionJob | None:
        """Return the job for ``(dataset_id, external_id)`` if any."""
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.external_id == external_id,
                )
            )
            return result.first()

    async def get_pending_jobs(
        self,
        dataset_id: UUID | None = None,
        limit: int = 100,
    ) -> list[IngestionJob]:
        """Get pending jobs ready for processing.

        Args:
            dataset_id: Optional filter by dataset
            limit: Maximum jobs to return

        Returns:
            List of pending IngestionJobs ordered by created_at
        """
        async with self.db.get_session() as session:
            stmt = select(IngestionJob).where(
                IngestionJob.status == IngestionJobStatus.PENDING.value
            )

            if dataset_id:
                stmt = stmt.where(IngestionJob.dataset_id == dataset_id)

            stmt = stmt.order_by(IngestionJob.created_at).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    async def get_by_dataset(
        self,
        dataset_id: UUID,
        tenant_id: UUID,
        status_filter: list[IngestionJobStatus] | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[IngestionJob]:
        """Get all jobs for a dataset with optional status filter.

        DELETED rows are tombstones kept only for the external_id<->vector
        mapping, not real jobs — they are excluded from the default listing.
        Pass an explicit ``status_filter`` to query them.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)
            status_filter: Optional list of IngestionJobStatus enums to filter by
            limit: Maximum jobs to return
            offset: Pagination offset

        Returns:
            List of IngestionJobs
        """
        async with self.db.get_session() as session:
            stmt = select(IngestionJob).where(
                IngestionJob.dataset_id == dataset_id,
                IngestionJob.tenant_id == tenant_id,
            )

            if status_filter:
                status_values = [s.value for s in status_filter]
                stmt = stmt.where(IngestionJob.status.in_(status_values))
            else:
                stmt = stmt.where(
                    IngestionJob.status != IngestionJobStatus.DELETED.value
                )

            stmt = (
                stmt.order_by(IngestionJob.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def update_status(
        self,
        job_id: UUID,
        status: IngestionJobStatus,
        error_message: str | None = None,
        expected_status: IngestionJobStatus | None = None,
    ) -> IngestionJob | None:
        """Update job status with appropriate timestamps.

        Args:
            job_id: Job UUID
            status: New status
            error_message: Error message for FAILED status
            expected_status: Optimistic guard. If given, the write applies only
                when the row is currently in this status; on mismatch the row is
                left untouched and ``None`` is returned. Lets a worker reach a
                terminal state only if nothing changed the row while it worked —
                e.g. a concurrent edit re-queued it to PENDING, or an unselect
                tombstoned it to DELETED.

        Returns:
            Updated job, or ``None`` if not found or the ``expected_status``
            guard did not match.
        """
        async with self.db.get_session() as session:
            job = await session.get(IngestionJob, job_id)
            if not job:
                return None

            if expected_status is not None and job.status != expected_status.value:
                logger.info(
                    f"Skipping {status.value} for job {job_id}: expected "
                    f"{expected_status.value} but row is {job.status} "
                    "(changed under the worker)"
                )
                return None

            now = datetime.now(timezone.utc)
            job.status = status.value
            job.updated_at = now

            if status == IngestionJobStatus.IN_PROGRESS:
                job.started_at = now
            elif status in (IngestionJobStatus.COMPLETED, IngestionJobStatus.FAILED):
                job.completed_at = now
                if status == IngestionJobStatus.FAILED:
                    job.error_message = error_message
                    job.retry_count += 1
            elif status == IngestionJobStatus.CANCELLED:
                job.completed_at = now

            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    async def get_stats_by_dataset(
        self, dataset_id: UUID, tenant_id: UUID
    ) -> dict[str, int]:
        """Get aggregated job statistics for a dataset.

        DELETED tombstones are excluded entirely — they are kept only for the
        external_id<->vector mapping, not counted as jobs — so no status count
        or ``total`` inflates as items are deleted.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)

        Returns:
            Dict with counts per non-deleted status and total
        """
        async with self.db.get_session() as session:
            # Get counts grouped by status
            stmt = (
                select(IngestionJob.status, func.count())
                .where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.tenant_id == tenant_id,
                    IngestionJob.status != IngestionJobStatus.DELETED.value,
                )
                .group_by(IngestionJob.status)
            )
            result = await session.exec(stmt)
            results = result.all()

            stats = {status.value: 0 for status in IngestionJobStatus}
            stats["total"] = 0

            for status, count in results:
                stats[status] = count
                stats["total"] += count

            return stats

    async def cancel_pending_by_dataset(self, dataset_id: UUID) -> int:
        """Cancel all pending jobs for a dataset.

        Args:
            dataset_id: Dataset UUID

        Returns:
            Number of jobs cancelled
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.status == IngestionJobStatus.PENDING.value,
                )
            )
            jobs = result.all()

            now = datetime.now(timezone.utc)
            count = 0
            for job in jobs:
                job.status = IngestionJobStatus.CANCELLED.value
                job.updated_at = now
                job.completed_at = now
                session.add(job)
                count += 1

            await session.commit()
            return count

    async def mark_deleted_by_external_id(
        self, dataset_id: UUID, external_id: str
    ) -> bool:
        """Tombstone a job by source-unique id (for source ``deleted`` events).

        Flips the row to DELETED instead of removing it, preserving the
        ``external_id``<->dataset mapping required to remove the item's
        vectors. A re-created item resurrects the row via
        ``upsert_by_external_id``.

        Returns True if a row was tombstoned, False if no match.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.external_id == external_id,
                )
            )
            job = result.first()

            if job:
                now = datetime.now(timezone.utc)
                job.status = IngestionJobStatus.DELETED.value
                job.updated_at = now
                job.completed_at = now
                session.add(job)
                await session.commit()
                return True
            return False

    async def get_active_external_ids(
        self, dataset_id: UUID, tenant_id: UUID
    ) -> list[str]:
        """Every non-tombstoned job's ``external_id`` for a dataset (unbounded).

        Backs unselection: the caller needs to test *all* live jobs against the
        removed picks, so this returns the full set with no page limit. A
        single-column projection keeps it cheap even for large datasets.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob.external_id).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.tenant_id == tenant_id,
                    IngestionJob.status != IngestionJobStatus.DELETED.value,
                )
            )
            return list(result.all())

    async def mark_deleted_by_external_ids(
        self, dataset_id: UUID, external_ids: list[str]
    ) -> int:
        """Tombstone many jobs by source-unique id in one pass.

        Bulk form of ``mark_deleted_by_external_id`` for unselection, which may
        cover thousands of jobs. Already-DELETED rows are skipped so the count
        reflects rows actually tombstoned. The id list is chunked to stay under
        SQLite's bound-parameter limit.

        Returns the number of rows tombstoned.
        """
        if not external_ids:
            return 0
        # Well under SQLite's ~999 bound-variable ceiling, with headroom for the
        # other predicates in the WHERE clause.
        chunk_size = 500
        count = 0
        async with self.db.get_session() as session:
            now = datetime.now(timezone.utc)
            for start in range(0, len(external_ids), chunk_size):
                chunk = external_ids[start : start + chunk_size]
                result = await session.exec(
                    select(IngestionJob).where(
                        IngestionJob.dataset_id == dataset_id,
                        IngestionJob.external_id.in_(chunk),
                        IngestionJob.status != IngestionJobStatus.DELETED.value,
                    )
                )
                for job in result.all():
                    job.status = IngestionJobStatus.DELETED.value
                    job.updated_at = now
                    job.completed_at = now
                    session.add(job)
                    count += 1
            await session.commit()
            return count

    async def reset_orphaned_in_progress(self) -> int:
        """Re-queue every IN_PROGRESS job (startup recovery).

        A job is only IN_PROGRESS while a worker is actively ingesting it. On a
        fresh process start no worker is running yet, so any IN_PROGRESS row is
        an orphan left by a previous process that died mid-ingest (reload,
        crash, OOM) — it would otherwise sit IN_PROGRESS forever, since the
        processor only ever claims PENDING jobs. Reset them to PENDING so they
        are picked up again.

        Single-instance assumption: one server process per database. Do not
        call this while another instance may be processing the same DB, or it
        would yank that instance's in-flight jobs back to PENDING.

        Returns:
            Number of jobs re-queued.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.status == IngestionJobStatus.IN_PROGRESS.value,
                )
            )
            jobs = result.all()

            now = datetime.now(timezone.utc)
            count = 0
            for job in jobs:
                job.status = IngestionJobStatus.PENDING.value
                job.updated_at = now
                job.started_at = None
                session.add(job)
                count += 1

            await session.commit()
            return count

    async def reset_failed_jobs(self, dataset_id: UUID, tenant_id: UUID) -> int:
        """Reset all failed jobs to pending for retry.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)

        Returns:
            Number of jobs reset
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.tenant_id == tenant_id,
                    IngestionJob.status == IngestionJobStatus.FAILED.value,
                )
            )
            jobs = result.all()

            now = datetime.now(timezone.utc)
            count = 0
            for job in jobs:
                job.status = IngestionJobStatus.PENDING.value
                job.updated_at = now
                job.started_at = None
                job.completed_at = None
                job.error_message = None
                session.add(job)
                count += 1

            await session.commit()
            return count
