"""Tests for the per-response-type query flow in ``query_endpoint``.

Locks the retrieval/chat gating contract:

- ``raw``     -> dataset search only; references returned, no model call.
- ``summary`` -> dataset search feeds the model as RAG context, but the
                 references are stripped from the user-facing response.
- ``both``    -> dataset search + model chat; both returned.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.query_handler import QueryEndpointHandler
from syft_space.components.endpoints.schemas import AuthenticatedQueryRequest
from syft_space.components.model_types.interfaces import (
    ChatMessageResult,
    ChatResult,
    TokenUsage,
)
from syft_space.components.shared.search_types import SearchedDocument, SearchResult

TENANT_ID = uuid4()
DATASET_ID = uuid4()
MODEL_ID = uuid4()


def _make_chat_result() -> ChatResult:
    return ChatResult(
        id="chat-test-id",
        model="test-model",
        messages=[ChatMessageResult(role="assistant", content="answer", tokens=1)],
        finish_reason="stop",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def _make_search_result() -> SearchResult:
    return SearchResult(
        documents=[
            SearchedDocument(
                document_id="doc-1",
                content="retrieved paper content",
                similarity_score=0.9,
            )
        ]
    )


def _make_endpoint(response_type: str) -> Endpoint:
    return Endpoint(
        name="ep",
        slug="ep",
        tenant_id=TENANT_ID,
        dataset_id=DATASET_ID,
        model_id=MODEL_ID,
        response_type=response_type,
        published=True,
    )


def _make_handler(
    endpoint: Endpoint,
) -> tuple[QueryEndpointHandler, MagicMock, MagicMock]:
    """Build a handler with a mocked pipeline for ``endpoint``.

    Returns (handler, dataset_instance, model_instance) so tests can assert
    on search/chat calls.
    """
    endpoint_repository = MagicMock()
    endpoint_repository.get_by_slug = AsyncMock(return_value=endpoint)

    policy_repository = MagicMock()
    policy_repository.get_by_endpoint_id_grouped = AsyncMock(return_value={})

    dataset = SimpleNamespace(
        id=DATASET_ID, tenant_id=TENANT_ID, dtype="chroma", configuration={}
    )
    dataset_repository = MagicMock()
    dataset_repository.get_by_id = AsyncMock(return_value=dataset)

    dataset_instance = MagicMock()
    dataset_instance.search = AsyncMock(return_value=_make_search_result())
    dataset_registry = MagicMock()
    dataset_registry.get_dataset_type = MagicMock(
        return_value=MagicMock(return_value=dataset_instance)
    )

    model = SimpleNamespace(
        id=MODEL_ID, tenant_id=TENANT_ID, dtype="openai", configuration={}
    )
    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=model)

    model_instance = MagicMock()
    model_instance.chat = AsyncMock(return_value=_make_chat_result())
    model_instance.aclose = AsyncMock()
    model_registry = MagicMock()
    model_registry.get_model_type = MagicMock(
        return_value=MagicMock(return_value=model_instance)
    )

    handler = QueryEndpointHandler(
        endpoint_repository=endpoint_repository,
        dataset_repository=dataset_repository,
        model_repository=model_repository,
        policy_repository=policy_repository,
        dataset_registry=dataset_registry,
        model_registry=model_registry,
        policy_registry=MagicMock(),
    )
    return handler, dataset_instance, model_instance


def _make_request() -> AuthenticatedQueryRequest:
    return AuthenticatedQueryRequest(
        messages="what do the papers say?",
        sender_email="user@example.com",
    )


@pytest.mark.asyncio
async def test_raw_searches_dataset_and_skips_model() -> None:
    endpoint = _make_endpoint("raw")
    handler, dataset_instance, model_instance = _make_handler(endpoint)
    tenant = SimpleNamespace(id=TENANT_ID)

    response = await handler.query_endpoint("ep", _make_request(), tenant)

    dataset_instance.search.assert_awaited_once()
    model_instance.chat.assert_not_awaited()
    assert response.summary is None
    assert response.references is not None
    assert response.references.documents[0].document_id == "doc-1"


@pytest.mark.asyncio
async def test_summary_retrieves_and_feeds_model_but_strips_references() -> None:
    """SUMMARY must ground the model in the dataset without exposing it."""
    endpoint = _make_endpoint("summary")
    handler, dataset_instance, model_instance = _make_handler(endpoint)
    tenant = SimpleNamespace(id=TENANT_ID)

    response = await handler.query_endpoint("ep", _make_request(), tenant)

    dataset_instance.search.assert_awaited_once()
    model_instance.chat.assert_awaited_once()

    # The retrieved document must be injected as RAG context for the model.
    _, messages_arg, _ = model_instance.chat.await_args.args
    context_messages = [
        m
        for m in messages_arg
        if m.role == "system" and "retrieved paper content" in m.content
    ]
    assert len(context_messages) == 1

    # ...but the raw documents never leave the server.
    assert response.summary is not None
    assert response.summary.message.content == "answer"
    assert response.references is None


@pytest.mark.asyncio
async def test_summary_without_dataset_skips_search() -> None:
    endpoint = _make_endpoint("summary")
    endpoint.dataset_id = None
    handler, dataset_instance, model_instance = _make_handler(endpoint)
    tenant = SimpleNamespace(id=TENANT_ID)

    response = await handler.query_endpoint("ep", _make_request(), tenant)

    dataset_instance.search.assert_not_awaited()
    model_instance.chat.assert_awaited_once()
    assert response.summary is not None
    assert response.references is None


@pytest.mark.asyncio
async def test_both_returns_summary_and_references() -> None:
    endpoint = _make_endpoint("both")
    handler, dataset_instance, model_instance = _make_handler(endpoint)
    tenant = SimpleNamespace(id=TENANT_ID)

    response = await handler.query_endpoint("ep", _make_request(), tenant)

    dataset_instance.search.assert_awaited_once()
    model_instance.chat.assert_awaited_once()
    assert response.summary is not None
    assert response.references is not None
    assert response.references.documents[0].document_id == "doc-1"
