"""Tests for QueryEventCollector — Group 3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from syft_space.components.analytics.collector import QueryEventCollector
from syft_space.components.analytics.entities import QueryEventStatus
from syft_space.components.analytics.repository import QueryEventRepository
from syft_space.components.shared.database import AsyncDatabase

from .conftest import TENANT_ID


class TestQueryEventCollector:
    """Fire-and-forget event capture."""

    async def test_capture_persists_event(
        self, event_repository: QueryEventRepository, analytics_db: AsyncDatabase
    ):
        """capture() persists a query event to the database."""
        collector = QueryEventCollector(event_repository)
        ep_id = uuid4()

        await collector.capture(
            tenant_id=TENANT_ID,
            endpoint_id=ep_id,
            endpoint_slug="test-slug",
            dataset_id=None,
            user_email="alice@test.com",
            revenue_amount=1.50,
            currency="USD",
            status=QueryEventStatus.SUCCESS.value,
        )

        # Verify event was stored
        now = datetime.now(timezone.utc)
        count, revenue, users = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(minutes=1), now
        )
        assert count == 1
        assert revenue == 1.50
        assert users == 1

    async def test_capture_swallows_exceptions(self):
        """Exceptions in capture are logged, not raised."""
        mock_repo = AsyncMock(spec=QueryEventRepository)
        mock_repo.create.side_effect = RuntimeError("DB down")

        collector = QueryEventCollector(mock_repo)

        # Should not raise
        with patch("syft_space.components.analytics.collector.logger") as mock_logger:
            await collector.capture(
                tenant_id=TENANT_ID,
                endpoint_id=uuid4(),
                endpoint_slug="test",
                dataset_id=None,
                user_email="user@test.com",
                revenue_amount=0.0,
                currency="USD",
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
            revenue_amount=0.0,
            currency="USD",
            status=QueryEventStatus.NOT_FOUND.value,
        )

        now = datetime.now(timezone.utc)
        # With status=None we get all events regardless of status
        count, _, _ = await event_repository.get_summary_counts(
            TENANT_ID, now - timedelta(minutes=1), now, status=None
        )
        assert count == 1

        # With status=SUCCESS we should get 0 (it was NOT_FOUND)
        count_success, _, _ = await event_repository.get_summary_counts(
            TENANT_ID,
            now - timedelta(minutes=1),
            now,
            status=QueryEventStatus.SUCCESS.value,
        )
        assert count_success == 0
