"""Repository for analytics query events."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, text
from sqlmodel import select

from syft_space.components.analytics.entities import QueryEvent, QueryEventStatus
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class QueryEventRepository(AsyncBaseRepository[QueryEvent]):
    """Repository for QueryEvent CRUD and aggregation operations."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, QueryEvent)

    def _apply_filters(
        self,
        statement,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        status: str | None = QueryEventStatus.SUCCESS.value,
    ):
        """Apply common filters to a query statement."""
        statement = statement.where(
            QueryEvent.tenant_id == tenant_id,
            QueryEvent.timestamp >= start,
            QueryEvent.timestamp <= end,
        )
        if endpoint_id is not None:
            statement = statement.where(QueryEvent.endpoint_id == endpoint_id)
        if dataset_id is not None:
            statement = statement.where(QueryEvent.dataset_id == dataset_id)
        if status is not None:
            statement = statement.where(QueryEvent.status == status)
        return statement

    async def get_summary_counts(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        status: str | None = QueryEventStatus.SUCCESS.value,
    ) -> tuple[int, float, int]:
        """Get aggregated counts for summary statistics.

        Returns:
            Tuple of (event_count, revenue_sum, distinct_user_count)
        """
        async with self.db.get_session() as session:
            statement = select(
                func.count().label("event_count"),
                func.coalesce(func.sum(QueryEvent.revenue_amount), 0.0).label(
                    "revenue_sum"
                ),
                func.count(func.distinct(QueryEvent.user_email)).label(
                    "distinct_users"
                ),
            )
            statement = self._apply_filters(
                statement, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            result = await session.exec(statement)
            row = result.first()
            if row is None:
                return (0, 0.0, 0)
            return (int(row[0]), float(row[1]), int(row[2]))

    async def get_time_series_data(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bucket_format: str,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        status: str | None = QueryEventStatus.SUCCESS.value,
    ) -> list[tuple[str, int, int, float]]:
        """Get time-bucketed aggregation for all 3 series.

        Args:
            bucket_format: SQLite strftime format (e.g., '%Y-%m-%d' for daily)

        Returns:
            List of (bucket_key, query_count, distinct_users, revenue_sum)
        """
        async with self.db.get_session() as session:
            bucket_expr = func.strftime(bucket_format, QueryEvent.timestamp)
            statement = select(
                bucket_expr.label("bucket"),
                func.count().label("query_count"),
                func.count(func.distinct(QueryEvent.user_email)).label(
                    "distinct_users"
                ),
                func.coalesce(func.sum(QueryEvent.revenue_amount), 0.0).label(
                    "revenue_sum"
                ),
            )
            statement = self._apply_filters(
                statement, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            statement = statement.group_by(text("bucket")).order_by(text("bucket"))
            result = await session.exec(statement)
            return [
                (str(row[0]), int(row[1]), int(row[2]), float(row[3]))
                for row in result.all()
            ]

    async def get_top_users(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        limit: int = 5,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        status: str | None = QueryEventStatus.SUCCESS.value,
    ) -> list[tuple[str, int, float]]:
        """Get top users ranked by query count.

        Returns:
            List of (user_email, query_count, revenue_sum)
        """
        async with self.db.get_session() as session:
            statement = select(
                QueryEvent.user_email,
                func.count().label("query_count"),
                func.coalesce(func.sum(QueryEvent.revenue_amount), 0.0).label(
                    "revenue_sum"
                ),
            )
            statement = self._apply_filters(
                statement, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            statement = (
                statement.group_by(QueryEvent.user_email)
                .order_by(text("query_count DESC"))
                .limit(limit)
            )
            result = await session.exec(statement)
            return [(str(row[0]), int(row[1]), float(row[2])) for row in result.all()]
