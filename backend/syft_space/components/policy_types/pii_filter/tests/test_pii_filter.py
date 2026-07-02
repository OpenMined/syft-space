"""Tests for the PII filter policy type."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from syft_space.components.model_types.interfaces import (
    ChatMessageResult,
    ChatResult,
    TokenUsage,
)
from syft_space.components.policy_types.interfaces import PolicyContext
from syft_space.components.policy_types.pii_filter.pii_filter_type import (
    PiiFilterConfig,
    PiiFilterType,
)


def _make_model_mock(sanitized_text: str) -> AsyncMock:
    """Return an async mock that behaves like a model instance."""
    mock = AsyncMock()
    mock.chat.return_value = ChatResult(
        id="mock-id",
        model="mock-model",
        messages=[
            ChatMessageResult(role="assistant", content=sanitized_text, tokens=10)
        ],
        finish_reason="stop",
        usage=TokenUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
    )
    return mock


def _ctx(response: dict | None, model_mock: AsyncMock | None = None) -> PolicyContext:
    metadata: dict = {}
    if model_mock is not None:
        metadata["model_instance"] = model_mock
        metadata["model_id"] = str(uuid4())
    return PolicyContext(
        endpoint_slug="test-endpoint",
        sender_email="tester@example.com",
        request={},
        response=response,
        metadata=metadata,
    )


def _summary_response(content: str) -> dict:
    """Build a minimal QueryEndpointResponse-shaped dict with a summary."""
    return {
        "summary": {
            "id": "x",
            "model": "m",
            "message": {"role": "assistant", "content": content, "tokens": 5},
            "finish_reason": "stop",
            "usage": {},
            "cost": 0.0,
            "provider_info": {},
        },
        "references": None,
    }


# ---------------------------------------------------------------------------
# pre_hook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pre_hook_is_passthrough() -> None:
    policy = PiiFilterType()
    ctx = _ctx({"foo": "bar"})
    result = await policy.pre_hook([{}], ctx)
    assert result is ctx
    assert result.response == {"foo": "bar"}


# ---------------------------------------------------------------------------
# post_hook — no-op paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_hook_skips_when_no_model_in_metadata() -> None:
    """Endpoints without a model (data-only) must not be affected."""
    policy = PiiFilterType()
    response = _summary_response("Contact support@example.com for help.")
    ctx = _ctx(response)  # no model_instance in metadata

    result = await policy.post_hook([{}], ctx)

    assert result.response == response


@pytest.mark.asyncio
async def test_post_hook_skips_when_response_is_none() -> None:
    policy = PiiFilterType()
    mock_model = _make_model_mock("sanitized")
    ctx = _ctx(None, mock_model)

    result = await policy.post_hook([{}], ctx)

    mock_model.chat.assert_not_called()
    assert result.response is None


@pytest.mark.asyncio
async def test_post_hook_skips_when_no_summary_in_response() -> None:
    """Data-only responses have no summary.message.content — skip silently."""
    policy = PiiFilterType()
    mock_model = _make_model_mock("[REDACTED]")
    ctx = _ctx({"summary": None, "references": {"documents": []}}, mock_model)

    await policy.post_hook([{}], ctx)

    mock_model.chat.assert_not_called()


# ---------------------------------------------------------------------------
# post_hook — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_hook_calls_model_and_replaces_content() -> None:
    policy = PiiFilterType()
    original = "Hi, I'm John Doe, email: john@example.com"
    sanitized = "Hi, I'm [REDACTED], email: [REDACTED]"
    mock_model = _make_model_mock(sanitized)
    ctx = _ctx(_summary_response(original), mock_model)

    result = await policy.post_hook([{}], ctx)

    mock_model.chat.assert_called_once()
    assert result.response is not None
    assert result.response["summary"]["message"]["content"] == sanitized


@pytest.mark.asyncio
async def test_post_hook_preserves_rest_of_response_unchanged() -> None:
    """Only summary.message.content is modified; all other fields survive."""
    policy = PiiFilterType()
    mock_model = _make_model_mock("clean text")
    response = _summary_response("original text with PII")
    response["references"] = {"documents": [{"id": "1", "content": "raw doc"}]}
    ctx = _ctx(response, mock_model)

    result = await policy.post_hook([{}], ctx)

    assert result.response is not None
    assert result.response["references"] == response["references"]
    assert result.response["summary"]["model"] == "m"


@pytest.mark.asyncio
async def test_post_hook_passes_default_system_prompt_to_model() -> None:
    policy = PiiFilterType()
    mock_model = _make_model_mock("clean")
    ctx = _ctx(_summary_response("original"), mock_model)

    await policy.post_hook([{}], ctx)

    call_args = mock_model.chat.call_args
    messages = call_args.args[1]
    system_msg = next((m for m in messages if m.role == "system"), None)
    assert system_msg is not None
    assert "personally identifiable information" in system_msg.content.lower()


@pytest.mark.asyncio
async def test_post_hook_appends_custom_instructions() -> None:
    policy = PiiFilterType()
    mock_model = _make_model_mock("clean")
    cfg = PiiFilterConfig(instructions="Also redact company names.").model_dump()
    ctx = _ctx(_summary_response("original"), mock_model)

    await policy.post_hook([cfg], ctx)

    call_args = mock_model.chat.call_args
    messages = call_args.args[1]
    system_msg = next(m for m in messages if m.role == "system")
    assert "Also redact company names." in system_msg.content


# ---------------------------------------------------------------------------
# post_hook — error resilience
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_hook_gracefully_skips_on_model_error() -> None:
    """If the model call fails, the original content must be returned unchanged."""
    policy = PiiFilterType()
    original = "text with some PII"
    mock_model = AsyncMock()
    mock_model.chat.side_effect = RuntimeError("model offline")
    ctx = _ctx(_summary_response(original), mock_model)

    result = await policy.post_hook([{}], ctx)

    assert result.response is not None
    assert result.response["summary"]["message"]["content"] == original


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_config_accepts_empty_config() -> None:
    cfg = await PiiFilterType.validate_config({})
    assert cfg == {"instructions": ""}


@pytest.mark.asyncio
async def test_validate_config_accepts_instructions_field() -> None:
    cfg = await PiiFilterType.validate_config(
        {"instructions": "Also redact nicknames."}
    )
    assert cfg["instructions"] == "Also redact nicknames."


@pytest.mark.asyncio
async def test_validate_config_rejects_unknown_fields_gracefully() -> None:
    """Pydantic ignores extra fields by default; unknown keys are dropped."""
    cfg = await PiiFilterType.validate_config({"instructions": "", "unknown_key": "x"})
    assert "unknown_key" not in cfg


# ---------------------------------------------------------------------------
# metadata accessors
# ---------------------------------------------------------------------------


def test_metadata_accessors() -> None:
    assert PiiFilterType.name() == "pii_filter"
    assert "personally identifiable information" in PiiFilterType.description().lower()
    assert PiiFilterType.icon()
    schema = PiiFilterType.configuration_schema()
    assert "properties" in schema
    assert "instructions" in schema["properties"]
