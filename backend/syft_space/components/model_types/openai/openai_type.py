"""OpenAI model type implementation."""

from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from syft_space.components.model_types.interfaces import (
    BaseModelType,
    ChatContext,
    ChatMessage,
    ChatMessageResult,
    ChatParameters,
    ChatResult,
    TokenUsage,
)
from syft_space.components.shared.domain_types import (
    HealthcheckResponse,
    HealthcheckStatus,
)

try:
    from openai import AsyncOpenAI

    enabled = True
except ImportError:
    enabled = False

# Retries for transient failures (429, 5xx, timeouts); the client's built-in
# backoff honors the server's Retry-After header.
MAX_RETRIES = 3
# Per-request timeout in seconds.
REQUEST_TIMEOUT_SECONDS = 600.0


class OpenAIModelType(BaseModelType):
    """OpenAI model type for interacting with OpenAI's API.

    Supports OpenAI's chat completion API and compatible endpoints.
    Can be configured with API key, model selection, and custom base URL.

    Reference: https://platform.openai.com/docs/api-reference
    """

    NAME = "openai"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize OpenAI model type.

        Args:
            config: Configuration dictionary with API key and optional settings
        """
        self.config = config
        if enabled:
            client_kwargs: dict[str, Any] = {
                "api_key": config.get("api_key", ""),
                "max_retries": MAX_RETRIES,
                "timeout": REQUEST_TIMEOUT_SECONDS,
            }
            if config.get("base_url"):
                client_kwargs["base_url"] = config["base_url"]
            self.client = AsyncOpenAI(**client_kwargs)

    @classmethod
    def name(cls) -> str:
        """Get the name of the model type."""
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the model type."""
        return cls.NAME.lower()

    @classmethod
    def description(cls) -> str:
        """Get the description of the model type."""
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the model type."""
        return "🤖"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this model type.

        Returns:
            JSON schema describing configuration requirements
        """
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "OpenAI API Key",
                    "description": "Your OpenAI API key",
                },
                "model": {
                    "type": "string",
                    "title": "Model",
                    "description": "Model to use for chat completions",
                    "default": "gpt-3.5-turbo",
                },
                "base_url": {
                    "type": "string",
                    "title": "Base URL",
                    "description": "Custom base URL for OpenAI-compatible APIs (optional)",
                    "default": "https://api.openai.com/v1",
                },
                "system_prompt": {
                    "type": "string",
                    "title": "System Prompt",
                    "description": "System prompt to use for chat completions",
                    "default": "",
                },
            },
            "required": ["api_key"],
            "order": ["api_key", "model", "base_url"],
        }

    @classmethod
    def redact_configuration(cls, configuration: dict[str, Any]) -> dict[str, Any]:
        """Drop the OpenAI API key from the exposed config."""
        return {k: v for k, v in configuration.items() if k != "api_key"}

    async def chat(
        self,
        ctx: ChatContext,
        messages: list[ChatMessage],
        params: ChatParameters | None = None,
    ) -> ChatResult:
        """Chat with the OpenAI model.

        Args:
            ctx: Chat context with model identifier
            messages: List of chat messages
            params: Optional chat parameters

        Returns:
            ChatResult with generated messages

        Raises:
            ImportError: If openai package is not installed
        """
        if not enabled:
            raise ImportError("OpenAI package is required for chat functionality")

        if params is None:
            params = ChatParameters()

        # Get model from config or use default
        model = self.config.get("model", "gpt-3.5-turbo")

        # Get system prompt from config or use default
        system_prompt = self.config.get("system_prompt", "")

        # Convert ChatMessage to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        # Add system prompt if provided
        if system_prompt:
            openai_messages.insert(0, {"role": "system", "content": system_prompt})

        # Prepare chat completion parameters
        completion_params = {
            "model": model,
            "messages": openai_messages,
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
            "top_p": params.top_p,
            "presence_penalty": params.presence_penalty,
            "frequency_penalty": params.frequency_penalty,
        }

        # Add stop sequences if provided
        if params.stop_sequences:
            completion_params["stop"] = params.stop_sequences

        # Add any extra options
        if params.extra_options:
            completion_params.update(params.extra_options)

        # Call OpenAI API
        response = await self.client.chat.completions.create(**completion_params)

        # Upstream gateways occasionally return an empty completion (all-None
        # payload) on transient failures instead of an HTTP error.
        if not response.choices:
            logger.info(
                f"Model {model} returned a completion with no choices "
                f"(response_id={response.id}), returning empty response"
            )
            return ChatResult(
                id=response.id or "",
                model=response.model or model,
                messages=[],
                finish_reason="error",
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                metadata={"empty_response": True},
            )

        # Extract the first choice (OpenAI returns a list)
        choice = response.choices[0]
        message = choice.message

        # Convert OpenAI response to ChatResult
        # Estimate tokens for the message (OpenAI doesn't provide per-message tokens)
        # We'll use the completion tokens as an approximation for the assistant message
        assistant_message = ChatMessageResult(
            role=message.role or "assistant",
            content=message.content or "",
            tokens=response.usage.completion_tokens if response.usage else 0,
        )

        # Create token usage
        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
        )

        # Create chat result
        return ChatResult(
            id=response.id,
            model=response.model,
            messages=[assistant_message],
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            metadata={"response_id": response.id},
        )

    @classmethod
    def enabled(cls) -> bool:
        """Check if this model type is enabled.

        Returns:
            True if openai package is installed
        """
        return enabled

    async def healthcheck(self) -> HealthcheckResponse:
        """Check if the OpenAI API is healthy.

        Returns:
            HealthcheckResponse indicating health status
        """
        if not enabled:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message="OpenAI package not installed",
            )

        if not hasattr(self, "client"):
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message="OpenAI client not initialized",
            )

        try:
            # Try to make a simple API call to check connectivity
            # Use a minimal request to test the connection
            await self.client.models.list()
            return HealthcheckResponse(
                status=HealthcheckStatus.HEALTHY,
                message="OpenAI API is accessible",
            )
        except Exception as e:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message=f"OpenAI API is unhealthy: {str(e)}",
            )

    async def aclose(self) -> None:
        """Close the underlying HTTP client's connection pool.

        Idempotent: safe to call more than once and when no client was built
        (e.g. the ``openai`` package is unavailable).
        """
        client = getattr(self, "client", None)
        if client is not None:
            await client.close()

    @classmethod
    def get_actions(
        cls,
    ) -> dict[str, Callable[..., Awaitable[dict[str, Any]]]]:
        """Return actions this model type supports.

        Actions are optional capabilities that can be invoked via the
        generic ``POST /models/types/{dtype}/actions/{action_name}`` route.
        """
        return {
            "fetch_available_models": cls._action_fetch_available_models,
        }

    @staticmethod
    async def _action_fetch_available_models(
        *, base_url: str, api_key: str
    ) -> dict[str, Any]:
        """Action wrapper for :meth:`fetch_available_models`.

        Accepts keyword arguments from the request body and returns a
        JSON-serialisable dict.
        """
        raw = await OpenAIModelType.fetch_available_models(
            base_url=base_url, api_key=api_key
        )
        return {"models": raw}

    @staticmethod
    async def fetch_available_models(
        base_url: str, api_key: str
    ) -> list[dict[str, str | None]]:
        """Fetch available models from an OpenAI-compatible API endpoint.

        Args:
            base_url: Base URL of the OpenAI-compatible API
            api_key: API key for authentication

        Returns:
            Sorted list of model dicts with id, name, owned_by fields

        Raises:
            ImportError: If openai package is not installed
            Exception: If the API request fails
        """
        if not enabled:
            raise ImportError("OpenAI package is required")

        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=10.0)
        response = await client.models.list()

        models = [
            {
                "id": m.id,
                "name": getattr(m, "name", None),
                "owned_by": getattr(m, "owned_by", None),
            }
            for m in response.data
        ]
        models.sort(key=lambda m: m["id"])
        return models
