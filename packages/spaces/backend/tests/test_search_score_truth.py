"""Search score truth: both stores report ``1 - cosine_distance / 2`` and the
similarity threshold is applied before ``limit`` truncation, not after."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from syft_space.components.shared.search_types import SearchContext, SearchParameters
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    _OVERFETCH_FACTOR,
    ChromaDBLocalVectorStore,
)
from syft_space.components.vector_stores.weaviate_remote import weaviate_vector_store

# ============== Weaviate ==============


def test_weaviate_score_is_certainty_not_bm25_score():
    """``near_text`` populates ``certainty``; ``score`` stays None (BM25 only)."""
    src = Path(weaviate_vector_store.__file__).read_text()
    assert "certainty=True" in src
    assert "similarity_score=result.metadata.certainty" in src
    assert "metadata.score" not in src


# ============== ChromaDB ==============


def _results(distances: list[float]) -> dict:
    ids = [f"c{i}" for i in range(len(distances))]
    return {
        "ids": [ids],
        "distances": [distances],
        "documents": [[f"text {i}" for i in ids]],
        "metadatas": [[{"doc_id": "d"} for _ in ids]],
    }


def _store() -> ChromaDBLocalVectorStore:
    return ChromaDBLocalVectorStore.__new__(ChromaDBLocalVectorStore)


def test_chroma_threshold_runs_before_limit_truncation():
    # Nearest-first: rows 0,1 pass, 2,3 miss, 4,5,6 pass. With limit 3 the
    # old code (fetch 3, then filter) returned only rows 0 and 1.
    results = _results([0.2, 0.4, 1.6, 1.8, 0.6, 0.7, 0.8])
    docs, matched = _store()._process_query_results(
        results, "ds", similarity_threshold=0.5, limit=3
    )
    assert [d.document_id for d in docs] == ["c0", "c1", "c4"]
    assert matched == {"c0", "c1", "c4"}


def test_chroma_score_is_one_minus_half_distance():
    docs, _ = _store()._process_query_results(
        _results([0.0, 1.0]), "ds", similarity_threshold=0.0, limit=5
    )
    assert [d.similarity_score for d in docs] == [1.0, 0.5]


async def test_chroma_search_overfetches_then_returns_at_most_limit():
    captured: dict = {}

    class _Collection:
        async def query(self, **kwargs):
            captured.update(kwargs)
            return _results([0.1] * kwargs["n_results"])

        async def get(self, ids, include):
            return {"ids": [], "documents": []}

    class _Client:
        async def get_collection(self, name):
            return _Collection()

    store = _store()
    store.config = SimpleNamespace(collection_name="docs")
    store._generate_embeddings = lambda texts: [[0.0] for _ in texts]

    async def _client():
        return _Client()

    store.get_client = _client

    ctx = SearchContext(sender="a@b.c", dataset_id=uuid4())
    result = await store.search(
        ctx, "q", SearchParameters(similarity_threshold=0.5, limit=5)
    )

    assert captured["n_results"] == 5 * _OVERFETCH_FACTOR
    assert len(result.documents) == 5
