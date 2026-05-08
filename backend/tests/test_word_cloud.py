"""Tests for word cloud handler and repository — word cloud feature."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from syft_space.components.analytics.handlers import AnalyticsHandler
from syft_space.components.analytics.repository import QueryEventRepository
from syft_space.components.analytics.schemas import TimeRange
from syft_space.components.tenants.entities import Tenant

from .conftest import TENANT_ID, make_event


def _make_tenant() -> Tenant:
    return Tenant(
        id=TENANT_ID,
        name="test-tenant",
        display_name="Test Tenant",
        domain="test.example.com",
    )


# ============== Repository: get_query_texts ==============


class TestGetQueryTexts:
    """QueryEventRepository.get_query_texts."""

    async def test_returns_non_empty_texts(
        self, event_repository: QueryEventRepository
    ):
        now = datetime.now(timezone.utc)

        await event_repository.create_with_lines(
            make_event(query_text="machine learning models", timestamp=now), []
        )
        await event_repository.create_with_lines(
            make_event(query_text="natural language processing", timestamp=now), []
        )
        # Empty text should be excluded
        await event_repository.create_with_lines(
            make_event(query_text="", timestamp=now), []
        )

        texts = await event_repository.get_query_texts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=None,
        )

        assert len(texts) == 2
        assert "machine learning models" in texts
        assert "natural language processing" in texts

    async def test_empty_range(self, event_repository: QueryEventRepository):
        now = datetime.now(timezone.utc)
        texts = await event_repository.get_query_texts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            endpoint_id=None,
            dataset_id=None,
            status=None,
        )
        assert texts == []

    async def test_respects_endpoint_filter(
        self, event_repository: QueryEventRepository
    ):
        from uuid import uuid4

        now = datetime.now(timezone.utc)
        ep1 = uuid4()
        ep2 = uuid4()

        await event_repository.create_with_lines(
            make_event(endpoint_id=ep1, query_text="data analysis", timestamp=now),
            [],
        )
        await event_repository.create_with_lines(
            make_event(
                endpoint_id=ep2, query_text="image recognition", timestamp=now
            ),
            [],
        )

        texts = await event_repository.get_query_texts(
            TENANT_ID,
            now - timedelta(days=1),
            now,
            endpoint_id=ep1,
            dataset_id=None,
            status=None,
        )

        assert len(texts) == 1
        assert texts[0] == "data analysis"


# ============== Handler: get_word_cloud ==============


class TestGetWordCloud:
    """AnalyticsHandler.get_word_cloud with mocked repository."""

    async def test_aggregates_word_frequencies(self):
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        event_repo.get_query_texts.return_value = [
            "machine learning models",
            "deep learning neural networks",
            "machine learning algorithms",
        ]

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_word_cloud(_make_tenant(), TimeRange.THIRTY_DAYS)

        assert len(result.words) > 0
        # Words should be sorted by count descending
        counts = [w.count for w in result.words]
        assert counts == sorted(counts, reverse=True)
        # "learning" or its lemma should appear with count >= 2
        word_map = {w.word: w.count for w in result.words}
        learning_variants = [c for w, c in word_map.items() if "learn" in w]
        assert any(c >= 2 for c in learning_variants)

    async def test_empty_texts_returns_empty(self):
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()
        event_repo.get_query_texts.return_value = []

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_word_cloud(_make_tenant(), TimeRange.SEVEN_DAYS)

        assert result.words == []

    async def test_max_words_capping(self):
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        # Generate text with many unique words
        words = [f"word{i}" for i in range(100)]
        event_repo.get_query_texts.return_value = [" ".join(words)]

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_word_cloud(
            _make_tenant(), TimeRange.THIRTY_DAYS, max_words=10
        )

        assert len(result.words) <= 10

    async def test_custom_stop_words_passed_through(self):
        event_repo = AsyncMock()
        endpoint_repo = AsyncMock()

        event_repo.get_query_texts.return_value = [
            "endpoint dataset query machine learning"
        ]

        handler = AnalyticsHandler(event_repo, endpoint_repo)
        result = await handler.get_word_cloud(
            _make_tenant(),
            TimeRange.THIRTY_DAYS,
            custom_stop_words=["endpoint", "dataset", "query"],
        )

        word_set = {w.word for w in result.words}
        assert "endpoint" not in word_set
        assert "dataset" not in word_set
        assert "query" not in word_set
