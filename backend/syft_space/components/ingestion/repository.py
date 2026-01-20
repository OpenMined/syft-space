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
    - upsert_by_path(): Create or update job by file path (for watcher events)
    - get_pending_jobs(): Get jobs ready for processing
    - get_by_dataset(): Get all jobs for a dataset
    - update_status(): Update job status with timestamps
    - get_stats_by_dataset(): Get aggregated statistics
    - cancel_pending_by_dataset(): Cancel all pending jobs for a dataset
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize the ingestion job repository.

        Args:
            db: Database instance
        """
        super().__init__(db, IngestionJob)

    async def upsert_by_path(
        self,
        tenant_id: UUID,
        dataset_id: UUID,
        file_path: str,
        file_name: str,
        file_size: int,
        file_mtime_ns: int,
    ) -> IngestionJob:
        """Create or update an ingestion job by file path.

        Logic:
        - If job exists with same fingerprint AND status == COMPLETED → no change (skip)
        - If job exists with different fingerprint OR status != COMPLETED → reset to PENDING
        - If job doesn't exist → create PENDING job

        Args:
            tenant_id: Tenant UUID
            dataset_id: Dataset UUID
            file_path: Absolute file path
            file_name: File basename
            file_size: Size in bytes
            file_mtime_ns: Modification time in nanoseconds

        Returns:
            Created or updated IngestionJob
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.file_path == file_path,
                )
            )
            existing = result.first()

            now = datetime.now(timezone.utc)

            if existing:
                # Check if fingerprint unchanged AND already completed
                fingerprint_unchanged = (
                    existing.file_size == file_size
                    and existing.file_mtime_ns == file_mtime_ns
                )
                if (
                    fingerprint_unchanged
                    and existing.status == IngestionJobStatus.COMPLETED.value
                ):
                    # No change needed, file already ingested with same fingerprint
                    logger.info(
                        f"File {file_path} already ingested with same fingerprint"
                    )
                    return existing

                # Fingerprint changed or not completed - reset to pending
                existing.file_size = file_size
                existing.file_mtime_ns = file_mtime_ns
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
                # Create new job
                job = IngestionJob(
                    tenant_id=tenant_id,
                    dataset_id=dataset_id,
                    file_path=file_path,
                    file_name=file_name,
                    file_size=file_size,
                    file_mtime_ns=file_mtime_ns,
                    status=IngestionJobStatus.PENDING.value,
                    created_at=now,
                    updated_at=now,
                )
                session.add(job)
                await session.commit()
                await session.refresh(job)
                return job

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

            stats = {
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "total": 0,
            }

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

    async def delete_by_path(self, dataset_id: UUID, file_path: str) -> bool:
        """Delete a job by file path (for file deletion events).

        Args:
            dataset_id: Dataset UUID
            file_path: File path to delete

        Returns:
            True if deleted, False if not found
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(IngestionJob).where(
                    IngestionJob.dataset_id == dataset_id,
                    IngestionJob.file_path == file_path,
                )
            )
            job = result.first()

            if job:
                await session.delete(job)
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
