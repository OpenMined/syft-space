"""PII Filter policy type — uses a configured model to sanitize response outputs."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from syft_space.components.model_types.interfaces import (
    ChatContext,
    ChatMessage,
    ChatParameters,
)
from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)

if TYPE_CHECKING:
    from syft_space.components.model_types.registry import ModelTypeRegistry
    from syft_space.components.models.repository import ModelRepository

logger = logging.getLogger(__name__)

# Module-level dependency injection — set once at app startup via set_dependencies().
# Follows the same pattern as rate_limit/limiter.py set_storage().
_model_registry: ModelTypeRegistry | None = None
_model_repository: ModelRepository | None = None


def set_dependencies(
    model_registry: ModelTypeRegistry,
    model_repository: ModelRepository,
) -> None:
    """Inject model registry and repository into the PII filter policy.

    Called once from main.py at application startup, after both the model
    registry is populated and the model repository is initialized.

    Args:
        model_registry: The model type registry for instantiating model types
        model_repository: The model repository for looking up model entities
    """
    global _model_registry, _model_repository
    _model_registry = model_registry
    _model_repository = model_repository


class PiiFilterConfig(BaseModel):
    """Configuration schema for the PII filter policy.

    The policy calls the specified model with the given prompt to redact or
    anonymize PII from endpoint response outputs. It targets the LLM-generated
    summary text, raw reference documents, or both.
    """

    model_id: UUID = Field(
        ...,
        description=(
            "UUID of the model to use for PII filtering. "
            "Must reference an existing configured model."
        ),
        json_schema_extra={"format": "model-selector"},
    )
    prompt: str = Field(
        ...,
        min_length=10,
        description=(
            "System prompt with PII filtering instructions for the model. "
            "Example: 'Redact all names, email addresses, phone numbers, and SSNs. "
            "Replace each with [REDACTED]. Return only the processed text, "
            "preserving all non-PII content exactly.'"
        ),
        json_schema_extra={"format": "textarea", "rows": 5},
    )
    target: Literal["summary", "references", "both"] = Field(
        default="both",
        description=(
            "Which part of the response to filter. "
            "'summary' filters the LLM-generated answer text only. "
            "'references' filters the source document content only. "
            "'both' filters summary and all reference documents."
        ),
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description=(
            "Glob patterns for user emails that PII filtering applies to. "
            "Use '*' for all users, '*@company.com' for a domain. "
            "Users not matching any pattern receive unfiltered responses."
        ),
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=32000,
        description=(
            "Maximum output tokens for the PII filter model call. "
            "Should be at least as large as the content being filtered."
        ),
    )
    on_error: Literal["block", "passthrough"] = Field(
        default="block",
        description=(
            "Behavior when the PII filter model call fails. "
            "'block' (default): block the response entirely — safe for compliance. "
            "'passthrough': return the original unfiltered response — prioritizes availability."
        ),
    )


class PiiFilterPolicy(BasePolicyType):
    """PII Filter policy type.

    Post-hook only: calls a configured model with a configurable system prompt to
    redact or anonymize personally identifiable information (PII) from endpoint
    query responses before they reach the requester.

    Targets:
        - summary.message.content  — the LLM-generated answer
        - references.documents[].content  — raw source document chunks
        - or both

    Aggregation: SEQUENTIAL — when multiple PII filter policies are attached to
    an endpoint, each config's output feeds the next. This enables layered
    filtering (e.g., a general PII pass followed by a domain-specific pass).

    pre_hook is a no-op; all processing happens in post_hook.
    """

    NAME = "pii_filter"

    @classmethod
    def name(cls) -> str:
        """Get the name of the policy type."""
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        """Get the description of the policy type."""
        return (
            "Use an AI model to automatically redact or anonymize PII in query responses. "
            "Configure a prompt to instruct the model on what to filter and how to replace it."
        )

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the policy type."""
        return "🛡️"

    @classmethod
    def enabled(cls) -> bool:
        """Check if this policy type is enabled."""
        return True

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema for this policy type."""
        return PiiFilterConfig.model_json_schema(schema_generator=ConfigSchemaGenerator)

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration with UUID serialized as string

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            validated = PiiFilterConfig(**config)
            return validated.model_dump(mode="json")
        except Exception as e:
            raise ValueError(f"Invalid PII filter config: {e}") from e

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Pre-hook (no-op — PII filtering acts on outputs, not inputs).

        Args:
            configs: List of configurations (unused — PII filter is post-hook only)
            context: Policy context with request information

        Returns:
            Unmodified context
        """
        del configs  # explicitly unused — PII filtering is a post-hook concern
        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook: filter PII from response content using the configured model.

        Processes each config sequentially — the filtered output of one config
        becomes the input for the next, enabling layered filtering strategies.

        Args:
            configs: List of configurations for all PII filter policies
            context: Policy context with response to be filtered

        Returns:
            Context with PII-filtered response content

        Raises:
            PolicyViolationError: If filtering fails and on_error='block', or
                if required dependencies are missing
        """
        if not configs or context.response is None:
            return context

        tenant_id_str = context.metadata.get("tenant_id")
        if not tenant_id_str:
            raise PolicyViolationError(
                message="PII filter: tenant_id not found in policy context metadata",
                policy_type=self.NAME,
            )
        tenant_id = UUID(tenant_id_str)

        model_cache: dict[UUID, tuple[Any, Any]] = {}
        for config_dict in configs:
            config = PiiFilterConfig(**config_dict)

            # Skip this config if sender email doesn't match applied_to patterns
            if not matches_any_pattern(str(context.sender_email), config.applied_to):
                continue

            if config.model_id not in model_cache:
                model_cache[config.model_id] = await self._resolve_model(
                    config.model_id, tenant_id
                )
            model_instance, model_entity = model_cache[config.model_id]
            ctx = ChatContext(sender=context.sender_email, model_id=model_entity.id)
            params = ChatParameters(max_tokens=config.max_tokens)

            if config.target == "both":
                await asyncio.gather(
                    self._filter_summary(context, config, model_instance, ctx, params),
                    self._filter_references(
                        context, config, model_instance, ctx, params
                    ),
                )
            elif config.target == "summary":
                await self._filter_summary(context, config, model_instance, ctx, params)
            else:
                await self._filter_references(
                    context, config, model_instance, ctx, params
                )

        return context

    async def _resolve_model(self, model_id: UUID, tenant_id: UUID) -> tuple[Any, Any]:
        """Look up and instantiate the model for this policy.

        Args:
            model_id: UUID of the model to use
            tenant_id: Tenant UUID for scoped lookup

        Returns:
            Tuple of (model_instance, model_entity)

        Raises:
            PolicyViolationError: If dependencies missing, model not found,
                or model type not registered
        """
        if _model_repository is None or _model_registry is None:
            raise PolicyViolationError(
                message=(
                    "PII filter: model dependencies not initialized. "
                    "Ensure set_dependencies() is called at app startup."
                ),
                policy_type=self.NAME,
            )

        model = await _model_repository.get_by_id(model_id, tenant_id)
        if not model:
            raise PolicyViolationError(
                message=f"PII filter: model '{model_id}' not found for this tenant",
                policy_type=self.NAME,
                details={"model_id": str(model_id)},
            )

        try:
            model_type_cls = _model_registry.get_model_type(model.dtype)
        except KeyError:
            raise PolicyViolationError(
                message=f"PII filter: model type '{model.dtype}' is not registered",
                policy_type=self.NAME,
                details={"model_dtype": model.dtype},
            ) from None

        return model_type_cls(model.configuration), model

    async def _filter_summary(
        self,
        context: PolicyContext,
        config: PiiFilterConfig,
        model_instance: Any,
        ctx: ChatContext,
        params: ChatParameters,
    ) -> None:
        """Filter PII from the summary message content in-place.

        Args:
            context: Policy context whose response.summary will be mutated
            config: PII filter configuration
            model_instance: Instantiated model to call
            ctx: Chat context
            params: Chat parameters
        """
        summary = context.response.get("summary") if context.response else None
        if not summary or not isinstance(summary.get("message"), dict):
            return

        original = summary["message"].get("content", "")
        if not original:
            return

        filtered = await self._call_filter(
            original, config.prompt, config.on_error, model_instance, ctx, params
        )
        summary["message"]["content"] = filtered

    async def _filter_references(
        self,
        context: PolicyContext,
        config: PiiFilterConfig,
        model_instance: Any,
        ctx: ChatContext,
        params: ChatParameters,
    ) -> None:
        """Filter PII from each reference document's content in-place.

        Args:
            context: Policy context whose response.references will be mutated
            config: PII filter configuration
            model_instance: Instantiated model to call
            ctx: Chat context
            params: Chat parameters
        """
        references = context.response.get("references") if context.response else None
        if not references or not references.get("documents"):
            return

        docs = references["documents"]
        docs_to_filter = [(i, doc) for i, doc in enumerate(docs) if doc.get("content")]
        if not docs_to_filter:
            return

        filtered = await asyncio.gather(
            *(
                self._call_filter(
                    doc["content"],
                    config.prompt,
                    config.on_error,
                    model_instance,
                    ctx,
                    params,
                )
                for _, doc in docs_to_filter
            )
        )
        for (i, _), content in zip(docs_to_filter, filtered, strict=False):
            docs[i]["content"] = content

    async def _call_filter(
        self,
        text: str,
        prompt: str,
        on_error: str,
        model_instance: Any,
        ctx: ChatContext,
        params: ChatParameters,
    ) -> str:
        """Call the model to filter PII from a text string.

        Sends a system prompt with instructions and the text as the user message.
        Returns the filtered text from the model's response.

        Args:
            text: Original text that may contain PII
            prompt: System prompt with PII filtering instructions
            on_error: 'block' or 'passthrough' behavior on failure
            model_instance: Instantiated model to call
            ctx: Chat context
            params: Chat parameters including max_tokens

        Returns:
            Filtered text with PII redacted/anonymized

        Raises:
            PolicyViolationError: If model call fails and on_error='block'
        """
        messages = [
            ChatMessage(role="system", content=prompt),
            ChatMessage(
                role="user",
                content=(
                    "Process the following text according to your instructions "
                    "and return only the processed result:\n\n" + text
                ),
            ),
        ]
        try:
            result = await model_instance.chat(ctx, messages, params)
            if not result.messages:
                raise ValueError("Model returned no messages")
            return str(result.messages[-1].content)
        except PolicyViolationError:
            raise
        except Exception as e:
            logger.error("PII filter model call failed: %s", e)
            if on_error == "block":
                raise PolicyViolationError(
                    message=(
                        "PII filter failed and is configured to block the response on error. "
                        "Check the filter model configuration."
                    ),
                    policy_type=self.NAME,
                    details={"error": str(e)},
                ) from e
            # passthrough — return original text unfiltered
            logger.warning(
                "PII filter error — returning unfiltered content (on_error=passthrough)"
            )
            return text
