"""Tests for analytics QueryEventRepository and endpoint count methods — Group 3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from syft_space.components.analytics.entities import QueryEventStatus
from syft_space.components.analytics.repository import QueryEventRepository
from syft_space.components.endpoints.repository import EndpointRepository

from .conftest import TENANT_ID, make_endpoint, make_event

# ============== QueryEventRepository ==============


class TestGetSummaryCounts:
    """QueryEventRepository.get_summary_counts aggregation."""

    async def test_empty_returns_zeros(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(days=7), now
        )
        assert count == 0
        assert revenue == []
        assert users == 0

    async def test_counts_events_in_range(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        ep_id = uuid4()

        # 3 events in range (USD), 1 outside the window, 2 IDR events
        for i in range(3):
            await event_repository.create(
                make_event(
                    endpoint_id=ep_id,
                    user_email=f"user{i}@test.com",
                    revenue_amount=10.0,
                    currency="USD",
                    timestamp=now - timedelta(hours=i + 1),
                )
            )
        await event_repository.create(
            make_event(
                endpoint_id=ep_id,
                user_email="old@test.com",
                revenue_amount=5.0,
                currency="USD",
                timestamp=now - timedelta(days=30),  # outside window
            )
        )
        for amt in (1000.0, 2500.0):
            await event_repository.create(
                make_event(
                    endpoint_id=ep_id,
                    user_email="ionesio@openmined.org",
                    revenue_amount=amt,
                    currency="IDR",
                    timestamp=now - timedelta(hours=2),
                )
            )

        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(days=7), now
        )
        assert count == 5
        # Per-currency breakdown — USD: 30, IDR: 3500. Order is not guaranteed.
        assert dict(revenue) == {"USD": 30.0, "IDR": 3500.0}
        assert users == 4  # 3 user{i} + ionesio

    async def test_filters_by_endpoint_id(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        target_ep = uuid4()
        other_ep = uuid4()

        await event_repository.create(
            make_event(endpoint_id=target_ep, revenue_amount=10.0, timestamp=now)
        )
        await event_repository.create(
            make_event(endpoint_id=other_ep, revenue_amount=20.0, timestamp=now)
        )

        count, revenue, _ = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(days=1), now, endpoint_id=target_ep
        )
        assert count == 1
        assert dict(revenue) == {"USD": 10.0}

    async def test_filters_by_dataset_id(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        ds_id = uuid4()

        await event_repository.create(make_event(dataset_id=ds_id, timestamp=now))
        await event_repository.create(make_event(dataset_id=uuid4(), timestamp=now))

        count, _, _ = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(days=1), now, dataset_id=ds_id
        )
        assert count == 1

    async def test_filters_by_status(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        await event_repository.create(
            make_event(status=QueryEventStatus.SUCCESS.value, timestamp=now)
        )
        await event_repository.create(
            make_event(status=QueryEventStatus.INTERNAL_ERROR.value, timestamp=now)
        )

        count, _, _ = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            status=QueryEventStatus.SUCCESS.value,
        )
        assert count == 1

    async def test_distinct_user_count(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        # Same user, 3 events
        for _ in range(3):
            await event_repository.create(
                make_event(user_email="same@test.com", timestamp=now)
            )

        count, _, users = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(days=1), now
        )
        assert count == 3
        assert users == 1


class TestGetTimeSeriesData:
    """QueryEventRepository.get_time_series_data bucketed aggregation."""

    async def test_daily_buckets(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        # Events on two different days
        day1 = now.replace(hour=12, minute=0, second=0, microsecond=0)
        day2 = day1 - timedelta(days=1)

        # Day1: 2 USD events (10 + 5) + 1 IDR event (1000)
        # Day2: 1 USD event (20)
        await event_repository.create(
            make_event(revenue_amount=10.0, currency="USD", timestamp=day1)
        )
        await event_repository.create(
            make_event(revenue_amount=5.0, currency="USD", timestamp=day1)
        )
        await event_repository.create(
            make_event(revenue_amount=1000.0, currency="IDR", timestamp=day1)
        )
        await event_repository.create(
            make_event(revenue_amount=20.0, currency="USD", timestamp=day2)
        )

        counts, revenue = await event_repository.get_time_series_data(
            TENANT_ID,
            day2 - timedelta(hours=1),
            day1 + timedelta(hours=1),
            "%Y-%m-%d",
        )

        # Counts: 2 buckets, ordered ascending. Day2 has 1 query, Day1 has 3.
        # All events use make_event's default user_email so distinct_users is 1
        # for every bucket here.
        assert len(counts) == 2
        counts_by_key = {bucket: (qc, du) for bucket, qc, du in counts}
        day1_key = day1.strftime("%Y-%m-%d")
        day2_key = day2.strftime("%Y-%m-%d")
        assert counts_by_key[day2_key] == (1, 1)
        assert counts_by_key[day1_key] == (3, 1)

        # Revenue rows: 3 entries — (day1, USD, 15) (day1, IDR, 1000) (day2, USD, 20)
        revenue_by_key = {(bucket, currency): amt for bucket, currency, amt in revenue}
        assert revenue_by_key == {
            (day1_key, "USD"): 15.0,
            (day1_key, "IDR"): 1000.0,
            (day2_key, "USD"): 20.0,
        }

    async def test_empty_returns_empty_lists(
        self, event_repository: QueryEventRepository
    ):
        now = datetime.now(timezone.utc)
        counts, revenue = await event_repository.get_time_series_data(
            TENANT_ID, now - timedelta(days=7), now, "%Y-%m-%d"
        )
        assert counts == []
        assert revenue == []


class TestGetTopUsers:
    """QueryEventRepository.get_top_users ranking."""

    async def test_ranks_by_query_count(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        # alice: 3 USD queries; bob: 1 IDR query at 100k
        for _ in range(3):
            await event_repository.create(
                make_event(
                    user_email="alice@test.com",
                    revenue_amount=1.0,
                    currency="USD",
                    timestamp=now,
                )
            )
        await event_repository.create(
            make_event(
                user_email="bob@test.com",
                revenue_amount=100000.0,
                currency="IDR",
                timestamp=now,
            )
        )

        users = await event_repository.get_top_users(
            TENANT_ID, now - timedelta(days=1), now, limit=10
        )

        assert len(users) == 2
        assert users[0][0] == "alice@test.com"
        assert users[0][1] == 3  # query_count
        assert dict(users[0][2]) == {"USD": 3.0}
        assert users[1][0] == "bob@test.com"
        assert users[1][1] == 1
        assert dict(users[1][2]) == {"IDR": 100000.0}

    async def test_limit_constrains_results(
        self, event_repository: QueryEventRepository
    ):
        now = datetime.now(timezone.utc)

        for i in range(5):
            await event_repository.create(
                make_event(user_email=f"user{i}@test.com", timestamp=now)
            )

        users = await event_repository.get_top_users(
            TENANT_ID, now - timedelta(days=1), now, limit=3
        )
        assert len(users) == 3

    async def test_empty_returns_empty(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        users = await event_repository.get_top_users(
            TENANT_ID, now - timedelta(days=1), now
        )
        assert users == []


# ============== EndpointRepository count methods ==============


class TestEndpointCountPublished:
    """EndpointRepository.count_published."""

    async def test_counts_only_published(
        self, endpoint_repository: EndpointRepository, tenant: object
    ):
        await endpoint_repository.create(make_endpoint(published=True, slug="pub1"))
        await endpoint_repository.create(make_endpoint(published=True, slug="pub2"))
        await endpoint_repository.create(make_endpoint(published=False, slug="draft"))

        count = await endpoint_repository.count_published(TENANT_ID)
        assert count == 2

    async def test_empty_returns_zero(
        self, endpoint_repository: EndpointRepository, tenant: object
    ):
        count = await endpoint_repository.count_published(TENANT_ID)
        assert count == 0

    async def test_isolates_by_tenant(
        self, endpoint_repository: EndpointRepository, tenant: object
    ):
        other_tenant = uuid4()
        await endpoint_repository.create(make_endpoint(published=True, slug="mine"))
        await endpoint_repository.create(
            make_endpoint(published=True, slug="theirs", tenant_id=other_tenant)
        )

        count = await endpoint_repository.count_published(TENANT_ID)
        assert count == 1


class TestEndpointCountCreatedInRange:
    """EndpointRepository.count_created_in_range."""

    async def test_counts_in_range(
        self, endpoint_repository: EndpointRepository, tenant: object
    ):
        now = datetime.now(timezone.utc)

        await endpoint_repository.create(
            make_endpoint(slug="new1", created_at=now - timedelta(hours=1))
        )
        await endpoint_repository.create(
            make_endpoint(slug="new2", created_at=now - timedelta(hours=2))
        )
        await endpoint_repository.create(
            make_endpoint(slug="old", created_at=now - timedelta(days=30))
        )

        count = await endpoint_repository.count_created_in_range(
            TENANT_ID, now - timedelta(days=7), now
        )
        assert count == 2

    async def test_empty_returns_zero(
        self, endpoint_repository: EndpointRepository, tenant: object
    ):
        now = datetime.now(timezone.utc)
        count = await endpoint_repository.count_created_in_range(
            TENANT_ID, now - timedelta(days=7), now
        )
        assert count == 0
