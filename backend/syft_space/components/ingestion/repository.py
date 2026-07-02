"""Repository for IngestionJob database operations."""

from datetime import datetime, timezone
from uuid import UUID

from loguru import logger
from sqlalchemy import func
from sqlmodel import select

from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


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

        Logic:
        - Existing row with matching ``fingerprint`` AND status == COMPLETED → skip.
        - Existing row with different fingerprint OR not completed → reset to PENDING.
        - No existing row → create PENDING.

        The fingerprint comparison is an opaque string equality check —
        sources define the format (see ``BaseSource.fingerprint``); the
        repository treats it as a blob.
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
                if (
                    existing.fingerprint == fingerprint
                    and existing.status == IngestionJobStatus.COMPLETED.value
                ):
                    logger.info(
                        f"Item {external_id} already ingested with same fingerprint"
                    )
                    return existing

                existing.fingerprint = fingerprint
                existing.status = IngestionJobStatus.PENDING.value
                existing.error_message = None
                existing.updated_at = now
                existing.started_at = None
                existing.completed_at = None
                # Keep retry_count for tracking history

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
    ) -> IngestionJob | None:
        """Update job status with appropriate timestamps.

        Args:
            job_id: Job UUID
            status: New status
            error_message: Error message for FAILED status

        Returns:
            Updated job or None if not found
        """
        async with self.db.get_session() as session:
            job = await session.get(IngestionJob, job_id)
            if not job:
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

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)

        Returns:
            Dict with counts per status and total
        """
        async with self.db.get_session() as session:
            # Get counts grouped by status
            stmt = (
                select(IngestionJob.status, func.count())
                .where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.tenant_id == tenant_id,
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
