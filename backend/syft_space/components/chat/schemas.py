"""Local chat API schemas for request/response models."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """A single message in the conversation."""

    role: Literal["user", "assistant", "system"] = Field(
        ..., description="Role of the message sender"
    )
    content: str = Field(..., description="Message content")


class LocalChatRequest(BaseModel):
    """Request model for local chat (no endpoint/auth required)."""

    model_id: UUID = Field(..., description="ID of the model to chat with")
    dataset_id: UUID | None = Field(
        default=None, description="Optional ID of the data source to search"
    )
    messages: list[ChatMessageRequest] = Field(
        ..., min_length=1, description="Conversation messages"
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt override applied before any references context",
    )
    similarity_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Similarity threshold for matching"
    )
    limit: int = Field(default=5, ge=1, description="Maximum number of search results")
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in references"
    )
    max_tokens: int = Field(default=500, ge=1, description="Maximum tokens to generate")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature for generation"
    )
    stop_sequences: list[str] = Field(
        default_factory=list, description="Stop sequences"
    )
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Presence penalty"
    )
    frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Frequency penalty"
    )


class DocumentResponse(BaseModel):
    """A single reference document from search."""

    document_id: str = Field(..., description="Document identifier")
    content: str = Field(..., description="Document content")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )
    similarity_score: float = Field(..., description="Similarity score")


class ReferencesResponse(BaseModel):
    """Search results from the data source."""

    documents: list[DocumentResponse] = Field(..., description="Matched documents")
    search_engine: str | None = Field(
        default=None, description="Dataset type used for search"
    )


class MessageResponse(BaseModel):
    """The assistant's response message."""

    role: str = Field(..., description="Role (always 'assistant')")
    content: str = Field(..., description="Response content")
    tokens: int = Field(..., description="Token count for this message")


class TokenUsage(BaseModel):
    """Token usage breakdown."""

    prompt_tokens: int = Field(..., description="Prompt tokens used")
    completion_tokens: int = Field(..., description="Completion tokens used")
    total_tokens: int = Field(..., description="Total tokens used")


class SummaryResponse(BaseModel):
    """Model chat completion response."""

    id: str = Field(..., description="Completion ID")
    model: str = Field(..., description="Model used")
    message: MessageResponse = Field(..., description="Assistant message")
    finish_reason: str = Field(..., description="Reason for completion")
    usage: TokenUsage = Field(..., description="Token usage")


class LocalChatResponse(BaseModel):
    """Response from local chat."""

    summary: SummaryResponse | None = Field(
        default=None, description="Model response (if model configured)"
    )
    references: ReferencesResponse | None = Field(
        default=None, description="Search results (if data source configured)"
    )
