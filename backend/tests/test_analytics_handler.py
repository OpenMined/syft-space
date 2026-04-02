"""Tests for AnalyticsHandler business logic — Group 3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from syft_space.components.analytics.handlers import AnalyticsHandler, BucketGranularity
from syft_space.components.analytics.schemas import TimeRange
from syft_space.components.tenants.entities import Tenant

from .conftest import TENANT_ID


def _make_tenant() -> Tenant:
    return Tenant(
        id=TENANT_ID,
        name="test-tenant",
        display_name="Test Tenant",
        domain="test.example.com",
    )


# ============== get_summary_stats ==============


class TestGetSummaryStats:
    """AnalyticsHandler.get_summary_stats with mocked repositories."""

    async def test_summary_with_data(self):
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        endpoint_repo.count_published.return_value = 5
        endpoint_repo.count_created_in_range.return_value = 2

        # current: 100 queries, $50 revenue, 10 users
        # previous: 80 queries
        # month: $200 revenue
        event_repo.get_summary_counts.side_effect = [
            (100, 50.0, 10),  # current period
            (80, 30.0, 8),  # previous period
            (200, 200.0, 15),  # current month
        ]

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_summary_stats(_make_tenant(), TimeRange.THIRTY_DAYS)

        assert result.active_endpoints.value == 5.0
        assert result.active_endpoints.change_value == 2.0
        assert result.total_queries.value == 100.0
        assert result.total_queries.change_value == 25.0  # (100-80)/80 * 100
        assert result.total_revenue.value == 50.0
        assert result.total_revenue.change_value == 200.0  # month revenue
        assert result.active_users.value == 10.0

    async def test_summary_with_zero_previous(self):
        """Previous period zero → 100% change when current > 0."""
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        endpoint_repo.count_published.return_value = 0
        endpoint_repo.count_created_in_range.return_value = 0
        event_repo.get_summary_counts.side_effect = [
            (50, 0.0, 5),  # current
            (0, 0.0, 0),  # previous (zero)
            (0, 0.0, 0),  # month
        ]

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_summary_stats(_make_tenant(), TimeRange.SEVEN_DAYS)

        assert result.total_queries.change_value == 100.0

    async def test_summary_all_zeros(self):
        """Completely empty data returns zeros."""
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        endpoint_repo.count_published.return_value = 0
        endpoint_repo.count_created_in_range.return_value = 0
        event_repo.get_summary_counts.return_value = (0, 0.0, 0)

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_summary_stats(_make_tenant(), TimeRange.THIRTY_DAYS)

        assert result.total_queries.value == 0.0
        assert result.total_queries.change_value == 0.0

    async def test_summary_passes_filters(self):
        """endpoint_id and dataset_id are forwarded to repo."""
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        endpoint_repo.count_published.return_value = 0
        endpoint_repo.count_created_in_range.return_value = 0
        event_repo.get_summary_counts.return_value = (0, 0.0, 0)

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        ep_id = uuid4()
        ds_id = uuid4()

        await handler.get_summary_stats(
            _make_tenant(), TimeRange.THIRTY_DAYS, endpoint_id=ep_id, dataset_id=ds_id
        )

        # All 3 calls should include the filter IDs
        for call in event_repo.get_summary_counts.call_args_list:
            assert call.args[3] == ep_id  # endpoint_id
            assert call.args[4] == ds_id  # dataset_id


# ============== get_time_series ==============


class TestGetTimeSeries:
    """AnalyticsHandler.get_time_series gap-filling logic."""

    async def test_gap_fills_missing_buckets(self):
        """Days with no data should be filled with zeros."""
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        # Return data for only 1 bucket
        event_repo.get_time_series_data.return_value = [
            ("2024-01-03", 5, 2, 10.0),
        ]

        handler = AnalyticsHandler(event_repo, endpoint_repo)

        # Freeze time to a known date for predictable buckets
        fixed_now = datetime(2024, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
        with patch("syft_space.components.analytics.handlers.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = await handler.get_time_series(_make_tenant(), TimeRange.SEVEN_DAYS)

        # Should have multiple points (7-8 days), most zero-filled
        assert len(result.query_volume) > 1
        # The bucket for 2024-01-03 should have data
        values = {p.label: p.value for p in result.query_volume}
        non_zero = [v for v in values.values() if v > 0]
        assert len(non_zero) >= 1

    async def test_empty_data_returns_all_zero_buckets(self):
        """No data returns series of zero-valued points."""
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()
        event_repo.get_time_series_data.return_value = []

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_time_series(_make_tenant(), TimeRange.SEVEN_DAYS)

        assert len(result.query_volume) > 0
        assert all(p.value == 0.0 for p in result.query_volume)
        assert all(p.value == 0.0 for p in result.user_activity)
        assert all(p.value == 0.0 for p in result.revenue)

    async def test_three_series_aligned(self):
        """All three series have the same bucket labels."""
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()
        event_repo.get_time_series_data.return_value = []

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_time_series(_make_tenant(), TimeRange.THIRTY_DAYS)

        qv_labels = [p.label for p in result.query_volume]
        ua_labels = [p.label for p in result.user_activity]
        rev_labels = [p.label for p in result.revenue]
        assert qv_labels == ua_labels == rev_labels


# ============== get_top_users ==============


class TestGetTopUsers:
    """AnalyticsHandler.get_top_users."""

    async def test_transforms_raw_data(self):
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        event_repo.get_top_users.return_value = [
            ("alice@test.com", 50, 100.0),
            ("bob@test.com", 30, 50.0),
        ]

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_top_users(_make_tenant(), TimeRange.THIRTY_DAYS)

        assert len(result.users) == 2
        assert result.users[0].user_email == "alice@test.com"
        assert result.users[0].query_count == 50
        assert result.users[0].revenue == 100.0
        assert result.users[1].user_email == "bob@test.com"

    async def test_empty_returns_empty(self):
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()
        event_repo.get_top_users.return_value = []

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_top_users(_make_tenant(), TimeRange.SEVEN_DAYS)

        assert result.users == []


# ============== Private helpers ==============


class TestComputePctChange:
    def test_positive_change(self):
        assert AnalyticsHandler._compute_pct_change(150, 100) == 50.0

    def test_negative_change(self):
        assert AnalyticsHandler._compute_pct_change(80, 100) == -20.0

    def test_zero_previous_with_current(self):
        assert AnalyticsHandler._compute_pct_change(50, 0) == 100.0

    def test_zero_both(self):
        assert AnalyticsHandler._compute_pct_change(0, 0) == 0.0

    def test_no_change(self):
        assert AnalyticsHandler._compute_pct_change(100, 100) == 0.0


class TestComputeTimeBoundaries:
    def test_thirty_day_boundaries(self):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        c_start, c_end, p_start, p_end = AnalyticsHandler._compute_time_boundaries(
            TimeRange.THIRTY_DAYS, now
        )

        assert c_end == now
        assert c_start == now - timedelta(days=30)
        assert p_end == c_start
        assert p_start == c_start - timedelta(days=30)

    def test_seven_day_boundaries(self):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        c_start, c_end, p_start, p_end = AnalyticsHandler._compute_time_boundaries(
            TimeRange.SEVEN_DAYS, now
        )

        assert (c_end - c_start).days == 7
        assert (p_end - p_start).days == 7


class TestGenerateBucketKeys:
    def test_daily_7_days(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 7, tzinfo=timezone.utc)

        buckets = AnalyticsHandler._generate_bucket_keys(
            start, end, BucketGranularity.DAILY, "%Y-%m-%d"
        )

        assert len(buckets) == 7
        assert buckets[0][0] == "2024-01-01"
        assert buckets[-1][0] == "2024-01-07"

    def test_monthly_spanning_year(self):
        start = datetime(2023, 11, 1, tzinfo=timezone.utc)
        end = datetime(2024, 2, 15, tzinfo=timezone.utc)

        buckets = AnalyticsHandler._generate_bucket_keys(
            start, end, BucketGranularity.MONTHLY, "%Y-%m"
        )

        keys = [b[0] for b in buckets]
        assert "2023-11" in keys
        assert "2023-12" in keys
        assert "2024-01" in keys
        assert "2024-02" in keys

    def test_weekly_aligns_to_monday(self):
        # 2024-01-03 is a Wednesday
        start = datetime(2024, 1, 3, tzinfo=timezone.utc)
        end = datetime(2024, 1, 20, tzinfo=timezone.utc)

        buckets = AnalyticsHandler._generate_bucket_keys(
            start, end, BucketGranularity.WEEKLY, "%Y-%W"
        )

        # Should start from Monday of the week containing Jan 3
        assert len(buckets) >= 2
        for _, label in buckets:
            assert "Week of" in label
