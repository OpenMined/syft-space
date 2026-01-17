"""OpenAI model type implementation."""

from typing import Any

from syft_space.components.model_types.interfaces import (
    BaseModelType,
    ChatMessage,
    ChatMessageResult,
    ChatParameters,
    ChatResult,
    TokenUsage,
)
from syft_space.components.shared.domain_types import (
    Context,
    HealthcheckResponse,
    HealthcheckStatus,
)

try:
    from openai import AsyncOpenAI

    enabled = True
except ImportError:
    enabled = False


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
            api_key = config.get("api_key", "")
            base_url = config.get("base_url")
            if base_url:
                self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            else:
                self.client = AsyncOpenAI(api_key=api_key)

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

    async def chat(
        self,
        ctx: Context,
        messages: list[ChatMessage],
        params: ChatParameters | None = None,
    ) -> ChatResult:
        """Chat with the OpenAI model.

        Args:
            ctx: Request context with sender information
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
