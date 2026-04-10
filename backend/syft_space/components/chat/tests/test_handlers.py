"""Unit tests for the local chat handler.

Covers timeout handling, error classification, and tenant isolation. All
external integrations (model types, dataset types, repositories) are mocked —
these tests are hermetic and make no network calls.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException

from syft_space.components.chat.handlers import LocalChatHandler
from syft_space.components.chat.schemas import (
    ChatMessageRequest,
    LocalChatRequest,
)
from syft_space.components.model_types.interfaces import (
    ChatMessageResult,
    ChatResult,
    TokenUsage,
)
from syft_space.config import app_settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tenant(tenant_id: UUID | None = None) -> SimpleNamespace:
    """Build a minimal tenant stub (we only need .id)."""
    return SimpleNamespace(id=tenant_id or uuid4())


def _make_model(model_id: UUID | None = None) -> SimpleNamespace:
    """Build a minimal model stub matching what the repository returns."""
    return SimpleNamespace(
        id=model_id or uuid4(),
        dtype="fake-model",
        configuration={},
    )


def _make_dataset(dataset_id: UUID | None = None) -> SimpleNamespace:
    """Build a minimal dataset stub matching what the repository returns."""
    return SimpleNamespace(
        id=dataset_id or uuid4(),
        dtype="fake-dataset",
        configuration={},
    )


def _make_chat_result(content: str = "hello!") -> ChatResult:
    return ChatResult(
        id="chatcmpl-test",
        model="fake-model",
        messages=[ChatMessageResult(role="assistant", content=content, tokens=2)],
        finish_reason="stop",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
    )


def _make_search_result(document_count: int = 0) -> SimpleNamespace:
    docs = [
        SimpleNamespace(
            document_id=f"doc-{i}",
            content=f"content-{i}",
            metadata={},
            similarity_score=0.9,
        )
        for i in range(document_count)
    ]
    return SimpleNamespace(documents=docs)


def _make_request(
    *,
    model_id: UUID | None = None,
    dataset_id: UUID | None = None,
) -> LocalChatRequest:
    return LocalChatRequest(
        model_id=model_id or uuid4(),
        dataset_id=dataset_id,
        messages=[ChatMessageRequest(role="user", content="hi")],
    )


def _build_handler(
    *,
    model: SimpleNamespace | None = None,
    dataset: SimpleNamespace | None = None,
    model_chat: AsyncMock | None = None,
    dataset_search: AsyncMock | None = None,
    model_type_missing: bool = False,
    dataset_type_missing: bool = False,
) -> tuple[LocalChatHandler, MagicMock, MagicMock]:
    """Wire a LocalChatHandler with fully mocked dependencies.

    Returns the handler along with the model and dataset repository mocks so
    tests can assert on the arguments they were called with.
    """
    model_repo = MagicMock()
    model_repo.get_by_id = AsyncMock(return_value=model)

    dataset_repo = MagicMock()
    dataset_repo.get_by_id = AsyncMock(return_value=dataset)

    model_instance = MagicMock()
    model_instance.chat = model_chat or AsyncMock(return_value=_make_chat_result())

    model_type_cls = MagicMock(return_value=model_instance)

    model_registry = MagicMock()
    if model_type_missing:
        model_registry.get_model_type = MagicMock(side_effect=KeyError("fake-model"))
    else:
        model_registry.get_model_type = MagicMock(return_value=model_type_cls)

    dataset_instance = MagicMock()
    dataset_instance.search = dataset_search or AsyncMock(
        return_value=_make_search_result(document_count=1)
    )

    dataset_type_cls = MagicMock(return_value=dataset_instance)

    dataset_registry = MagicMock()
    if dataset_type_missing:
        dataset_registry.get_dataset_type = MagicMock(
            side_effect=KeyError("fake-dataset")
        )
    else:
        dataset_registry.get_dataset_type = MagicMock(return_value=dataset_type_cls)

    handler = LocalChatHandler(
        dataset_repository=dataset_repo,
        model_repository=model_repo,
        dataset_registry=dataset_registry,
        model_registry=model_registry,
    )
    return handler, model_repo, dataset_repo


@pytest.fixture(autouse=True)
def _fast_chat_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep timeout tests snappy by default (overridden per-test as needed)."""
    monkeypatch.setattr(app_settings, "chat_timeout_seconds", 0.05)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_chat_happy_path_model_only() -> None:
    model = _make_model()
    handler, _, _ = _build_handler(model=model)
    request = _make_request(model_id=model.id)
    tenant = _make_tenant()

    response = await handler.chat(request, tenant)

    assert response.summary is not None
    assert response.summary.message.content == "hello!"
    assert response.references is None


async def test_chat_happy_path_with_dataset() -> None:
    model = _make_model()
    dataset = _make_dataset()
    handler, _, _ = _build_handler(model=model, dataset=dataset)
    request = _make_request(model_id=model.id, dataset_id=dataset.id)

    response = await handler.chat(request, _make_tenant())

    assert response.summary is not None
    assert response.references is not None
    assert len(response.references.documents) == 1
    assert response.references.search_engine == "fake-dataset"


# ---------------------------------------------------------------------------
# Timeout classification (504)
# ---------------------------------------------------------------------------


async def test_chat_model_timeout_returns_504() -> None:
    async def _hang(*_args: object, **_kwargs: object) -> ChatResult:
        await asyncio.sleep(1.0)  # exceeds fast timeout fixture (0.05s)
        return _make_chat_result()

    handler, _, _ = _build_handler(
        model=_make_model(),
        model_chat=AsyncMock(side_effect=_hang),
    )

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(_make_request(), _make_tenant())

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.detail.lower()


async def test_chat_dataset_search_timeout_returns_504() -> None:
    async def _hang(*_args: object, **_kwargs: object) -> object:
        await asyncio.sleep(1.0)
        return _make_search_result()

    dataset = _make_dataset()
    handler, _, _ = _build_handler(
        model=_make_model(),
        dataset=dataset,
        dataset_search=AsyncMock(side_effect=_hang),
    )
    request = _make_request(dataset_id=dataset.id)

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(request, _make_tenant())

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Upstream / network failures (502)
# ---------------------------------------------------------------------------


async def test_chat_model_upstream_http_error_returns_502() -> None:
    handler, _, _ = _build_handler(
        model=_make_model(),
        model_chat=AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(_make_request(), _make_tenant())

    assert exc_info.value.status_code == 502
    assert "upstream" in exc_info.value.detail.lower()
    assert "connection refused" in exc_info.value.detail


async def test_chat_dataset_upstream_connection_error_returns_502() -> None:
    dataset = _make_dataset()
    handler, _, _ = _build_handler(
        model=_make_model(),
        dataset=dataset,
        dataset_search=AsyncMock(side_effect=ConnectionError("boom")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(_make_request(dataset_id=dataset.id), _make_tenant())

    assert exc_info.value.status_code == 502
    assert "upstream" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Missing entities / config
# ---------------------------------------------------------------------------


async def test_chat_missing_model_returns_404() -> None:
    # model=None → repo returns None
    handler, _, _ = _build_handler(model=None)

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(_make_request(), _make_tenant())

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


async def test_chat_missing_dataset_returns_404() -> None:
    handler, _, _ = _build_handler(model=_make_model(), dataset=None)
    request = _make_request(dataset_id=uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(request, _make_tenant())

    assert exc_info.value.status_code == 404


async def test_chat_unregistered_model_type_returns_400() -> None:
    handler, _, _ = _build_handler(
        model=_make_model(),
        model_type_missing=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(_make_request(), _make_tenant())

    assert exc_info.value.status_code == 400
    assert "not registered" in exc_info.value.detail.lower()


async def test_chat_unregistered_dataset_type_returns_400() -> None:
    dataset = _make_dataset()
    handler, _, _ = _build_handler(
        model=_make_model(),
        dataset=dataset,
        dataset_type_missing=True,
    )
    request = _make_request(dataset_id=dataset.id)

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(request, _make_tenant())

    assert exc_info.value.status_code == 400
    assert "not registered" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Unknown failures (500) — model returns nothing
# ---------------------------------------------------------------------------


async def test_chat_model_returns_no_messages_returns_500() -> None:
    empty_result = ChatResult(
        id="chatcmpl-empty",
        model="fake-model",
        messages=[],
        finish_reason="stop",
        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
    )
    handler, _, _ = _build_handler(
        model=_make_model(),
        model_chat=AsyncMock(return_value=empty_result),
    )

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(_make_request(), _make_tenant())

    assert exc_info.value.status_code == 500
    assert "no messages" in exc_info.value.detail.lower()


async def test_chat_unexpected_model_error_returns_500() -> None:
    handler, _, _ = _build_handler(
        model=_make_model(),
        model_chat=AsyncMock(side_effect=RuntimeError("kaboom")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(_make_request(), _make_tenant())

    assert exc_info.value.status_code == 500
    assert "kaboom" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


async def test_chat_tenant_isolation_cannot_reach_other_tenants_model() -> None:
    """A request from tenant A must not surface tenant B's model.

    The repository is responsible for tenant-scoped lookups; here we assert
    that the handler forwards tenant.id unchanged and surfaces a 404 when the
    repository returns None for the caller's tenant.
    """
    tenant_a = _make_tenant()
    tenant_b_model = _make_model()  # conceptually owned by another tenant

    # Repository returns None when asked for this model scoped to tenant A.
    def _tenant_scoped_lookup(
        model_id: UUID, tenant_id: UUID
    ) -> SimpleNamespace | None:
        if tenant_id == tenant_a.id:
            return None
        return tenant_b_model

    handler, model_repo, _ = _build_handler(model=None)
    model_repo.get_by_id = AsyncMock(side_effect=_tenant_scoped_lookup)

    request = _make_request(model_id=tenant_b_model.id)

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(request, tenant_a)

    assert exc_info.value.status_code == 404
    model_repo.get_by_id.assert_awaited_once_with(tenant_b_model.id, tenant_a.id)


async def test_chat_tenant_isolation_cannot_reach_other_tenants_dataset() -> None:
    tenant_a = _make_tenant()
    tenant_b_dataset = _make_dataset()

    def _tenant_scoped_lookup(
        dataset_id: UUID, tenant_id: UUID
    ) -> SimpleNamespace | None:
        if tenant_id == tenant_a.id:
            return None
        return tenant_b_dataset

    handler, _, dataset_repo = _build_handler(model=_make_model(), dataset=None)
    dataset_repo.get_by_id = AsyncMock(side_effect=_tenant_scoped_lookup)

    request = _make_request(dataset_id=tenant_b_dataset.id)

    with pytest.raises(HTTPException) as exc_info:
        await handler.chat(request, tenant_a)

    assert exc_info.value.status_code == 404
    dataset_repo.get_by_id.assert_awaited_once_with(tenant_b_dataset.id, tenant_a.id)
