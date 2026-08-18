"""Tests for analytics QueryEventRepository and endpoint count methods — Group 3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from syft_space.components.analytics.entities import QueryEventStatus
from syft_space.components.analytics.repository import QueryEventRepository
from syft_space.components.endpoints.repository import EndpointRepository

from .conftest import TENANT_ID, make_cost_line, make_endpoint, make_event

SUCCESS = QueryEventStatus.SUCCESS.value


async def _create(repo: QueryEventRepository, event, lines=()):
    """Convenience: persist an event and any cost lines through the repo."""
    return await repo.create_with_lines(event, list(lines))


# ============== QueryEventRepository ==============


class TestGetSummaryCounts:
    """QueryEventRepository.get_summary_counts aggregation."""

    async def test_empty_returns_zeros(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(days=7),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
        )
        assert count == 0
        assert revenue == []
        assert users == 0

    async def test_counts_events_in_range(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        ep_id = uuid4()

        for i in range(3):
            ev = make_event(
                endpoint_id=ep_id,
                user_email=f"user{i}@test.com",
                timestamp=now - timedelta(hours=i + 1),
            )
            await _create(
                event_repository,
                ev,
                [make_cost_line(ev, amount=10.0, currency="USD")],
            )
        old = make_event(
            endpoint_id=ep_id,
            user_email="old@test.com",
            timestamp=now - timedelta(days=30),  # outside window
        )
        await _create(
            event_repository, old, [make_cost_line(old, amount=5.0, currency="USD")]
        )
        for amt in (1000.0, 2500.0):
            ev = make_event(
                endpoint_id=ep_id,
                user_email="ionesio@openmined.org",
                timestamp=now - timedelta(hours=2),
            )
            await _create(
                event_repository,
                ev,
                [make_cost_line(ev, amount=amt, currency="IDR")],
            )

        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(days=7),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
        )
        assert count == 5
        assert dict(revenue) == {"USD": 30.0, "IDR": 3500.0}
        assert users == 4

    async def test_filters_by_endpoint_id(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        target_ep = uuid4()
        other_ep = uuid4()

        ev1 = make_event(endpoint_id=target_ep, timestamp=now)
        await _create(event_repository, ev1, [make_cost_line(ev1, amount=10.0)])
        ev2 = make_event(endpoint_id=other_ep, timestamp=now)
        await _create(event_repository, ev2, [make_cost_line(ev2, amount=20.0)])

        count, revenue, _ = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            endpoint_id=target_ep,
            dataset_id=None,
            status=SUCCESS,
        )
        assert count == 1
        assert dict(revenue) == {"USD": 10.0}

    async def test_filters_by_dataset_id(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        ds_id = uuid4()

        await _create(event_repository, make_event(dataset_id=ds_id, timestamp=now))
        await _create(event_repository, make_event(dataset_id=uuid4(), timestamp=now))

        count, _, _ = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            endpoint_id=None,
            dataset_id=ds_id,
            status=SUCCESS,
        )
        assert count == 1

    async def test_filters_by_status(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        await _create(
            event_repository,
            make_event(status=QueryEventStatus.SUCCESS.value, timestamp=now),
        )
        await _create(
            event_repository,
            make_event(status=QueryEventStatus.INTERNAL_ERROR.value, timestamp=now),
        )

        count, _, _ = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=QueryEventStatus.SUCCESS.value,
        )
        assert count == 1

    async def test_distinct_user_count(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        for _ in range(3):
            await _create(
                event_repository,
                make_event(user_email="same@test.com", timestamp=now),
            )

        count, _, users = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
        )
        assert count == 3
        assert users == 1


class TestGetTimeSeriesData:
    """QueryEventRepository.get_time_series_data bucketed aggregation."""

    async def test_daily_buckets(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        day1 = now.replace(hour=12, minute=0, second=0, microsecond=0)
        day2 = day1 - timedelta(days=1)

        # Day1: 2 USD lines (10 + 5) + 1 IDR line (1000)
        # Day2: 1 USD line (20)
        ev = make_event(timestamp=day1)
        await _create(
            event_repository, ev, [make_cost_line(ev, amount=10.0, currency="USD")]
        )
        ev = make_event(timestamp=day1)
        await _create(
            event_repository, ev, [make_cost_line(ev, amount=5.0, currency="USD")]
        )
        ev = make_event(timestamp=day1)
        await _create(
            event_repository, ev, [make_cost_line(ev, amount=1000.0, currency="IDR")]
        )
        ev = make_event(timestamp=day2)
        await _create(
            event_repository, ev, [make_cost_line(ev, amount=20.0, currency="USD")]
        )

        counts, revenue = await event_repository.get_time_series_data(
            TENANT_ID,
            day2 - timedelta(hours=1),
            day1 + timedelta(hours=1),
            "%Y-%m-%d",
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
        )

        assert len(counts) == 2
        counts_by_key = {bucket: (qc, du) for bucket, qc, du in counts}
        day1_key = day1.strftime("%Y-%m-%d")
        day2_key = day2.strftime("%Y-%m-%d")
        assert counts_by_key[day2_key] == (1, 1)
        assert counts_by_key[day1_key] == (3, 1)

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
            TENANT_ID,
            now - timedelta(days=7),
            now,
            "%Y-%m-%d",
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
        )
        assert counts == []
        assert revenue == []


class TestGetTopUsers:
    """QueryEventRepository.get_top_users ranking."""

    async def test_ranks_by_query_count(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)

        for _ in range(3):
            ev = make_event(user_email="alice@test.com", timestamp=now)
            await _create(
                event_repository,
                ev,
                [make_cost_line(ev, amount=1.0, currency="USD")],
            )
        ev = make_event(user_email="bob@test.com", timestamp=now)
        await _create(
            event_repository,
            ev,
            [make_cost_line(ev, amount=100000.0, currency="IDR")],
        )

        users = await event_repository.get_top_users(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            limit=10,
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
        )

        assert len(users) == 2
        assert users[0][0] == "alice@test.com"
        assert users[0][1] == 3
        assert dict(users[0][2]) == {"USD": 3.0}
        assert users[1][0] == "bob@test.com"
        assert users[1][1] == 1
        assert dict(users[1][2]) == {"IDR": 100000.0}

    async def test_limit_constrains_results(
        self, event_repository: QueryEventRepository
    ):
        now = datetime.now(timezone.utc)

        for i in range(5):
            await _create(
                event_repository,
                make_event(user_email=f"user{i}@test.com", timestamp=now),
            )

        users = await event_repository.get_top_users(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            limit=3,
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
        )
        assert len(users) == 3

    async def test_empty_returns_empty(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        users = await event_repository.get_top_users(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            limit=5,
            endpoint_id=None,
            dataset_id=None,
            status=SUCCESS,
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
