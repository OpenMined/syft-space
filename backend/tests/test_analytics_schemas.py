"""Tests for analytics schemas — Group 3."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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
)


class TestTimeRange:
    def test_values(self):
        assert TimeRange.SEVEN_DAYS == "7d"
        assert TimeRange.THIRTY_DAYS == "30d"
        assert TimeRange.NINETY_DAYS == "90d"
        assert TimeRange.ONE_YEAR == "1y"

    def test_from_string(self):
        assert TimeRange("7d") is TimeRange.SEVEN_DAYS
        assert TimeRange("1y") is TimeRange.ONE_YEAR

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            TimeRange("2w")


class TestStatCard:
    def test_valid(self):
        card = StatCard(value=42.0, change_value=10.5, change_label="+10.5%")
        assert card.value == 42.0
        assert card.change_value == 10.5
        assert card.change_label == "+10.5%"

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            StatCard(value=1.0)  # missing change_value and change_label


class TestRevenueStatCard:
    def test_valid_with_breakdown(self):
        card = RevenueStatCard(
            breakdown=[
                CurrencyAmount(currency="USD", amount=12.5),
                CurrencyAmount(currency="IDR", amount=50000.0),
            ],
            change_breakdown=[CurrencyAmount(currency="USD", amount=3.0)],
        )
        assert len(card.breakdown) == 2
        assert card.breakdown[0].currency == "USD"
        assert card.breakdown[1].amount == 50000.0
        assert card.change_breakdown[0].amount == 3.0

    def test_empty_breakdowns_allowed(self):
        card = RevenueStatCard(breakdown=[], change_breakdown=[])
        assert card.breakdown == []
        assert card.change_breakdown == []


class TestSummaryStatsResponse:
    def test_full_response(self):
        card = StatCard(value=0.0, change_value=0.0, change_label="--")
        revenue = RevenueStatCard(breakdown=[], change_breakdown=[])
        resp = SummaryStatsResponse(
            active_endpoints=card,
            total_queries=card,
            total_revenue=revenue,
            active_users=card,
        )
        assert resp.active_endpoints.value == 0.0
        assert resp.total_revenue.breakdown == []

    def test_missing_field(self):
        card = StatCard(value=0.0, change_value=0.0, change_label="--")
        with pytest.raises(ValidationError):
            SummaryStatsResponse(
                active_endpoints=card,
                total_queries=card,
                # missing total_revenue, active_users
            )


class TestTimeSeriesPoint:
    def test_valid(self):
        pt = TimeSeriesPoint(label="Jan 1", value=5.0)
        assert pt.label == "Jan 1"
        assert pt.value == 5.0


class TestTimeSeriesResponse:
    def test_full_response(self):
        points = [TimeSeriesPoint(label="Jan 1", value=1.0)]
        resp = TimeSeriesResponse(
            query_volume=points,
            user_activity=points,
            revenue=[CurrencySeries(currency="USD", points=points)],
        )
        assert len(resp.query_volume) == 1
        assert resp.revenue[0].currency == "USD"

    def test_empty_series(self):
        resp = TimeSeriesResponse(
            query_volume=[],
            user_activity=[],
            revenue=[],
        )
        assert resp.query_volume == []
        assert resp.revenue == []


class TestTopUserEntry:
    def test_valid(self):
        entry = TopUserEntry(
            user_email="alice@test.com",
            query_count=100,
            revenue=[CurrencyAmount(currency="USD", amount=50.0)],
        )
        assert entry.user_email == "alice@test.com"
        assert entry.query_count == 100
        assert entry.revenue[0].amount == 50.0

    def test_empty_revenue_allowed(self):
        entry = TopUserEntry(user_email="a@t.com", query_count=1, revenue=[])
        assert entry.revenue == []


class TestTopUsersResponse:
    def test_with_users(self):
        resp = TopUsersResponse(
            users=[
                TopUserEntry(
                    user_email="a@t.com",
                    query_count=10,
                    revenue=[CurrencyAmount(currency="USD", amount=5.0)],
                ),
                TopUserEntry(
                    user_email="b@t.com",
                    query_count=5,
                    revenue=[CurrencyAmount(currency="IDR", amount=2000.0)],
                ),
            ]
        )
        assert len(resp.users) == 2
        assert resp.users[1].revenue[0].currency == "IDR"

    def test_empty(self):
        resp = TopUsersResponse(users=[])
        assert resp.users == []
