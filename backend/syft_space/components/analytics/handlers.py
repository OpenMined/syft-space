"""Analytics handlers for dashboard business logic."""

import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from syft_space.components.analytics.entities import QueryEventStatus
from syft_space.components.analytics.repository import QueryEventRepository
from syft_space.components.analytics.schemas import (
    CurrencyAmount,
    CurrencySeries,
    RevenueStatCard,
    StatCard,
    SummaryStatsResponse,
    TimeRange,
    TimeSeriesPoint,
    TimeSeriesResponse,
    TopUserEntry,
    TopUsersResponse,
    WordCloudEntry,
    WordCloudResponse,
)
from syft_space.components.analytics.text_processing import (
    clean_texts_batch,
    extract_ngrams,
)
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.tenants.entities import Tenant


class BucketGranularity(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# Mapping: time range -> (bucket granularity, SQLite strftime format)
_BUCKET_CONFIG: dict[TimeRange, tuple[BucketGranularity, str]] = {
    TimeRange.SEVEN_DAYS: (BucketGranularity.DAILY, "%Y-%m-%d"),
    TimeRange.THIRTY_DAYS: (BucketGranularity.DAILY, "%Y-%m-%d"),
    TimeRange.NINETY_DAYS: (BucketGranularity.WEEKLY, "%Y-%W"),
    TimeRange.ONE_YEAR: (BucketGranularity.MONTHLY, "%Y-%m"),
}

# Mapping: time range -> timedelta for the period length
_TIME_DELTAS: dict[TimeRange, timedelta] = {
    TimeRange.SEVEN_DAYS: timedelta(days=7),
    TimeRange.THIRTY_DAYS: timedelta(days=30),
    TimeRange.NINETY_DAYS: timedelta(days=90),
    TimeRange.ONE_YEAR: timedelta(days=365),
}


class AnalyticsHandler:
    """Handler for analytics dashboard business logic.

    Orchestrates queries across the analytics database (query_events)
    and the main application database (endpoints).
    """

    def __init__(
        self,
        query_event_repository: QueryEventRepository,
        endpoint_repository: EndpointRepository,
    ):
        self.query_event_repository = query_event_repository
        self.endpoint_repository = endpoint_repository

    # ============== Public Methods ==============

    async def get_summary_stats(
        self,
        tenant: Tenant,
        time_range: TimeRange,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
    ) -> SummaryStatsResponse:
        """Compute all 4 dashboard stat cards."""
        now = datetime.now(timezone.utc)
        current_start, current_end, previous_start, previous_end = (
            self._compute_time_boundaries(time_range, now)
        )

        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        status = QueryEventStatus.SUCCESS.value

        # Run all 5 independent DB queries in parallel
        (
            published_count,
            created_in_range,
            current_counts,
            previous_counts,
            month_counts,
        ) = await asyncio.gather(
            self.endpoint_repository.count_published(tenant.id),
            self.endpoint_repository.count_created_in_range(
                tenant.id, current_start, current_end
            ),
            self.query_event_repository.get_summary_counts(
                tenant.id,
                current_start,
                current_end,
                endpoint_id,
                dataset_id,
                status,
            ),
            self.query_event_repository.get_summary_counts(
                tenant.id,
                previous_start,
                previous_end,
                endpoint_id,
                dataset_id,
                status,
            ),
            self.query_event_repository.get_summary_counts(
                tenant.id,
                month_start,
                now,
                endpoint_id,
                dataset_id,
                status,
            ),
        )

        current_count, current_revenue_breakdown, current_users = current_counts
        previous_count = previous_counts[0]
        month_revenue_breakdown = month_counts[1]

        query_pct_change = self._compute_pct_change(current_count, previous_count)

        return SummaryStatsResponse(
            active_endpoints=StatCard(
                value=float(published_count),
                change_value=float(created_in_range),
                change_label=f"+{created_in_range} this period",
            ),
            total_queries=StatCard(
                value=float(current_count),
                change_value=query_pct_change,
                change_label=f"{query_pct_change:+.1f}% from last period",
            ),
            total_revenue=RevenueStatCard(
                breakdown=[
                    CurrencyAmount(currency=c, amount=a)
                    for c, a in current_revenue_breakdown
                ],
                change_breakdown=[
                    CurrencyAmount(currency=c, amount=a)
                    for c, a in month_revenue_breakdown
                ],
            ),
            active_users=StatCard(
                value=float(current_users),
                change_value=0.0,
                change_label=time_range.value,
            ),
        )

    async def get_time_series(
        self,
        tenant: Tenant,
        time_range: TimeRange,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
    ) -> TimeSeriesResponse:
        """Compute 3 time-bucketed series with gap-filling."""
        now = datetime.now(timezone.utc)
        current_start, current_end, _, _ = self._compute_time_boundaries(
            time_range, now
        )
        granularity, bucket_format = _BUCKET_CONFIG[time_range]

        # Query aggregated data from analytics DB
        counts_data, revenue_data = (
            await self.query_event_repository.get_time_series_data(
                tenant.id,
                current_start,
                current_end,
                bucket_format,
                endpoint_id,
                dataset_id,
                QueryEventStatus.SUCCESS.value,
            )
        )

        # Build lookups
        counts_by_bucket: dict[str, tuple[int, int]] = {
            bucket_key: (query_count, user_count)
            for bucket_key, query_count, user_count in counts_data
        }
        # currency -> bucket_key -> revenue_sum
        revenue_by_currency: dict[str, dict[str, float]] = {}
        for bucket_key, currency, revenue_sum in revenue_data:
            revenue_by_currency.setdefault(currency, {})[bucket_key] = revenue_sum

        # Generate all expected bucket keys and gap-fill
        expected_buckets = self._generate_bucket_keys(
            current_start, current_end, granularity, bucket_format
        )

        query_volume: list[TimeSeriesPoint] = []
        user_activity: list[TimeSeriesPoint] = []
        for bucket_key, label in expected_buckets:
            counts = counts_by_bucket.get(bucket_key, (0, 0))
            query_volume.append(TimeSeriesPoint(label=label, value=float(counts[0])))
            user_activity.append(TimeSeriesPoint(label=label, value=float(counts[1])))

        # One CurrencySeries per currency present in the data, gap-filled
        # against the same x-axis as query_volume.
        revenue: list[CurrencySeries] = []
        for currency in sorted(revenue_by_currency):
            bucket_to_amount = revenue_by_currency[currency]
            points = [
                TimeSeriesPoint(
                    label=label, value=float(bucket_to_amount.get(bucket_key, 0.0))
                )
                for bucket_key, label in expected_buckets
            ]
            revenue.append(CurrencySeries(currency=currency, points=points))

        return TimeSeriesResponse(
            query_volume=query_volume,
            user_activity=user_activity,
            revenue=revenue,
        )

    async def get_top_users(
        self,
        tenant: Tenant,
        time_range: TimeRange,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
    ) -> TopUsersResponse:
        """Get top 5 users by query count."""
        now = datetime.now(timezone.utc)
        current_start, current_end, _, _ = self._compute_time_boundaries(
            time_range, now
        )

        raw_users = await self.query_event_repository.get_top_users(
            tenant.id,
            current_start,
            current_end,
            limit=5,
            endpoint_id=endpoint_id,
            dataset_id=dataset_id,
            status=QueryEventStatus.SUCCESS.value,
        )

        users = [
            TopUserEntry(
                user_email=email,
                query_count=count,
                revenue=[
                    CurrencyAmount(currency=c, amount=a) for c, a in revenue_breakdown
                ],
            )
            for email, count, revenue_breakdown in raw_users
        ]

        return TopUsersResponse(users=users)

    async def get_word_cloud(
        self,
        tenant: Tenant,
        time_range: TimeRange,
        endpoint_id: UUID | None = None,
        dataset_id: UUID | None = None,
        max_words: int = 80,
        ngram_size: int = 1,
        custom_stop_words: list[str] | None = None,
    ) -> WordCloudResponse:
        """Build word frequency data from query texts for cloud rendering.

        Fetches all query texts in the time range, runs NLP cleaning
        (normalization, stop word removal, lemmatization), then extracts
        n-grams and counts frequencies.

        Args:
            ngram_size: Number of words per chunk (1=single, 2=bigram, 3=trigram).
        """
        now = datetime.now(timezone.utc)
        current_start, current_end, _, _ = self._compute_time_boundaries(
            time_range, now
        )

        raw_texts = await self.query_event_repository.get_query_texts(
            tenant.id,
            current_start,
            current_end,
            endpoint_id=endpoint_id,
            dataset_id=dataset_id,
            status=QueryEventStatus.SUCCESS.value,
        )

        # spaCy lemmatization is CPU-bound — off-load so a word-cloud
        # request doesn't block the event loop.
        cleaned_texts = await asyncio.to_thread(
            clean_texts_batch, raw_texts, custom_stop_words=custom_stop_words
        )
        word_counts: Counter[str] = Counter()
        for cleaned in cleaned_texts:
            if cleaned:
                word_counts.update(extract_ngrams(cleaned, n=ngram_size))

        # Build sorted response, capped at max_words
        words = [
            WordCloudEntry(word=word, count=count)
            for word, count in word_counts.most_common(max_words)
        ]

        return WordCloudResponse(words=words)

    # ============== Private Helpers ==============

    @staticmethod
    def _compute_time_boundaries(
        time_range: TimeRange, now: datetime
    ) -> tuple[datetime, datetime, datetime, datetime]:
        """Compute current and previous period boundaries.

        Returns:
            (current_start, current_end, previous_start, previous_end)
        """
        delta = _TIME_DELTAS[time_range]
        current_end = now
        current_start = now - delta
        previous_end = current_start
        previous_start = current_start - delta
        return current_start, current_end, previous_start, previous_end

    @staticmethod
    def _compute_pct_change(current: int, previous: int) -> float:
        """Compute percentage change between two values."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100.0

    @staticmethod
    def _generate_bucket_keys(
        start: datetime,
        end: datetime,
        granularity: BucketGranularity,
        bucket_format: str,
    ) -> list[tuple[str, str]]:
        """Generate all expected bucket (key, label) pairs for gap-filling.

        Returns:
            Ordered list of (bucket_key, human_readable_label) tuples
        """
        buckets: list[tuple[str, str]] = []
        current = start

        if granularity == BucketGranularity.DAILY:
            while current <= end:
                key = current.strftime(bucket_format)
                label = current.strftime("%b %-d")
                buckets.append((key, label))
                current += timedelta(days=1)

        elif granularity == BucketGranularity.WEEKLY:
            # Align to Monday of the starting week
            days_since_monday = current.weekday()
            current = current - timedelta(days=days_since_monday)
            while current <= end:
                key = current.strftime(bucket_format)
                label = f"Week of {current.strftime('%b %-d')}"
                buckets.append((key, label))
                current += timedelta(weeks=1)

        elif granularity == BucketGranularity.MONTHLY:
            # Align to first day of the starting month
            current = current.replace(day=1)
            while current <= end:
                key = current.strftime(bucket_format)
                label = current.strftime("%B %Y")
                buckets.append((key, label))
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

        return buckets
