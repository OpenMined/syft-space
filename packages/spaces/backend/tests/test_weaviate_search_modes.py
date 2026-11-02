"""Weaviate search modes: the call each mode makes and where its score comes
from. The collection is stubbed; nothing connects."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from weaviate.classes.query import HybridFusion

from syft_space.components.shared.search_types import SearchContext, SearchParameters
from syft_space.components.vector_stores.weaviate_remote.schemas import SearchMode
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateVectorStore,
)

CONF: dict[str, Any] = {
    "http_url": "https://weaviate.example",
    "grpc_url": "https://weaviate.example:50051",
    "api_key": "k",
    "collection_name": "Docs",
    "content_property": "body",
}


def _hit(*, certainty: float | None = None, score: float | None = None):
    return SimpleNamespace(
        uuid=uuid4(),
        properties={"body": "text"},
        metadata=SimpleNamespace(
            certainty=certainty, score=score, distance=0.3, creation_time=None
        ),
    )


class _Collection:
    """Records the one query call made against it."""

    def __init__(self, hits):
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._hits = hits
        self.query = SimpleNamespace(near_text=self._near_text, hybrid=self._hybrid)

    async def _near_text(self, **kwargs):
        self.calls.append(("near_text", kwargs))
        return SimpleNamespace(objects=self._hits)

    async def _hybrid(self, **kwargs):
        self.calls.append(("hybrid", kwargs))
        return SimpleNamespace(objects=self._hits)


async def _search(config: dict[str, Any], hits, **params):
    store = WeaviateVectorStore(config)
    collection = _Collection(hits)
    client = SimpleNamespace(
        collections=SimpleNamespace(get=lambda name: collection),
    )

    async def get_client():
        return client

    store.get_client = get_client  # type: ignore[method-assign]
    result = await store.search(
        SearchContext(dataset_id=uuid4(), sender="owner@example.org"),
        "persijap",
        SearchParameters(**params),
    )
    return collection.calls, result


class TestVectorMode:
    async def test_is_the_default(self):
        assert WeaviateVectorStore(CONF).config.search_mode is SearchMode.VECTOR

    async def test_calls_near_text_with_the_threshold_as_certainty(self):
        calls, _ = await _search(CONF, [_hit(certainty=0.8)], similarity_threshold=0.6)
        assert [name for name, _ in calls] == ["near_text"]
        kwargs = calls[0][1]
        assert kwargs["query"] == "persijap"
        assert kwargs["certainty"] == 0.6
        assert kwargs["limit"] == 5

    async def test_score_is_certainty(self):
        _, result = await _search(CONF, [_hit(certainty=0.8, score=0.01)])
        assert result.documents[0].similarity_score == 0.8


class TestHybridMode:
    HYBRID = {**CONF, "search_mode": "hybrid", "alpha": 0.4}

    async def test_calls_hybrid_with_relative_score_fusion(self):
        calls, _ = await _search(
            self.HYBRID, [_hit(score=0.9)], similarity_threshold=0.6
        )
        assert [name for name, _ in calls] == ["hybrid"]
        kwargs = calls[0][1]
        assert kwargs["query"] == "persijap"
        assert kwargs["alpha"] == 0.4
        assert kwargs["fusion_type"] is HybridFusion.RELATIVE_SCORE
        assert kwargs["limit"] == 5

    async def test_threshold_bounds_the_vector_leg_as_a_distance(self):
        calls, _ = await _search(self.HYBRID, [], similarity_threshold=0.6)
        assert calls[0][1]["max_vector_distance"] == pytest.approx(0.8)

    async def test_keyword_leg_is_not_restricted_to_the_content_property(self):
        calls, _ = await _search(self.HYBRID, [])
        assert "query_properties" not in calls[0][1]

    async def test_score_is_the_fused_score(self):
        _, result = await _search(self.HYBRID, [_hit(certainty=0.8, score=0.9)])
        assert result.documents[0].similarity_score == 0.9

    async def test_a_missing_score_reads_as_zero(self):
        _, result = await _search(self.HYBRID, [_hit(score=None)])
        assert result.documents[0].similarity_score == 0.0

    async def test_alpha_defaults_vector_heavy(self):
        store = WeaviateVectorStore({**CONF, "search_mode": "hybrid"})
        assert store.config.alpha == 0.7

    @pytest.mark.parametrize("alpha", [-0.1, 1.5])
    async def test_alpha_outside_the_unit_interval_is_refused(self, alpha):
        with pytest.raises(ValueError):
            WeaviateVectorStore({**CONF, "search_mode": "hybrid", "alpha": alpha})

    async def test_an_unknown_mode_is_refused(self):
        with pytest.raises(ValueError):
            WeaviateVectorStore({**CONF, "search_mode": "bm25"})
