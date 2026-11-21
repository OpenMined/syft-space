"""A failed dataset search is logged and reported, never passed off as an
empty result.

After an embedding-model change the stored vectors no longer match the query
embedding; ChromaDB raises a dimension mismatch, which used to come back as
"no documents" with nothing in the log.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from loguru import logger

from syft_space.components.shared.search_types import SearchContext, SearchResult
from syft_space.components.vector_stores.chromadb_local import (
    chromadb_vector_store as store_module,
)
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
)
from tests.components.endpoints.test_response_type_flow import (
    TENANT_ID,
    _make_endpoint,
    _make_handler,
    _make_request,
)

_MISMATCH = "Collection expecting embedding with dimension of 384, got 1024"


@pytest.fixture
def logged():
    """Loguru records at ERROR and above, with their exception info."""
    records: list = []
    sink = logger.add(lambda message: records.append(message.record), level="ERROR")
    yield records
    logger.remove(sink)


def _failing_store(monkeypatch) -> ChromaDBLocalVectorStore:
    monkeypatch.setattr(store_module, "_chromadb_available", lambda: True)

    class _Collection:
        async def query(self, **kwargs):
            raise ValueError(_MISMATCH)

    class _Client:
        async def get_collection(self, name):
            return _Collection()

    store = ChromaDBLocalVectorStore.__new__(ChromaDBLocalVectorStore)
    store.config = SimpleNamespace(collection_name="docs")
    store._generate_embeddings = lambda texts: [[0.0] for _ in texts]

    async def _client():
        return _Client()

    store.get_client = _client
    return store


async def test_chroma_search_failure_is_logged_with_traceback(monkeypatch, logged):
    dataset_id = uuid4()
    store = _failing_store(monkeypatch)

    result = await store.search(
        SearchContext(sender="a@b.c", dataset_id=dataset_id), "q"
    )

    assert result.documents == []
    assert _MISMATCH in result.metadata["error"]
    assert len(logged) == 1
    record = logged[0]
    assert "Collection_docs" in record["message"]
    assert str(dataset_id) in record["message"]
    assert record["exception"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("response_type", ["raw", "summary", "both"])
async def test_search_error_reaches_the_response(response_type, logged) -> None:
    """200 with ``search_error`` set, in every response type: a chat client
    keeps working, a client that checks can tell a failure from no match."""
    handler, dataset_instance, _ = _make_handler(_make_endpoint(response_type))
    dataset_instance.search = AsyncMock(
        return_value=SearchResult(
            documents=[], metadata={"count": 0, "error": f"ValueError: {_MISMATCH}"}
        )
    )

    response = await handler.query_endpoint(
        "ep", _make_request(), SimpleNamespace(id=TENANT_ID)
    )

    assert response.search_error == f"ValueError: {_MISMATCH}"
    assert any(_MISMATCH in record["message"] for record in logged)


@pytest.mark.asyncio
async def test_empty_search_has_no_search_error() -> None:
    handler, dataset_instance, _ = _make_handler(_make_endpoint("raw"))
    dataset_instance.search = AsyncMock(return_value=SearchResult(documents=[]))

    response = await handler.query_endpoint(
        "ep", _make_request(), SimpleNamespace(id=TENANT_ID)
    )

    assert response.references is not None
    assert response.references.documents == []
    assert response.search_error is None


@pytest.mark.asyncio
async def test_store_that_raises_is_logged_and_turns_into_500(logged) -> None:
    """Weaviate raises instead of failing softly: the handler keeps its
    convention of HTTP 500 and logs with the traceback."""
    from fastapi import HTTPException

    handler, dataset_instance, _ = _make_handler(_make_endpoint("raw"))
    dataset_instance.search = AsyncMock(side_effect=RuntimeError(_MISMATCH))

    with pytest.raises(HTTPException) as err:
        await handler.query_endpoint(
            "ep", _make_request(), SimpleNamespace(id=TENANT_ID)
        )

    assert err.value.status_code == 500
    assert _MISMATCH in str(err.value.detail)
    assert any(record["exception"] is not None for record in logged)
