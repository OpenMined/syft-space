"""Tests for QueryEventCollector — Group 3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from syft_space.components.analytics.collector import QueryEventCollector
from syft_space.components.analytics.entities import QueryEventStatus
from syft_space.components.analytics.repository import QueryEventRepository
from syft_space.components.shared.database import AsyncDatabase

from .conftest import TENANT_ID


class TestQueryEventCollector:
    """Fire-and-forget event capture."""

    async def test_capture_persists_event_with_cost_lines(
        self, event_repository: QueryEventRepository, analytics_db: AsyncDatabase
    ):
        """capture() persists a query event and its cost lines."""
        collector = QueryEventCollector(event_repository)
        ep_id = uuid4()

        await collector.capture(
            tenant_id=TENANT_ID,
            endpoint_id=ep_id,
            endpoint_slug="test-slug",
            dataset_id=None,
            user_email="alice@test.com",
            status=QueryEventStatus.SUCCESS.value,
            cost_lines=[("summary", 1.50, "USD")],
        )

        now = datetime.now(timezone.utc)
        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(minutes=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=QueryEventStatus.SUCCESS.value,
        )
        assert count == 1
        assert dict(revenue) == {"USD": 1.50}
        assert users == 1

    async def test_capture_no_cost_lines_records_event_only(
        self, event_repository: QueryEventRepository
    ):
        """An event with no charges still records the query (free tier)."""
        collector = QueryEventCollector(event_repository)

        await collector.capture(
            tenant_id=TENANT_ID,
            endpoint_id=uuid4(),
            endpoint_slug="free-slug",
            dataset_id=None,
            user_email="bob@test.com",
            status=QueryEventStatus.SUCCESS.value,
        )

        now = datetime.now(timezone.utc)
        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(minutes=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=QueryEventStatus.SUCCESS.value,
        )
        assert count == 1
        assert revenue == []
        assert users == 1

    async def test_capture_swallows_exceptions(self):
        """Exceptions in capture are logged, not raised."""
        mock_repo = AsyncMock(spec=QueryEventRepository)
        mock_repo.create_with_lines.side_effect = RuntimeError("DB down")

        collector = QueryEventCollector(mock_repo)

        with patch("syft_space.components.analytics.collector.logger") as mock_logger:
            await collector.capture(
                tenant_id=TENANT_ID,
                endpoint_id=uuid4(),
                endpoint_slug="test",
                dataset_id=None,
                user_email="user@test.com",
                status=QueryEventStatus.SUCCESS.value,
            )

            mock_logger.error.assert_called_once()
            assert "Failed to capture" in str(mock_logger.error.call_args)

    async def test_capture_records_error_status(
        self, event_repository: QueryEventRepository
    ):
        """capture() correctly stores non-success statuses."""
        collector = QueryEventCollector(event_repository)

        await collector.capture(
            tenant_id=TENANT_ID,
            endpoint_id=None,
            endpoint_slug="missing",
            dataset_id=None,
            user_email="user@test.com",
            status=QueryEventStatus.NOT_FOUND.value,
        )

        now = datetime.now(timezone.utc)
        count, _, _ = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(minutes=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=None,
        )
        assert count == 1

        count_success, _, _ = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(minutes=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=QueryEventStatus.SUCCESS.value,
        )
        assert count_success == 0
