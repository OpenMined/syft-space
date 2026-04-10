"""Tests for the PII filter policy type."""

from __future__ import annotations

import pytest

from syft_space.components.policy_types.interfaces import PolicyContext
from syft_space.components.policy_types.pii_filter.pii_filter_type import (
    DEFAULT_REPLACEMENT,
    PiiFilterConfig,
    PiiFilterType,
)


def _ctx(response: dict | None) -> PolicyContext:
    return PolicyContext(
        endpoint_slug="test-endpoint",
        sender_email="tester@example.com",
        request={},
        response=response,
    )


def _default_cfg() -> dict:
    return PiiFilterConfig().model_dump()


def _response(context: PolicyContext) -> dict:
    """Return ``context.response`` and fail the test if it is ``None``."""
    assert context.response is not None
    return context.response


@pytest.mark.asyncio
async def test_post_hook_redacts_email_in_string_response() -> None:
    policy = PiiFilterType()
    context = _ctx({"message": "Contact us at support@example.com for help."})

    result = await policy.post_hook([_default_cfg()], context)

    assert DEFAULT_REPLACEMENT in _response(result)["message"]
    assert "support@example.com" not in _response(result)["message"]


@pytest.mark.asyncio
async def test_post_hook_redacts_phone_numbers() -> None:
    policy = PiiFilterType()
    cases = [
        "Call (555) 123-4567 tomorrow.",
        "Phone: 555-123-4567",
        "International: +1 555-123-4567",
        "Dotted: 555.123.4567",
    ]

    for sample in cases:
        context = _ctx({"msg": sample})
        result = await policy.post_hook([_default_cfg()], context)
        assert DEFAULT_REPLACEMENT in _response(result)["msg"], sample
        assert "123-4567" not in _response(result)["msg"], sample
        assert "123.4567" not in _response(result)["msg"], sample


@pytest.mark.asyncio
async def test_post_hook_redacts_ssn() -> None:
    policy = PiiFilterType()
    context = _ctx({"msg": "SSN on file: 123-45-6789."})

    result = await policy.post_hook([_default_cfg()], context)

    assert "123-45-6789" not in _response(result)["msg"]
    assert DEFAULT_REPLACEMENT in _response(result)["msg"]


@pytest.mark.asyncio
async def test_post_hook_redacts_credit_card_when_luhn_valid() -> None:
    policy = PiiFilterType()
    # 4111 1111 1111 1111 is the canonical Visa test number and passes Luhn.
    context = _ctx({"msg": "Card: 4111 1111 1111 1111 expires soon."})

    result = await policy.post_hook([_default_cfg()], context)

    assert "4111 1111 1111 1111" not in _response(result)["msg"]
    assert DEFAULT_REPLACEMENT in _response(result)["msg"]


@pytest.mark.asyncio
async def test_post_hook_does_not_redact_non_luhn_digit_runs() -> None:
    policy = PiiFilterType()
    # 16 digits but fails Luhn — should NOT be redacted as a credit card.
    context = _ctx({"msg": "Order number 1234567812345678 shipped."})

    result = await policy.post_hook([_default_cfg()], context)

    assert "1234567812345678" in _response(result)["msg"]


@pytest.mark.asyncio
async def test_post_hook_recurses_into_nested_dicts_and_lists() -> None:
    policy = PiiFilterType()
    response = {
        "user": {
            "email": "jane@corp.example",
            "contacts": [
                "other@corp.example",
                {"phone": "555-867-5309"},
            ],
        },
        "status": "ok",
    }
    context = _ctx(response)

    result = await policy.post_hook([_default_cfg()], context)

    redacted = _response(result)
    assert redacted["user"]["email"] == DEFAULT_REPLACEMENT
    assert redacted["user"]["contacts"][0] == DEFAULT_REPLACEMENT
    assert redacted["user"]["contacts"][1]["phone"] == DEFAULT_REPLACEMENT
    assert redacted["status"] == "ok"


@pytest.mark.asyncio
async def test_post_hook_leaves_non_pii_text_untouched() -> None:
    policy = PiiFilterType()
    response = {
        "title": "Weather report",
        "body": "It will be sunny with a high of 72 and a low of 55.",
    }
    context = _ctx(response)

    result = await policy.post_hook([_default_cfg()], context)

    assert result.response == response


@pytest.mark.asyncio
async def test_post_hook_leaves_non_string_values_untouched() -> None:
    policy = PiiFilterType()
    response = {
        "count": 42,
        "ratio": 3.14,
        "is_active": True,
        "missing": None,
        "tags": [1, 2, 3],
    }
    context = _ctx(response)

    result = await policy.post_hook([_default_cfg()], context)

    assert result.response == response


@pytest.mark.asyncio
async def test_post_hook_honours_custom_replacement_token() -> None:
    policy = PiiFilterType()
    cfg = PiiFilterConfig(replacement="<PII>").model_dump()
    context = _ctx({"msg": "Email alice@example.com please"})

    result = await policy.post_hook([cfg], context)

    assert "<PII>" in _response(result)["msg"]
    assert "alice@example.com" not in _response(result)["msg"]


@pytest.mark.asyncio
async def test_post_hook_only_redacts_enabled_categories() -> None:
    policy = PiiFilterType()
    cfg = PiiFilterConfig(categories=["email"]).model_dump()
    context = _ctx({"msg": "Email bob@example.com and phone 555-123-4567"})

    result = await policy.post_hook([cfg], context)

    assert "bob@example.com" not in _response(result)["msg"]
    assert "555-123-4567" in _response(result)["msg"]


@pytest.mark.asyncio
async def test_post_hook_with_no_configs_is_noop() -> None:
    policy = PiiFilterType()
    response = {"email": "test@example.com"}
    context = _ctx(response)

    result = await policy.post_hook([], context)

    assert result.response == {"email": "test@example.com"}


@pytest.mark.asyncio
async def test_post_hook_with_none_response_is_noop() -> None:
    policy = PiiFilterType()
    context = _ctx(None)

    result = await policy.post_hook([_default_cfg()], context)

    assert result.response is None


@pytest.mark.asyncio
async def test_pre_hook_is_passthrough() -> None:
    policy = PiiFilterType()
    response = {"email": "test@example.com"}
    context = _ctx(response)

    result = await policy.pre_hook([_default_cfg()], context)

    assert result is context
    # pre_hook must not touch the response
    assert result.response == {"email": "test@example.com"}


@pytest.mark.asyncio
async def test_validate_config_rejects_unknown_category() -> None:
    with pytest.raises(ValueError, match="Unknown PII categories"):
        await PiiFilterType.validate_config({"categories": ["dob"]})


@pytest.mark.asyncio
async def test_validate_config_accepts_known_categories() -> None:
    cfg = await PiiFilterType.validate_config(
        {"categories": ["email", "phone"], "replacement": "<X>"}
    )

    assert cfg["categories"] == ["email", "phone"]
    assert cfg["replacement"] == "<X>"


@pytest.mark.asyncio
async def test_validate_config_deduplicates_categories() -> None:
    cfg = await PiiFilterType.validate_config(
        {"categories": ["email", "email", "phone"]}
    )

    assert cfg["categories"] == ["email", "phone"]


def test_metadata_accessors() -> None:
    assert PiiFilterType.name() == "pii_filter"
    assert "personally identifiable information" in PiiFilterType.description()
    assert PiiFilterType.icon()
    schema = PiiFilterType.configuration_schema()
    assert "properties" in schema
    assert "categories" in schema["properties"]
    assert "replacement" in schema["properties"]
