"""PII filter policy type implementation.

Uses the endpoint's configured AI model to detect and redact personally
identifiable information (PII) from generated responses.  Runs in the
``post_hook`` phase and replaces ``context.response['summary']['message']['content']``
with a sanitized version produced by the model itself.

Only activates when the endpoint has a model — data-only endpoints are
skipped automatically because the endpoint handler only populates
``context.metadata['model_instance']`` when ``endpoint.model_id`` is set.
"""

from typing import Any
from uuid import UUID

from loguru import logger
from pydantic import BaseModel

from syft_space.components.model_types.interfaces import (
    ChatContext,
    ChatMessage,
    ChatParameters,
)
from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
    PolicyMetadataEntry,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator

# The placeholder the model is told to substitute for PII. The
# `spans_redacted` count below greps for this exact token, so the prompt and
# the count stay coupled through this single constant.
_REDACTION_TOKEN = "[REDACTED]"

_PII_SYSTEM_PROMPT = f"""\
You are a PII (Personally Identifiable Information) sanitization assistant.
Review the provided text and replace any PII with the placeholder {_REDACTION_TOKEN}.

Replace the following with {_REDACTION_TOKEN}:
- Full names of real individuals
- Email addresses
- Phone numbers
- Physical or mailing addresses
- Social security numbers or national ID numbers
- Credit card or bank account numbers
- Dates of birth
- Any other directly identifying personal information

Rules:
- Preserve the exact structure, meaning, and tone of the text.
- Do NOT redact general terms, job titles, organisation names, or product names.
- Return ONLY the sanitised text — no commentary, no preamble."""


class PiiFilterConfig(BaseModel):
    """Configuration schema for PII filter policy.

    No required fields — the filter delegates detection to the endpoint's own
    AI model at query time.  An optional ``instructions`` field can append
    domain-specific guidance to the default sanitization prompt.
    """

    instructions: str = ""


class PiiFilterType(BasePolicyType):
    """Policy that redacts PII from model endpoint responses.

    Sends the model's generated response back to the same model with a
    sanitization prompt, then replaces the original content with the
    sanitized version returned by the model.

    Endpoints without a model (data-only) are skipped automatically — the
    endpoint handler only populates ``context.metadata['model_instance']``
    when ``endpoint.model_id`` is set and this policy type is active.
    """

    NAME = "pii_filter"

    def __init__(self) -> None:
        return None

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return (
            "Ask the endpoint's AI model to evaluate its own response and "
            "replace any personally identifiable information (PII) with "
            "[REDACTED] before the response is returned to the caller."
        )

    @classmethod
    def icon(cls) -> str:
        return "🛡️"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return PiiFilterConfig.model_json_schema(schema_generator=ConfigSchemaGenerator)

    async def pre_hook(
        self,
        configs: list[dict[str, Any]],
        context: PolicyContext,  # noqa: ARG002
    ) -> PolicyContext:
        """No pre-request work — PII sanitization only runs on responses."""
        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Ask the model to sanitize PII from the generated response text.

        Extracts the ``summary.message.content`` field, sends it to the
        endpoint's model with a sanitization prompt, and replaces the original
        content with the sanitized version.  Any failure is logged and
        suppressed so that callers always receive a response.
        """
        model_instance = context.metadata.get("model_instance")
        if model_instance is None or context.response is None:
            return context

        original_text = self._extract_text(context.response)
        if not original_text:
            return context

        extra_instructions = ""
        for cfg in configs:
            try:
                validated = PiiFilterConfig(**cfg)
                if validated.instructions:
                    extra_instructions = validated.instructions
                    break
            except Exception:
                pass

        system_prompt = _PII_SYSTEM_PROMPT
        if extra_instructions:
            system_prompt = (
                f"{system_prompt}\n\nAdditional instructions: {extra_instructions}"
            )

        try:
            model_id = UUID(context.metadata["model_id"])
            chat_ctx = ChatContext(
                sender=str(context.sender_email),
                model_id=model_id,
            )
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(
                    role="user",
                    content=f"Sanitize the following text:\n\n{original_text}",
                ),
            ]
            params = ChatParameters(max_tokens=4096)
            result = await model_instance.chat(chat_ctx, messages, params)
            if result.messages:
                sanitized = result.messages[-1].content.strip()
                context.response = self._replace_text(context.response, sanitized)
                spans_redacted = sanitized.count(_REDACTION_TOKEN)
                context.add_policy_metadata(
                    PolicyMetadataEntry(
                        policy_type=self.NAME,
                        kind="transform",
                        status="applied",
                        details={"spans_redacted": spans_redacted},
                    )
                )
        except Exception as exc:
            logger.warning(
                f"PII filter: model sanitization call failed, skipping redaction: {exc}"
            )

        return context

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalise a configuration dictionary."""
        try:
            validated = PiiFilterConfig(**config)
            return validated.model_dump()
        except Exception as exc:
            raise ValueError(f"Invalid pii_filter policy config: {exc}") from exc

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str | None:
        """Extract the model's generated text from the response payload."""
        try:
            return response["summary"]["message"]["content"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def _replace_text(response: dict[str, Any], sanitized: str) -> dict[str, Any]:
        """Replace the message content in the response dict in place."""
        response["summary"]["message"]["content"] = sanitized
        return response
