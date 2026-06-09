"""Unit tests for endpoint-level system prompt override in ``_chat_with_model``.

These tests verify OME-235: when an ``Endpoint`` has a non-empty ``system_prompt``
set, the custom prompt takes precedence over the model's default system prompt
by being injected into the ``messages`` list passed to ``model_instance.chat``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.handlers import EndpointHandler
from syft_space.components.endpoints.schemas import (
    AuthenticatedQueryRequest,
    ChatMessageRequest,
)
from syft_space.components.model_types.interfaces import (
    ChatMessageResult,
    ChatResult,
    TokenUsage,
)


def _make_chat_result() -> ChatResult:
    """Return a minimal valid ``ChatResult`` for the mocked model."""
    return ChatResult(
        id="chat-test-id",
        model="test-model",
        messages=[
            ChatMessageResult(role="assistant", content="ok", tokens=1),
        ],
        finish_reason="stop",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def _make_handler(model_instance: MagicMock) -> tuple[EndpointHandler, MagicMock]:
    """Build a handler whose dependencies are mocks. Returns (handler, model)."""
    tenant_id = uuid4()
    model_id = uuid4()

    mock_model = SimpleNamespace(
        id=model_id,
        tenant_id=tenant_id,
        dtype="openai",
        configuration={},
    )

    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=mock_model)

    model_type_cls = MagicMock(return_value=model_instance)
    model_registry = MagicMock()
    model_registry.get_model_type = MagicMock(return_value=model_type_cls)

    handler = EndpointHandler(
        endpoint_repository=MagicMock(),
        dataset_repository=MagicMock(),
        model_repository=model_repository,
        policy_repository=MagicMock(),
        dataset_registry=MagicMock(),
        model_registry=model_registry,
        policy_registry=MagicMock(),
    )
    return handler, mock_model


def _make_endpoint(system_prompt: str | None) -> Endpoint:
    """Build an ``Endpoint`` entity with the given optional system prompt."""
    return Endpoint(
        name="ep",
        slug="ep",
        tenant_id=uuid4(),
        model_id=uuid4(),
        system_prompt=system_prompt,
    )


def _make_request(
    messages: str | list[ChatMessageRequest],
) -> AuthenticatedQueryRequest:
    return AuthenticatedQueryRequest(
        messages=messages,
        sender_email="user@example.com",
    )


@pytest.mark.asyncio
async def test_system_prompt_inserted_when_no_leading_system_message() -> None:
    """A new system message should be inserted at index 0 when absent."""
    model_instance = MagicMock()
    model_instance.chat = AsyncMock(return_value=_make_chat_result())

    handler, mock_model = _make_handler(model_instance)
    endpoint = _make_endpoint(system_prompt="You are a legal assistant.")
    endpoint.model_id = mock_model.id
    endpoint.tenant_id = mock_model.tenant_id

    request = _make_request([ChatMessageRequest(role="user", content="Hi")])

    await handler._chat_with_model(endpoint, request, references=None)

    model_instance.chat.assert_awaited_once()
    _, messages_arg, _ = model_instance.chat.await_args.args
    assert len(messages_arg) == 2
    assert messages_arg[0].role == "system"
    assert messages_arg[0].content == "You are a legal assistant."
    assert messages_arg[1].role == "user"
    assert messages_arg[1].content == "Hi"


@pytest.mark.asyncio
async def test_system_prompt_replaces_existing_leading_system_message() -> None:
    """Existing leading system message content should be replaced."""
    model_instance = MagicMock()
    model_instance.chat = AsyncMock(return_value=_make_chat_result())

    handler, mock_model = _make_handler(model_instance)
    endpoint = _make_endpoint(system_prompt="Override prompt.")
    endpoint.model_id = mock_model.id
    endpoint.tenant_id = mock_model.tenant_id

    request = _make_request(
        [
            ChatMessageRequest(role="system", content="Old caller system."),
            ChatMessageRequest(role="user", content="Hi"),
        ]
    )

    await handler._chat_with_model(endpoint, request, references=None)

    _, messages_arg, _ = model_instance.chat.await_args.args
    assert len(messages_arg) == 2
    assert messages_arg[0].role == "system"
    assert messages_arg[0].content == "Override prompt."
    assert messages_arg[1].role == "user"


@pytest.mark.asyncio
async def test_no_override_when_endpoint_system_prompt_is_empty() -> None:
    """When ``endpoint.system_prompt`` is ``None`` or empty, messages pass through."""
    model_instance = MagicMock()
    model_instance.chat = AsyncMock(return_value=_make_chat_result())

    handler, mock_model = _make_handler(model_instance)
    endpoint = _make_endpoint(system_prompt=None)
    endpoint.model_id = mock_model.id
    endpoint.tenant_id = mock_model.tenant_id

    request = _make_request([ChatMessageRequest(role="user", content="Hi")])

    await handler._chat_with_model(endpoint, request, references=None)

    _, messages_arg, _ = model_instance.chat.await_args.args
    assert len(messages_arg) == 1
    assert messages_arg[0].role == "user"
    assert messages_arg[0].content == "Hi"
