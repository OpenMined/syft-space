"""Ingestion API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.handlers import IngestionHandler
from syft_space.components.ingestion.schemas import (
    IngestionJobListResponse,
    IngestionStatusResponse,
    RetryIngestionResponse,
    StartIngestionResponse,
    StopIngestionResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_ingestion_routes(handler: IngestionHandler) -> APIRouter:
    """Build the ingestion routes.

    Args:
        handler: Ingestion handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/ingestion", tags=["ingestion"])

    def get_handler() -> IngestionHandler:
        """Dependency to get the ingestion handler."""
        return handler

    @router.get("/datasets/{dataset_id}/status", response_model=IngestionStatusResponse)
    async def get_ingestion_status(
        dataset_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: IngestionHandler = Depends(get_handler),
    ) -> IngestionStatusResponse:
        """Get ingestion status for a dataset.

        Returns aggregated statistics including pending, completed, failed counts
        and whether the watcher is currently active.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant (injected)

        Returns:
            Ingestion status with progress information
        """
        return handler.get_ingestion_status(dataset_id, tenant)

    @router.get("/datasets/{dataset_id}/jobs", response_model=IngestionJobListResponse)
    async def list_ingestion_jobs(
        dataset_id: UUID,
        status: IngestionJobStatus | None = Query(
            None, description="Filter by job status"
        ),
        limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
        offset: int = Query(0, ge=0, description="Pagination offset"),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: IngestionHandler = Depends(get_handler),
    ) -> IngestionJobListResponse:
        """List ingestion jobs for a dataset.

        Args:
            dataset_id: Dataset UUID
            status: Optional IngestionJobStatus to filter by
            limit: Maximum results (default 100)
            offset: Pagination offset
            tenant: Current tenant (injected)

        Returns:
            Paginated list of ingestion jobs
        """
        return handler.list_ingestion_jobs(dataset_id, tenant, status, limit, offset)

    @router.post("/datasets/{dataset_id}/start", response_model=StartIngestionResponse)
    async def start_ingestion(
        dataset_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: IngestionHandler = Depends(get_handler),
    ) -> StartIngestionResponse:
        """Start ingestion for a dataset.

        Scans existing files in the dataset's filePaths, creates ingestion jobs,
        and starts the file watcher.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant (injected)

        Returns:
            Start response with number of jobs created
        """
        return handler.start_ingestion(dataset_id, tenant)

    @router.post("/datasets/{dataset_id}/stop", response_model=StopIngestionResponse)
    async def stop_ingestion(
        dataset_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: IngestionHandler = Depends(get_handler),
    ) -> StopIngestionResponse:
        """Stop ingestion for a dataset.

        Stops the file watcher and cancels all pending jobs.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant (injected)

        Returns:
            Stop response with number of jobs cancelled
        """
        return handler.stop_ingestion(dataset_id, tenant)

    @router.post("/datasets/{dataset_id}/retry", response_model=RetryIngestionResponse)
    async def retry_failed_ingestion(
        dataset_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: IngestionHandler = Depends(get_handler),
    ) -> RetryIngestionResponse:
        """Retry failed ingestion jobs for a dataset.

        Resets all failed jobs to pending status so they will be re-processed.

        Args:
            dataset_id: Dataset UUID
            tenant: Current tenant (injected)

        Returns:
            Number of jobs reset for retry
        """
        return handler.retry_failed_jobs(dataset_id, tenant)

    return router
