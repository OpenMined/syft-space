"""Endpoint API schemas for request/response models."""

from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from syftai_space.components.endpoints.entities import ResponseType


class CreateEndpointRequest(BaseModel):
    """Request model for creating an endpoint."""

    name: str = Field(..., description="Name of the endpoint")
    slug: str = Field(..., description="Unique URL slug")
    description: str = Field(default="", description="Markdown description")
    summary: str = Field(default="", description="Brief summary")
    dataset_id: Optional[UUID] = Field(default=None, description="ID of linked dataset")
    model_id: Optional[UUID] = Field(default=None, description="ID of linked model")
    response_type: str = Field(
        default=ResponseType.BOTH.value,
        description="Type of response (raw/summary/both)",
    )
    visibility: list[str] = Field(
        default=["*"], description="List of allowed emails/patterns (* for public)"
    )
    published: bool = Field(default=False, description="Whether endpoint is published")
    tags: str = Field(default="", description="Comma-separated tags")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Legal Q&A Endpoint",
                "slug": "legal-qa",
                "description": "# Legal Q&A\\nAnswers questions about legal documents",
                "summary": "Legal document Q&A system",
                "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
                "model_id": "223e4567-e89b-12d3-a456-426614174000",
                "response_type": "both",
                "visibility": ["*"],
                "published": True,
                "tags": "legal,qa,documents",
            }
        }


class EndpointResponse(BaseModel):
    """Response model for endpoint details."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Endpoint name")
    slug: str = Field(..., description="Unique URL slug")
    description: str = Field(..., description="Markdown description")
    summary: str = Field(..., description="Brief summary")
    dataset_id: Optional[UUID] = Field(..., description="Linked dataset ID")
    model_id: Optional[UUID] = Field(..., description="Linked model ID")
    response_type: str = Field(..., description="Type of response")
    visibility: list[str] = Field(..., description="Allowed emails/patterns")
    published: bool = Field(..., description="Whether published")
    tags: str = Field(..., description="Comma-separated tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class EndpointListItem(BaseModel):
    """Response model for endpoint in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Endpoint name")
    slug: str = Field(..., description="Unique URL slug")
    summary: str = Field(..., description="Brief summary")
    response_type: str = Field(..., description="Type of response")
    published: bool = Field(..., description="Whether published")
    tags: str = Field(..., description="Comma-separated tags")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


# Query Request/Response Models (based on User Flows.md)


class ChatMessageRequest(BaseModel):
    """Chat message in request."""

    role: str = Field(..., description="Role (user/assistant/system)")
    content: str = Field(..., description="Message content")


class QueryEndpointRequest(BaseModel):
    """Request model for querying an endpoint."""

    user_email: str = Field(..., description="Email of the user making the request")
    messages: Union[str, list[ChatMessageRequest]] = Field(
        ..., description="Messages or conversation string"
    )
    similarity_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Similarity threshold for matching"
    )
    limit: int = Field(
        default=5, ge=1, description="Maximum number of results to return"
    )
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in response"
    )
    max_tokens: int = Field(default=100, ge=1, description="Maximum tokens to generate")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature for generation"
    )
    stop_sequences: list[str] = Field(
        default_factory=lambda: ["\n"], description="Stop sequences"
    )
    stream: bool = Field(default=False, description="Whether to stream the response")
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Presence penalty"
    )
    frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    extras: dict[str, Any] = Field(
        default_factory=dict, description="Additional options"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "user_email": "user@example.com",
                "messages": [
                    {"role": "user", "content": "What is the capital of France?"}
                ],
                "similarity_threshold": 0.8,
                "limit": 5,
                "max_tokens": 100,
                "temperature": 0.7,
            }
        }


class MessageResponse(BaseModel):
    """Message in the response."""

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


class LogProbs(BaseModel):
    """Log probabilities for tokens."""

    token_logprobs: dict[str, float] = Field(
        ..., description="Log probabilities for each token"
    )


class ProviderInfo(BaseModel):
    """Provider-specific information."""

    api_version: Optional[str] = Field(default=None, description="API version used")
    response_time_ms: Optional[int] = Field(
        default=None, description="Response time in milliseconds"
    )
    search_engine: Optional[str] = Field(default=None, description="Search engine used")


class SummaryResponse(BaseModel):
    """OpenAI compatible chat completion response."""

    id: str = Field(..., description="Unique identifier for the response")
    model: str = Field(..., description="Model used for generation")
    message: MessageResponse = Field(..., description="Generated message")
    finish_reason: str = Field(..., description="Reason for completion")
    usage: TokenUsage = Field(..., description="Token usage information")
    logprobs: Optional[LogProbs] = Field(default=None, description="Log probabilities")
    cost: float = Field(..., description="Cost of the generation")
    provider_info: ProviderInfo = Field(
        ..., description="Provider-specific information"
    )


class DocumentResponse(BaseModel):
    """Reference document."""

    document_id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="Content of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )
    similarity_score: float = Field(
        ..., description="Similarity score for the document"
    )


class ReferencesResponse(BaseModel):
    """Reference documents and search information."""

    documents: list[DocumentResponse] = Field(
        ..., description="List of reference documents"
    )
    provider_info: ProviderInfo = Field(..., description="Search provider information")
    cost: float = Field(..., description="Cost of the search")


class QueryEndpointResponse(BaseModel):
    """Response model for endpoint query."""

    summary: Optional[SummaryResponse] = Field(
        default=None, description="Generated response summary (if model enabled)"
    )
    references: Optional[ReferencesResponse] = Field(
        default=None,
        description="Reference documents and search results (if dataset enabled)",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "summary": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "model": "gpt-4",
                    "message": {
                        "role": "assistant",
                        "content": "The capital of France is Paris.",
                        "tokens": 8,
                    },
                    "finish_reason": "stop",
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 8,
                        "total_tokens": 18,
                    },
                    "cost": 0.0025,
                    "provider_info": {"api_version": "v1", "response_time_ms": 150},
                },
                "references": {
                    "documents": [
                        {
                            "document_id": "doc1",
                            "content": "Paris is the capital of France.",
                            "metadata": {"source": "wikipedia"},
                            "similarity_score": 0.95,
                        }
                    ],
                    "provider_info": {
                        "search_engine": "weaviate",
                        "response_time_ms": 50,
                    },
                    "cost": 0.001,
                },
            }
        }
