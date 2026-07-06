"""Model type interfaces and domain models."""

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from syft_space.components.shared.domain_types import Context, HealthcheckResponse


class ChatContext(Context):
    """Context for chat requests."""

    model_id: UUID = Field(..., description="Unique identifier for the model")


class ChatMessage(BaseModel):
    """Domain model for a chat message."""

    role: str = Field(
        ..., description="Role of the message sender (user/assistant/system)"
    )
    content: str = Field(..., description="Content of the message")


class ChatParameters(BaseModel):
    """Domain contract for chat parameters."""

    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature for generation"
    )
    max_tokens: int = Field(default=100, ge=1, description="Maximum tokens to generate")
    stop_sequences: list[str] = Field(
        default_factory=list, description="Stop sequences"
    )
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Presence penalty"
    )
    frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    top_p: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Top-p sampling parameter"
    )
    extra_options: dict[str, Any] = Field(
        default_factory=dict, description="Extra options for the chat"
    )


class ChatMessageResult(BaseModel):
    """A single message in the chat result."""

    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")
    tokens: int = Field(..., description="Number of tokens in the message")


class TokenUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(
        ..., description="Number of tokens in the completion"
    )
    total_tokens: int = Field(..., description="Total number of tokens used")


class ChatResult(BaseModel):
    """Domain contract for chat results."""

    id: str = Field(..., description="Unique identifier for the chat completion")
    model: str = Field(..., description="Model used for generation")
    messages: list[ChatMessageResult] = Field(..., description="Generated messages")
    finish_reason: str = Field(..., description="Reason for completion")
    usage: TokenUsage = Field(..., description="Token usage information")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class BaseModelType(Protocol):
    """Base model type interface.

    All concrete model types must implement this protocol.
    """

    NAME: str

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the model type with configuration.

        Args:
            config: Configuration dictionary for this model type
        """
        ...

    @classmethod
    def name(cls) -> str:
        """Get the name of the model type."""
        ...

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the model type."""
        ...

    @classmethod
    def description(cls) -> str:
        """Get the description of the model type."""
        ...

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the model type."""
        ...

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this model type.

        This will be displayed in the frontend/SDK as configurable values
        when creating a model.

        Returns:
            Dictionary describing the configuration schema
        """
        ...

    @classmethod
    def redact_configuration(cls, configuration: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of the stored configuration safe to expose over the API.

        The default exposes the configuration unchanged. Model types with
        credential fields override this to drop or mask them before the
        configuration is serialized into a response.
        """
        return dict(configuration)

    async def chat(
        self,
        ctx: ChatContext,
        messages: list[ChatMessage],
        params: ChatParameters | None = None,
    ) -> ChatResult:
        """Chat with the model.

        Args:
            ctx: Chat context with model identifier
            messages: List of chat messages
            params: Optional chat parameters

        Returns:
            ChatResult with generated messages
        """
        ...

    async def healthcheck(self) -> HealthcheckResponse:
        """Check if the model type is healthy.

        Returns:
            HealthcheckResponse indicating health status
        """
        ...

    async def aclose(self) -> None:
        """Release any resources (e.g. HTTP connection pools).

        Instances are built per request, so the caller must close them after
        use or their underlying network transports leak until GC. Must be
        idempotent.
        """
        ...

    @classmethod
    def enabled(cls) -> bool:
        """Check if this model type is enabled.

        Returns:
            True if enabled, False otherwise
        """
        ...


class BaseModelTypeProvisioner(Protocol):
    """Base model type provisioner interface.

    Provisioners handle lifecycle management of model infrastructure.
    """

    NAME: str

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the provisioner with configuration.

        Args:
            config: Configuration dictionary for this provisioner
        """
        ...

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        ...

    async def start(self, config: dict[str, Any]) -> None:
        """Start the model type provisioner.

        Args:
            config: Configuration for starting the provisioner
        """
        ...

    async def stop(self) -> None:
        """Stop the model type provisioner."""
        ...

    async def status(self) -> str:
        """Get the status of the provisioner.

        Returns:
            String describing the current status
        """
        ...
