"""Unit tests for the PII Filter policy type."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from syft_space.components.model_types.interfaces import (
    ChatMessageResult,
    ChatResult,
    TokenUsage,
)
from syft_space.components.policy_types.interfaces import (
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.policy_types.pii_filter.pii_filter_type import (
    PiiFilterConfig,
    PiiFilterPolicy,
    set_dependencies,
)

# ============================================================
# Fixtures
# ============================================================

TENANT_ID = uuid4()
MODEL_ID = uuid4()
ENDPOINT_SLUG = "test-endpoint"
SENDER_EMAIL = "user@example.com"

VALID_CONFIG = {
    "model_id": str(MODEL_ID),
    "prompt": "Redact all names and email addresses. Replace with [REDACTED].",
    "target": "both",
    "applied_to": ["*"],
    "max_tokens": 512,
    "on_error": "block",
}


def _make_chat_result(content: str) -> ChatResult:
    """Helper: create a ChatResult with the given assistant content."""
    return ChatResult(
        id="test-id",
        model="test-model",
        messages=[ChatMessageResult(role="assistant", content=content, tokens=10)],
        finish_reason="stop",
        usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
    )


def _make_context(
    response: dict | None = None,
    metadata: dict | None = None,
) -> PolicyContext:
    """Helper: create a PolicyContext for testing."""
    if metadata is None:
        metadata = {"tenant_id": str(TENANT_ID)}
    return PolicyContext(
        endpoint_slug=ENDPOINT_SLUG,
        sender_email=SENDER_EMAIL,
        request={"messages": "test query"},
        response=response,
        metadata=metadata,
    )


def _make_summary_response(content: str = "Alice Smith called 555-1234.") -> dict:
    return {
        "summary": {
            "id": "sum-1",
            "model": "gpt-4",
            "message": {"role": "assistant", "content": content, "tokens": 10},
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "cost": 0.0,
            "provider_info": {},
        },
        "references": None,
    }


def _make_references_response(docs: list[str] | None = None) -> dict:
    if docs is None:
        docs = ["John Doe, SSN 123-45-6789.", "Jane Doe, phone 555-0000."]
    return {
        "summary": None,
        "references": {
            "documents": [
                {
                    "document_id": f"doc-{i}",
                    "content": c,
                    "metadata": {},
                    "similarity_score": 0.9,
                }
                for i, c in enumerate(docs)
            ],
            "provider_info": {},
            "cost": 0.0,
        },
    }


def _make_both_response() -> dict:
    resp = _make_summary_response()
    resp["references"] = _make_references_response()["references"]
    return resp


def _make_mock_model_instance(filtered_text: str = "[REDACTED]") -> MagicMock:
    """Helper: create a mock model instance whose chat() returns filtered_text."""
    instance = MagicMock()
    instance.chat = AsyncMock(return_value=_make_chat_result(filtered_text))
    return instance


def _setup_dependencies(
    model_instance: MagicMock | None = None,
    model_found: bool = True,
    model_dtype: str = "openai",
) -> tuple[MagicMock, MagicMock]:
    """Helper: set up mock model registry and repository."""
    if model_instance is None:
        model_instance = _make_mock_model_instance()

    mock_model_entity = MagicMock()
    mock_model_entity.id = MODEL_ID
    mock_model_entity.dtype = model_dtype
    mock_model_entity.configuration = {"api_key": "test", "model": "gpt-4"}

    mock_model_type_cls = MagicMock()
    mock_model_type_cls.return_value = model_instance

    mock_registry = MagicMock()
    mock_registry.get_model_type.return_value = mock_model_type_cls

    mock_repository = MagicMock()
    mock_repository.get_by_id = AsyncMock(
        return_value=mock_model_entity if model_found else None
    )

    set_dependencies(mock_registry, mock_repository)

    return mock_registry, mock_repository


# ============================================================
# Config Validation Tests
# ============================================================


class TestPiiFilterConfig:
    def test_valid_config(self):
        config = PiiFilterConfig(**VALID_CONFIG)
        assert config.model_id == MODEL_ID
        assert config.target == "both"
        assert config.on_error == "block"
        assert config.applied_to == ["*"]
        assert config.max_tokens == 512

    def test_invalid_model_id_not_uuid(self):
        bad = {**VALID_CONFIG, "model_id": "not-a-uuid"}
        with pytest.raises(ValidationError):
            PiiFilterConfig(**bad)

    def test_prompt_too_short(self):
        bad = {**VALID_CONFIG, "prompt": "short"}
        with pytest.raises(ValidationError):
            PiiFilterConfig(**bad)

    def test_invalid_target(self):
        bad = {**VALID_CONFIG, "target": "everything"}
        with pytest.raises(ValidationError):
            PiiFilterConfig(**bad)

    def test_invalid_on_error(self):
        bad = {**VALID_CONFIG, "on_error": "ignore"}
        with pytest.raises(ValidationError):
            PiiFilterConfig(**bad)

    def test_max_tokens_too_low(self):
        bad = {**VALID_CONFIG, "max_tokens": 0}
        with pytest.raises(ValidationError):
            PiiFilterConfig(**bad)

    def test_max_tokens_too_high(self):
        bad = {**VALID_CONFIG, "max_tokens": 32001}
        with pytest.raises(ValidationError):
            PiiFilterConfig(**bad)

    def test_defaults_are_correct(self):
        minimal = {
            "model_id": str(MODEL_ID),
            "prompt": "Remove all PII from the text below.",
        }
        config = PiiFilterConfig(**minimal)
        assert config.target == "both"
        assert config.applied_to == ["*"]
        assert config.max_tokens == 2048
        assert config.on_error == "block"


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid_config_returns_dict(self):
        result = await PiiFilterPolicy.validate_config(VALID_CONFIG)
        assert isinstance(result, dict)
        # model_id should be serialized as string in JSON mode
        assert isinstance(result["model_id"], str)

    @pytest.mark.asyncio
    async def test_invalid_config_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid PII filter config"):
            await PiiFilterPolicy.validate_config({"model_id": "bad", "prompt": "x"})


# ============================================================
# Pre-Hook Tests
# ============================================================


class TestPreHook:
    @pytest.mark.asyncio
    async def test_pre_hook_is_noop(self):
        policy = PiiFilterPolicy()
        context = _make_context()
        result = await policy.pre_hook([VALID_CONFIG], context)
        assert result is context


# ============================================================
# Post-Hook: Core Filtering Tests
# ============================================================


class TestPostHookFiltering:
    @pytest.mark.asyncio
    async def test_filters_summary_content(self):
        _setup_dependencies(
            model_instance=_make_mock_model_instance("Filtered summary.")
        )
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "summary"}
        context = _make_context(_make_summary_response("Alice Smith called 555-1234."))

        result = await policy.post_hook([config], context)

        assert result.response["summary"]["message"]["content"] == "Filtered summary."

    @pytest.mark.asyncio
    async def test_filters_all_reference_documents(self):
        _setup_dependencies(model_instance=_make_mock_model_instance("[REDACTED]"))
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "references"}
        context = _make_context(_make_references_response(["Doc 1 PII.", "Doc 2 PII."]))

        result = await policy.post_hook([config], context)

        docs = result.response["references"]["documents"]
        assert all(doc["content"] == "[REDACTED]" for doc in docs)

    @pytest.mark.asyncio
    async def test_filters_both_summary_and_references(self):
        _setup_dependencies(model_instance=_make_mock_model_instance("clean"))
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "both"}
        context = _make_context(_make_both_response())

        result = await policy.post_hook([config], context)

        assert result.response["summary"]["message"]["content"] == "clean"
        docs = result.response["references"]["documents"]
        assert all(doc["content"] == "clean" for doc in docs)

    @pytest.mark.asyncio
    async def test_target_summary_leaves_references_untouched(self):
        original_doc_content = "John Doe SSN 123-45-6789"
        _setup_dependencies(
            model_instance=_make_mock_model_instance("filtered summary")
        )
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "summary"}
        context = _make_context(_make_both_response())
        assert context.response is not None
        context.response["references"]["documents"][0]["content"] = original_doc_content

        result = await policy.post_hook([config], context)

        assert (
            result.response["references"]["documents"][0]["content"]
            == original_doc_content
        )
        assert result.response["summary"]["message"]["content"] == "filtered summary"

    @pytest.mark.asyncio
    async def test_target_references_leaves_summary_untouched(self):
        original_summary = "Alice Smith called 555-1234."
        _setup_dependencies(model_instance=_make_mock_model_instance("[REDACTED]"))
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "references"}
        context = _make_context(_make_both_response())
        assert context.response is not None
        context.response["summary"]["message"]["content"] = original_summary

        result = await policy.post_hook([config], context)

        assert result.response["summary"]["message"]["content"] == original_summary
        docs = result.response["references"]["documents"]
        assert all(doc["content"] == "[REDACTED]" for doc in docs)


# ============================================================
# Post-Hook: Null / Empty Content Edge Cases
# ============================================================


class TestPostHookEdgeCases:
    @pytest.mark.asyncio
    async def test_null_response_returns_unchanged(self):
        _setup_dependencies()
        policy = PiiFilterPolicy()
        context = _make_context(response=None)

        result = await policy.post_hook([VALID_CONFIG], context)

        assert result.response is None

    @pytest.mark.asyncio
    async def test_null_summary_skips_summary_filtering(self):
        _setup_dependencies()
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "summary"}
        context = _make_context({"summary": None, "references": None})

        # Should not raise
        result = await policy.post_hook([config], context)
        assert result.response["summary"] is None

    @pytest.mark.asyncio
    async def test_empty_documents_list_no_crash(self):
        _setup_dependencies()
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "references"}
        context = _make_context(
            {
                "summary": None,
                "references": {"documents": [], "provider_info": {}, "cost": 0.0},
            }
        )

        result = await policy.post_hook([config], context)
        assert result.response["references"]["documents"] == []

    @pytest.mark.asyncio
    async def test_empty_configs_list_returns_unchanged(self):
        _setup_dependencies()
        policy = PiiFilterPolicy()
        context = _make_context(_make_summary_response())

        result = await policy.post_hook([], context)
        assert (
            result.response["summary"]["message"]["content"]
            == "Alice Smith called 555-1234."
        )

    @pytest.mark.asyncio
    async def test_empty_document_content_not_filtered(self):
        mock_instance = _make_mock_model_instance("should not be called")
        _setup_dependencies(model_instance=mock_instance)
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "target": "references"}
        context = _make_context(
            {
                "summary": None,
                "references": {
                    "documents": [
                        {
                            "document_id": "d1",
                            "content": "",
                            "metadata": {},
                            "similarity_score": 0.5,
                        }
                    ],
                    "provider_info": {},
                    "cost": 0.0,
                },
            }
        )

        await policy.post_hook([config], context)

        # chat() should not have been called for empty content
        mock_instance.chat.assert_not_called()


# ============================================================
# Post-Hook: applied_to Pattern Tests
# ============================================================


class TestAppliedTo:
    @pytest.mark.asyncio
    async def test_non_matching_email_skips_filter(self):
        mock_instance = _make_mock_model_instance("should not be called")
        _setup_dependencies(model_instance=mock_instance)
        policy = PiiFilterPolicy()
        original_content = "Alice Smith called 555-1234."
        config = {**VALID_CONFIG, "applied_to": ["trusted@internal.com"]}
        context = _make_context(_make_summary_response(original_content))

        result = await policy.post_hook([config], context)

        # Content should be unchanged — user@example.com doesn't match trusted@internal.com
        assert result.response["summary"]["message"]["content"] == original_content
        mock_instance.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_matching_domain_pattern_applies_filter(self):
        _setup_dependencies(model_instance=_make_mock_model_instance("filtered"))
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "applied_to": ["*@example.com"]}
        context = _make_context(_make_summary_response("Alice Smith called 555-1234."))

        result = await policy.post_hook([config], context)

        assert result.response["summary"]["message"]["content"] == "filtered"

    @pytest.mark.asyncio
    async def test_wildcard_matches_all_users(self):
        _setup_dependencies(model_instance=_make_mock_model_instance("filtered"))
        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "applied_to": ["*"]}
        context = _make_context(_make_summary_response("some PII here"))

        result = await policy.post_hook([config], context)

        assert result.response["summary"]["message"]["content"] == "filtered"


# ============================================================
# Post-Hook: Sequential Config Tests
# ============================================================


class TestSequentialConfigs:
    @pytest.mark.asyncio
    async def test_second_config_receives_output_of_first(self):
        """Each config processes the output of the previous one."""
        call_count = 0
        expected_inputs = ["original text", "pass-1 output"]

        async def mock_chat(_ctx, messages, _params):
            nonlocal call_count
            user_msg = messages[-1].content
            assert expected_inputs[call_count] in user_msg, (
                f"Call {call_count}: expected '{expected_inputs[call_count]}' in user message"
            )
            result_text = f"pass-{call_count + 1} output"
            call_count += 1
            return _make_chat_result(result_text)

        mock_instance = MagicMock()
        mock_instance.chat = mock_chat
        _setup_dependencies(model_instance=mock_instance)

        policy = PiiFilterPolicy()
        config1 = {**VALID_CONFIG, "target": "summary", "prompt": "First pass filter."}
        config2 = {**VALID_CONFIG, "target": "summary", "prompt": "Second pass filter."}

        context = _make_context(_make_summary_response("original text"))
        result = await policy.post_hook([config1, config2], context)

        assert result.response["summary"]["message"]["content"] == "pass-2 output"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_skipped_config_does_not_break_chain(self):
        """If the first config doesn't apply (wrong user), second still runs."""
        _setup_dependencies(model_instance=_make_mock_model_instance("second-filtered"))
        policy = PiiFilterPolicy()
        config_skip = {**VALID_CONFIG, "applied_to": ["other@domain.com"]}
        config_apply = {**VALID_CONFIG, "applied_to": ["*"]}

        context = _make_context(_make_summary_response("original"))
        result = await policy.post_hook([config_skip, config_apply], context)

        # First config skipped (no match), second config applied
        assert result.response["summary"]["message"]["content"] == "second-filtered"


# ============================================================
# Post-Hook: Error Handling Tests
# ============================================================


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_on_error_block_raises_policy_violation(self):
        failing_instance = MagicMock()
        failing_instance.chat = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        _setup_dependencies(model_instance=failing_instance)

        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "on_error": "block"}
        context = _make_context(_make_summary_response("Alice Smith"))

        with pytest.raises(PolicyViolationError) as exc_info:
            await policy.post_hook([config], context)

        assert exc_info.value.policy_type == "pii_filter"
        assert "block" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_on_error_passthrough_returns_original(self):
        failing_instance = MagicMock()
        failing_instance.chat = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        _setup_dependencies(model_instance=failing_instance)

        policy = PiiFilterPolicy()
        original_content = "Alice Smith called 555-1234."
        config = {**VALID_CONFIG, "on_error": "passthrough"}
        context = _make_context(_make_summary_response(original_content))

        result = await policy.post_hook([config], context)

        # Original content preserved on error
        assert result.response["summary"]["message"]["content"] == original_content

    @pytest.mark.asyncio
    async def test_model_not_found_raises_policy_violation(self):
        _setup_dependencies(model_found=False)
        policy = PiiFilterPolicy()
        context = _make_context(_make_summary_response())

        with pytest.raises(PolicyViolationError) as exc_info:
            await policy.post_hook([VALID_CONFIG], context)

        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.policy_type == "pii_filter"

    @pytest.mark.asyncio
    async def test_model_type_not_registered_raises_policy_violation(self):
        mock_registry = MagicMock()
        mock_registry.get_model_type.side_effect = KeyError("unknown-type")
        mock_repository = MagicMock()
        mock_model = MagicMock()
        mock_model.id = MODEL_ID
        mock_model.dtype = "unknown-type"
        mock_model.configuration = {}
        mock_repository.get_by_id = AsyncMock(return_value=mock_model)
        set_dependencies(mock_registry, mock_repository)

        policy = PiiFilterPolicy()
        context = _make_context(_make_summary_response())

        with pytest.raises(PolicyViolationError) as exc_info:
            await policy.post_hook([VALID_CONFIG], context)

        assert "not registered" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_tenant_id_raises_policy_violation(self):
        _setup_dependencies()
        policy = PiiFilterPolicy()
        context = _make_context(
            _make_summary_response(),
            metadata={},  # No tenant_id
        )

        with pytest.raises(PolicyViolationError) as exc_info:
            await policy.post_hook([VALID_CONFIG], context)

        assert "tenant_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_uninitialized_dependencies_raises_policy_violation(self):
        """If set_dependencies was never called, post_hook raises PolicyViolationError."""
        # Reset dependencies to None
        set_dependencies(None, None)  # type: ignore[arg-type]

        policy = PiiFilterPolicy()
        context = _make_context(_make_summary_response())

        with pytest.raises(PolicyViolationError) as exc_info:
            await policy.post_hook([VALID_CONFIG], context)

        assert "not initialized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_llm_returns_empty_messages_raises_on_block(self):
        empty_result = ChatResult(
            id="x",
            model="m",
            messages=[],  # Empty!
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
        failing_instance = MagicMock()
        failing_instance.chat = AsyncMock(return_value=empty_result)
        _setup_dependencies(model_instance=failing_instance)

        policy = PiiFilterPolicy()
        config = {**VALID_CONFIG, "on_error": "block"}
        context = _make_context(_make_summary_response("text"))

        with pytest.raises(PolicyViolationError):
            await policy.post_hook([config], context)

    @pytest.mark.asyncio
    async def test_llm_returns_empty_messages_passthrough(self):
        empty_result = ChatResult(
            id="x",
            model="m",
            messages=[],
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
        failing_instance = MagicMock()
        failing_instance.chat = AsyncMock(return_value=empty_result)
        _setup_dependencies(model_instance=failing_instance)

        policy = PiiFilterPolicy()
        original = "original text with PII"
        config = {**VALID_CONFIG, "on_error": "passthrough"}
        context = _make_context(_make_summary_response(original))

        result = await policy.post_hook([config], context)

        assert result.response["summary"]["message"]["content"] == original


# ============================================================
# Policy Type Metadata Tests
# ============================================================


class TestPolicyTypeMetadata:
    def test_name(self):
        assert PiiFilterPolicy.name() == "pii_filter"

    def test_description_non_empty(self):
        assert len(PiiFilterPolicy.description()) > 10

    def test_icon_non_empty(self):
        assert PiiFilterPolicy.icon()

    def test_enabled(self):
        assert PiiFilterPolicy.enabled() is True

    def test_configuration_schema_has_required_fields(self):
        schema = PiiFilterPolicy.configuration_schema()
        assert "properties" in schema
        props = schema["properties"]
        assert "model_id" in props
        assert "prompt" in props
        assert "target" in props
        assert "applied_to" in props
        assert "max_tokens" in props
        assert "on_error" in props

    def test_configuration_schema_model_id_has_format_hint(self):
        schema = PiiFilterPolicy.configuration_schema()
        model_id_schema = schema["properties"]["model_id"]
        assert model_id_schema.get("format") == "model-selector"

    def test_configuration_schema_prompt_has_textarea_hint(self):
        schema = PiiFilterPolicy.configuration_schema()
        prompt_schema = schema["properties"]["prompt"]
        assert prompt_schema.get("format") == "textarea"
