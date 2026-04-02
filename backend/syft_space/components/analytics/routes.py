"""Analytics API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from syft_space.components.analytics.handlers import AnalyticsHandler
from syft_space.components.analytics.schemas import (
    SummaryStatsResponse,
    TimeRange,
    TimeSeriesResponse,
    TopUsersResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_analytics_routes(handler: AnalyticsHandler) -> APIRouter:
    """Build analytics API routes."""
    router = APIRouter(prefix="/analytics", tags=["analytics"])

    def get_handler() -> AnalyticsHandler:
        return handler

    @router.get("/summary", response_model=SummaryStatsResponse)
    async def get_summary(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: AnalyticsHandler = Depends(get_handler),
        time_range: TimeRange = Query(default=TimeRange.THIRTY_DAYS),
        endpoint_id: UUID | None = Query(default=None),
        dataset_id: UUID | None = Query(default=None),
    ) -> SummaryStatsResponse:
        """Get summary statistics for the 4 dashboard stat cards."""
        return await handler.get_summary_stats(
            tenant, time_range, endpoint_id, dataset_id
        )

    @router.get("/time-series", response_model=TimeSeriesResponse)
    async def get_time_series(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: AnalyticsHandler = Depends(get_handler),
        time_range: TimeRange = Query(default=TimeRange.THIRTY_DAYS),
        endpoint_id: UUID | None = Query(default=None),
        dataset_id: UUID | None = Query(default=None),
    ) -> TimeSeriesResponse:
        """Get time-bucketed series for query volume, user activity, and revenue."""
        return await handler.get_time_series(
            tenant, time_range, endpoint_id, dataset_id
        )

    @router.get("/top-users", response_model=TopUsersResponse)
    async def get_top_users(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: AnalyticsHandler = Depends(get_handler),
        time_range: TimeRange = Query(default=TimeRange.THIRTY_DAYS),
        endpoint_id: UUID | None = Query(default=None),
        dataset_id: UUID | None = Query(default=None),
    ) -> TopUsersResponse:
        """Get top 5 users ranked by query count."""
        return await handler.get_top_users(tenant, time_range, endpoint_id, dataset_id)

    return router
