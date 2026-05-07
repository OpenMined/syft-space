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
    ) -> tuple[int, list[tuple[str, float]], int]:
        """Get aggregated counts for summary statistics.

        Revenue is grouped by currency because Syft Space supports multiple
        wallet types (xendit/IDR, mpp/USD) and a cross-currency sum is not
        meaningful. Currencies with zero net revenue are omitted.

        Returns:
            Tuple of (event_count, [(currency, revenue_sum), ...], distinct_user_count)
        """
        async with self.db.get_session() as session:
            count_stmt = select(
                func.count().label("event_count"),
                func.count(func.distinct(QueryEvent.user_email)).label(
                    "distinct_users"
                ),
            )
            count_stmt = self._apply_filters(
                count_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            count_result = await session.exec(count_stmt)
            count_row = count_result.first()
            event_count = int(count_row[0]) if count_row else 0
            distinct_users = int(count_row[1]) if count_row else 0

            revenue_stmt = select(
                QueryEvent.currency,
                func.sum(QueryEvent.revenue_amount).label("revenue_sum"),
            ).where(QueryEvent.revenue_amount > 0)
            revenue_stmt = self._apply_filters(
                revenue_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            revenue_stmt = revenue_stmt.group_by(QueryEvent.currency)
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
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        status: str | None = QueryEventStatus.SUCCESS.value,
    ) -> tuple[list[tuple[str, int, int]], list[tuple[str, str, float]]]:
        """Get time-bucketed aggregations for the dashboard time-series.

        Returns two parallel datasets:
        - per-bucket counts (currency-agnostic): query_count and distinct users
        - per-(bucket, currency) revenue sums

        Args:
            bucket_format: SQLite strftime format (e.g., '%Y-%m-%d' for daily)

        Returns:
            Tuple of:
              - counts: list of (bucket_key, query_count, distinct_users)
              - revenue: list of (bucket_key, currency, revenue_sum)
        """
        async with self.db.get_session() as session:
            bucket_expr = func.strftime(bucket_format, QueryEvent.timestamp)

            counts_stmt = select(
                bucket_expr.label("bucket"),
                func.count().label("query_count"),
                func.count(func.distinct(QueryEvent.user_email)).label(
                    "distinct_users"
                ),
            )
            counts_stmt = self._apply_filters(
                counts_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            counts_stmt = counts_stmt.group_by(text("bucket")).order_by(text("bucket"))
            counts_result = await session.exec(counts_stmt)
            counts = [
                (str(row[0]), int(row[1]), int(row[2]))
                for row in counts_result.all()
            ]

            revenue_stmt = select(
                bucket_expr.label("bucket"),
                QueryEvent.currency,
                func.sum(QueryEvent.revenue_amount).label("revenue_sum"),
            ).where(QueryEvent.revenue_amount > 0)
            revenue_stmt = self._apply_filters(
                revenue_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            revenue_stmt = revenue_stmt.group_by(
                text("bucket"), QueryEvent.currency
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
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        status: str | None = QueryEventStatus.SUCCESS.value,
    ) -> list[str]:
        """Get all non-empty query texts in a time range.

        Returns:
            List of raw query text strings.
        """
        async with self.db.get_session() as session:
            statement = select(QueryEvent.query_text).where(
                QueryEvent.query_text != "",
                QueryEvent.query_text.is_not(None),  # type: ignore[union-attr]
            )
            statement = self._apply_filters(
                statement, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            result = await session.exec(statement)
            return [str(row) for row in result.all()]

    async def get_top_users(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        limit: int = 5,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        status: str | None = QueryEventStatus.SUCCESS.value,
    ) -> list[tuple[str, int, list[tuple[str, float]]]]:
        """Get top users ranked by query count.

        Revenue is per-currency because Syft Space supports multi-currency
        wallets. The query_count is currency-agnostic (one row per query).

        Returns:
            List of (user_email, query_count, [(currency, revenue_sum), ...])
        """
        async with self.db.get_session() as session:
            count_stmt = select(
                QueryEvent.user_email,
                func.count().label("query_count"),
            )
            count_stmt = self._apply_filters(
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
                QueryEvent.user_email,
                QueryEvent.currency,
                func.sum(QueryEvent.revenue_amount).label("revenue_sum"),
            ).where(
                QueryEvent.revenue_amount > 0,
                QueryEvent.user_email.in_(top_emails),  # type: ignore[union-attr]
            )
            revenue_stmt = self._apply_filters(
                revenue_stmt, tenant_id, start, end, endpoint_id, dataset_id, status
            )
            revenue_stmt = revenue_stmt.group_by(
                QueryEvent.user_email, QueryEvent.currency
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
