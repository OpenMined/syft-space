"""Ingestion handlers for business logic."""

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException

from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.manager import IngestionManager
from syft_space.components.ingestion.schemas import (
    IngestionJobListResponse,
    IngestionJobResponse,
    IngestionStatusResponse,
    RetryIngestionResponse,
    StartIngestionResponse,
    StopIngestionResponse,
)
from syft_space.components.tenants.entities import Tenant

if TYPE_CHECKING:
    from syft_space.components.datasets.repository import DatasetRepository


class IngestionHandler:
    """Handler for ingestion business logic."""

    def __init__(
        self,
        ingestion_manager: IngestionManager,
        dataset_repository: "DatasetRepository",
    ):
        """Initialize the ingestion handler.

        Args:
            ingestion_manager: Ingestion manager instance
            dataset_repository: Dataset repository (for lookups)
        """
        self.ingestion_manager = ingestion_manager
        self.dataset_repository = dataset_repository

    async def _get_dataset_or_404(self, dataset_id: UUID, tenant: Tenant):
        """Get dataset by ID or raise 404.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant (for authorization)

        Returns:
            Dataset entity

        Raises:
            HTTPException: If dataset not found or doesn't belong to tenant
        """
        dataset = await self.dataset_repository.get_by_id(dataset_id, tenant.id)
        if not dataset:
            raise HTTPException(
                status_code=404, detail=f"Dataset '{dataset_id}' not found"
            )
        return dataset

    async def get_ingestion_status(
        self, dataset_id: UUID, tenant: Tenant
    ) -> IngestionStatusResponse:
        """Get ingestion status for a dataset.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant

        Returns:
            Ingestion status with progress information
        """
        dataset = await self._get_dataset_or_404(dataset_id, tenant)

        stats = await self.ingestion_manager.get_ingestion_stats(dataset.id, tenant.id)

        is_watching = self.ingestion_manager.is_watching(dataset.id)

        return IngestionStatusResponse(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            is_watching=is_watching,
            total_jobs=stats["total"],
            pending=stats[IngestionJobStatus.PENDING.value],
            in_progress=stats[IngestionJobStatus.IN_PROGRESS.value],
            completed=stats[IngestionJobStatus.COMPLETED.value],
            failed=stats[IngestionJobStatus.FAILED.value],
            cancelled=stats[IngestionJobStatus.CANCELLED.value],
            deleted=stats[IngestionJobStatus.DELETED.value],
        )

    async def list_ingestion_jobs(
        self,
        dataset_id: UUID,
        tenant: Tenant,
        status_filter: IngestionJobStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> IngestionJobListResponse:
        """List ingestion jobs for a dataset.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant
            status_filter: Optional IngestionJobStatus enum to filter by
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Paginated list of ingestion jobs
        """
        dataset = await self._get_dataset_or_404(dataset_id, tenant)

        status_list = [status_filter] if status_filter else None
        jobs = await self.ingestion_manager.get_ingestion_jobs(
            dataset.id,
            tenant.id,
            status_filter=status_list,
            limit=limit,
            offset=offset,
        )

        # Get total count for pagination
        stats = await self.ingestion_manager.get_ingestion_stats(dataset.id, tenant.id)
        total = (
            stats.get(status_filter.value, stats["total"])
            if status_filter
            else stats["total"]
        )

        return IngestionJobListResponse(
            jobs=[IngestionJobResponse.model_validate(j) for j in jobs],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def start_ingestion(
        self, dataset_id: UUID, tenant: Tenant
    ) -> StartIngestionResponse:
        """Start ingestion for a dataset.

        Scans existing files and starts watcher.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant

        Returns:
            Start ingestion response
        """
        dataset = await self._get_dataset_or_404(dataset_id, tenant)

        # Check if already watching
        if self.ingestion_manager.is_watching(dataset.id):
            return StartIngestionResponse(
                message=f"Ingestion already running for dataset '{dataset.name}'",
                jobs_created=0,
                is_watching=True,
            )

        try:
            jobs_created = await self.ingestion_manager.start_dataset_ingestion(dataset)
            return StartIngestionResponse(
                message=f"Started ingestion for dataset '{dataset.name}'",
                jobs_created=jobs_created,
                is_watching=True,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    async def stop_ingestion(
        self, dataset_id: UUID, tenant: Tenant
    ) -> StopIngestionResponse:
        """Stop ingestion for a dataset.

        Stops watcher and cancels pending jobs.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant

        Returns:
            Stop ingestion response
        """
        dataset = await self._get_dataset_or_404(dataset_id, tenant)

        if not self.ingestion_manager.is_watching(dataset.id):
            return StopIngestionResponse(
                message=f"Ingestion not running for dataset '{dataset.name}'",
                jobs_cancelled=0,
            )

        jobs_cancelled = await self.ingestion_manager.stop_dataset_ingestion(dataset.id)
        return StopIngestionResponse(
            message=f"Stopped ingestion for dataset '{dataset.name}'",
            jobs_cancelled=jobs_cancelled,
        )

    async def retry_failed_jobs(
        self, dataset_id: UUID, tenant: Tenant
    ) -> RetryIngestionResponse:
        """Retry failed ingestion jobs for a dataset.

        Resets failed jobs to pending status.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant

        Returns:
            Retry response
        """
        dataset = await self._get_dataset_or_404(dataset_id, tenant)

        jobs_reset = await self.ingestion_manager.retry_failed_jobs(
            dataset.id, tenant.id
        )

        return RetryIngestionResponse(
            message=f"Reset {jobs_reset} failed jobs to pending",
            jobs_reset=jobs_reset,
        )
