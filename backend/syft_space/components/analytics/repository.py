"""Repository for analytics query events and cost lines."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, text
from sqlmodel import select

from syft_space.components.analytics.entities import (
    QueryCostLine,
    QueryEvent,
    QueryEventStatus,
)
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class QueryEventRepository(AsyncBaseRepository[QueryEvent]):
    """Repository for QueryEvent + QueryCostLine CRUD and aggregations.

    Query identity (count, distinct users, query text) lives on QueryEvent.
    Per-currency revenue lives on QueryCostLine — one row per chargeable
    component within a query, supporting multi-currency-per-query.
    """

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, QueryEvent)

    async def create_with_lines(
        self,
        event: QueryEvent,
        lines: list[QueryCostLine],
    ) -> QueryEvent:
        """Persist a QueryEvent and its cost lines in a single transaction."""
        async with self.db.get_session() as session:
            session.add(event)
            for line in lines:
                session.add(line)
            await session.commit()
            await session.refresh(event)
            return event

    def _apply_event_filters(
        self,
        statement,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        endpoint_id: UUID | None,
        dataset_id: UUID | None,
        status: str | None,
    ):
        """Apply filters to a QueryEvent-based statement."""
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

    def _apply_line_filters(
        self,
        statement,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        endpoint_id: UUID | None,
        dataset_id: UUID | None,
        status: str | None,
    ):
        """Apply filters to a QueryCostLine-based statement.

        All filter columns are denormalized onto cost lines so revenue
        aggregations don't need to join QueryEvent.
        """
        statement = statement.where(
            QueryCostLine.tenant_id == tenant_id,
            QueryCostLine.timestamp >= start,
            QueryCostLine.timestamp <= end,
        )
        if endpoint_id is not None:
            statement = statement.where(QueryCostLine.endpoint_id == endpoint_id)
        if dataset_id is not None:
            statement = statement.where(QueryCostLine.dataset_id == dataset_id)
        if status is not None:
            statement = statement.where(QueryCostLine.status == status)
        return statement

    async def get_summary_counts(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        endpoint_id: UUID | None,
        dataset_id: UUID | None,
        status: str | None,
    ) -> tuple[int, list[tuple[str, float]], int]:
        """Get aggregated counts for summary statistics.

        Query count + distinct users come from QueryEvent. Revenue is
        per-currency from QueryCostLine.

        Returns:
            (event_count, [(currency, revenue_sum), ...], distinct_user_count)
        """
        async with self.db.get_session() as session:
            count_stmt = select(
                func.count().label("event_count"),
                func.count(func.distinct(QueryEvent.user_email)).label(
                    "distinct_users"
                ),
            )
            count_stmt = self._apply_event_filters(
                count_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            count_result = await session.exec(count_stmt)
            count_row = count_result.first()
            event_count = int(count_row[0]) if count_row else 0
            distinct_users = int(count_row[1]) if count_row else 0

            revenue_stmt = select(
                QueryCostLine.currency,
                func.sum(QueryCostLine.amount).label("revenue_sum"),
            ).where(QueryCostLine.amount > 0)
            revenue_stmt = self._apply_line_filters(
                revenue_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            revenue_stmt = revenue_stmt.group_by(QueryCostLine.currency)
            revenue_result = await session.exec(revenue_stmt)
            breakdown = [
                (str(row[0]), float(row[1])) for row in revenue_result.all()
            ]

            return (event_count, breakdown, distinct_users)

    async def get_time_series_data(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bucket_format: str,
        endpoint_id: UUID | None,
        dataset_id: UUID | None,
        status: str | None,
    ) -> tuple[list[tuple[str, int, int]], list[tuple[str, str, float]]]:
        """Get time-bucketed aggregations for the dashboard time-series.

        Returns:
            counts: list of (bucket_key, query_count, distinct_users)
            revenue: list of (bucket_key, currency, revenue_sum)
        """
        async with self.db.get_session() as session:
            event_bucket = func.strftime(bucket_format, QueryEvent.timestamp)
            line_bucket = func.strftime(bucket_format, QueryCostLine.timestamp)

            counts_stmt = select(
                event_bucket.label("bucket"),
                func.count().label("query_count"),
                func.count(func.distinct(QueryEvent.user_email)).label(
                    "distinct_users"
                ),
            )
            counts_stmt = self._apply_event_filters(
                counts_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            counts_stmt = counts_stmt.group_by(text("bucket")).order_by(text("bucket"))
            counts_result = await session.exec(counts_stmt)
            counts = [
                (str(row[0]), int(row[1]), int(row[2]))
                for row in counts_result.all()
            ]

            revenue_stmt = select(
                line_bucket.label("bucket"),
                QueryCostLine.currency,
                func.sum(QueryCostLine.amount).label("revenue_sum"),
            ).where(QueryCostLine.amount > 0)
            revenue_stmt = self._apply_line_filters(
                revenue_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            revenue_stmt = revenue_stmt.group_by(
                text("bucket"), QueryCostLine.currency
            ).order_by(text("bucket"))
            revenue_result = await session.exec(revenue_stmt)
            revenue = [
                (str(row[0]), str(row[1]), float(row[2]))
                for row in revenue_result.all()
            ]

            return counts, revenue

    async def get_query_texts(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        endpoint_id: UUID | None,
        dataset_id: UUID | None,
        status: str | None,
    ) -> list[str]:
        """Get all non-empty query texts in a time range."""
        async with self.db.get_session() as session:
            statement = select(QueryEvent.query_text).where(
                QueryEvent.query_text != "",
                QueryEvent.query_text.is_not(None),  # type: ignore[union-attr]
            )
            statement = self._apply_event_filters(
                statement, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            result = await session.exec(statement)
            return [str(row) for row in result.all()]

    async def get_top_users(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        limit: int,
        endpoint_id: UUID | None,
        dataset_id: UUID | None,
        status: str | None,
    ) -> list[tuple[str, int, list[tuple[str, float]]]]:
        """Get top users ranked by query count.

        query_count comes from QueryEvent (currency-agnostic — one row per
        query). Revenue is per-currency from QueryCostLine, joined back to
        the user via the denormalized user_email column.

        Returns:
            [(user_email, query_count, [(currency, revenue_sum), ...])]
        """
        async with self.db.get_session() as session:
            count_stmt = select(
                QueryEvent.user_email,
                func.count().label("query_count"),
            )
            count_stmt = self._apply_event_filters(
                count_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            count_stmt = (
                count_stmt.group_by(QueryEvent.user_email)
                .order_by(text("query_count DESC"))
                .limit(limit)
            )
            count_result = await session.exec(count_stmt)
            top = [(str(row[0]), int(row[1])) for row in count_result.all()]
            if not top:
                return []

            top_emails = [email for email, _ in top]
            revenue_stmt = select(
                QueryCostLine.user_email,
                QueryCostLine.currency,
                func.sum(QueryCostLine.amount).label("revenue_sum"),
            ).where(
                QueryCostLine.amount > 0,
                QueryCostLine.user_email.in_(top_emails),  # type: ignore[union-attr]
            )
            revenue_stmt = self._apply_line_filters(
                revenue_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            revenue_stmt = revenue_stmt.group_by(
                QueryCostLine.user_email, QueryCostLine.currency
            )
            revenue_result = await session.exec(revenue_stmt)
            revenue_by_user: dict[str, list[tuple[str, float]]] = {}
            for row in revenue_result.all():
                revenue_by_user.setdefault(str(row[0]), []).append(
                    (str(row[1]), float(row[2]))
                )

            return [
                (email, count, revenue_by_user.get(email, []))
                for email, count in top
            ]


# Re-export for backward import compatibility (tests, future ports).
__all__ = ["QueryEventRepository", "QueryEvent", "QueryCostLine", "QueryEventStatus"]
