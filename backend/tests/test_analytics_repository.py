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
        assert revenue == 0.0
        assert users == 0

    async def test_counts_events_in_range(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        ep_id = uuid4()

        # 3 events in range, 1 outside
        for i in range(3):
            await event_repository.create(
                make_event(
                    endpoint_id=ep_id,
                    user_email=f"user{i}@test.com",
                    revenue_amount=10.0,
                    timestamp=now - timedelta(hours=i + 1),
                )
            )
        await event_repository.create(
            make_event(
                endpoint_id=ep_id,
                user_email="old@test.com",
                revenue_amount=5.0,
                timestamp=now - timedelta(days=30),
            )
        )

        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(days=7), now
        )
        assert count == 3
        assert revenue == 30.0
        assert users == 3

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
        assert revenue == 10.0

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

        await event_repository.create(make_event(revenue_amount=10.0, timestamp=day1))
        await event_repository.create(make_event(revenue_amount=5.0, timestamp=day1))
        await event_repository.create(make_event(revenue_amount=20.0, timestamp=day2))

        rows = await event_repository.get_time_series_data(
            TENANT_ID,
            day2 - timedelta(hours=1),
            day1 + timedelta(hours=1),
            "%Y-%m-%d",
        )

        assert len(rows) == 2
        # Rows are ordered by bucket
        bucket_keys = [r[0] for r in rows]
        assert bucket_keys == sorted(bucket_keys)

        # Day2 has 1 event / $20, Day1 has 2 events / $15
        by_key = {r[0]: r for r in rows}
        day2_key = day2.strftime("%Y-%m-%d")
        day1_key = day1.strftime("%Y-%m-%d")
        assert by_key[day2_key][1] == 1  # query_count
        assert by_key[day2_key][3] == 20.0  # revenue
        assert by_key[day1_key][1] == 2
        assert by_key[day1_key][3] == 15.0

    async def test_empty_returns_empty_list(
        self, event_repository: QueryEventRepository
    ):
        now = datetime.now(timezone.utc)
        rows = await event_repository.get_time_series_data(
            TENANT_ID, now - timedelta(days=7), now, "%Y-%m-%d"
        )
        assert rows == []


class TestGetTopUsers:
    """QueryEventRepository.get_top_users ranking."""

    async def test_ranks_by_query_count(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        # alice: 3 queries, bob: 1 query
        for _ in range(3):
            await event_repository.create(
                make_event(
                    user_email="alice@test.com", revenue_amount=1.0, timestamp=now
                )
            )
        await event_repository.create(
            make_event(user_email="bob@test.com", revenue_amount=100.0, timestamp=now)
        )

        users = await event_repository.get_top_users(
            TENANT_ID, now - timedelta(days=1), now, limit=10
        )

        assert len(users) == 2
        assert users[0][0] == "alice@test.com"
        assert users[0][1] == 3  # query_count
        assert users[1][0] == "bob@test.com"

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
