"""Regression test: chunk writes must be batched under ChromaDB's add() limit.

A large file (a per-row-chunked CSV produced ~8000 chunks) exceeded ChromaDB's
~5461 max batch size when written in a single ``collection.add`` call and the
ingestion job failed. ``_store_chunks`` now splits writes into _ADD_BATCH_SIZE
batches.
"""

from __future__ import annotations

from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    _ADD_BATCH_SIZE,
    ChromaDBLocalVectorStore,
)


class _FakeCollection:
    def __init__(self):
        self.batch_sizes: list[int] = []
        self.all_ids: list[str] = []
        self.deleted_where: list[dict] = []

    async def delete(self, where):
        # Must land before any add: the delete is what replaces the previous
        # version rather than leaving it alongside the new one.
        assert not self.all_ids
        self.deleted_where.append(where)

    async def add(self, ids, documents, embeddings, metadatas):
        # Every batch must be self-consistent and within the cap.
        assert len(ids) == len(documents) == len(embeddings) == len(metadatas)
        assert len(ids) <= _ADD_BATCH_SIZE
        self.batch_sizes.append(len(ids))
        self.all_ids.extend(ids)


def _chunks(n: int) -> list[dict]:
    return [
        {
            "doc_id": "doc",
            "text": f"t{i}",
            "embedding_text": f"e{i}",
            "file_name": "big.csv",
            "file_type": "csv",
            "file_size": 1,
            "page_numbers": [],
            "headings": [],
            "picture_ids": [],
        }
        for i in range(n)
    ]


async def _store(n: int) -> _FakeCollection:
    # Bypass __init__ (no ChromaDB/ONNX); stub the embedder.
    store = ChromaDBLocalVectorStore.__new__(ChromaDBLocalVectorStore)
    store._generate_embeddings = lambda texts: [[0.0] for _ in texts]
    coll = _FakeCollection()
    await store._store_chunks(coll, _chunks(n))
    return coll


async def test_large_input_is_split_into_capped_batches():
    n = 2 * _ADD_BATCH_SIZE + 20  # forces three batches
    coll = await _store(n)
    assert coll.batch_sizes == [_ADD_BATCH_SIZE, _ADD_BATCH_SIZE, 20]
    # Every chunk written exactly once, ids unique and complete.
    assert len(coll.all_ids) == n
    assert coll.all_ids == [f"doc_{i}" for i in range(n)]


async def test_previous_version_is_deleted_before_adding():
    """Without this an edited item is indexed twice, old chunks and new."""
    coll = await _store(3)
    assert coll.deleted_where == [{"doc_id": "doc"}]


async def test_small_input_is_one_batch():
    coll = await _store(3)
    assert coll.batch_sizes == [3]


async def test_empty_input_writes_nothing():
    coll = await _store(0)
    assert coll.batch_sizes == []
