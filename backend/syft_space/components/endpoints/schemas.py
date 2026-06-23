"""Endpoint API schemas for request/response models."""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from syft_space.components.dataset_types.redaction import (
    redact_config as redact_dataset_config,
)
from syft_space.components.endpoints.entities import ResponseType
from syft_space.components.endpoints.interfaces import QueryOutcome
from syft_space.components.model_types.redaction import (
    redact_config as redact_model_config,
)
from syft_space.components.policy_types.interfaces import PolicyMetadataEntry


class PolicyMetadata(BaseModel):
    """Aggregate of every policy's entry for one query, plus the overall outcome.

    Assembled by the endpoints layer (success path and rejection path alike),
    so `outcome` is the endpoints-owned `QueryOutcome` — the full query
    lifecycle, a superset of the policy-produced `PolicyRejection` categories.
    """

    outcome: QueryOutcome = Field(..., description="Overall query outcome")
    entries: list[PolicyMetadataEntry] = Field(default_factory=list)


class RejectionResponse(BaseModel):
    """Body returned when a policy blocks a query (HTTP 402/403).

    Carries the same `policy_metadata` envelope as a successful
    QueryEndpointResponse, so the SDK reads policy outcomes from one typed
    field regardless of status code.
    """

    detail: str = Field(..., description="Human-readable rejection message")
    policy_metadata: PolicyMetadata = Field(
        ..., description="Per-policy metadata, including the rejection reason"
    )


class CreateEndpointRequest(BaseModel):
    """Request model for creating an endpoint."""

    name: str = Field(..., description="Name of the endpoint")
    slug: str = Field(..., description="Unique URL slug")
    description: str = Field(default="", description="Markdown description")
    summary: str = Field(default="", description="Brief summary")
    dataset_id: UUID | None = Field(default=None, description="ID of linked dataset")
    model_id: UUID | None = Field(default=None, description="ID of linked model")
    response_type: str = Field(
        default=ResponseType.BOTH.value,
        description="Type of response (raw/summary/both)",
    )
    published: bool = Field(default=False, description="Whether endpoint is published")
    tags: str = Field(default="", description="Comma-separated tags")
    system_prompt: str | None = Field(
        default=None,
        description=(
            "Optional custom system prompt. When set, overrides the model's "
            "default system prompt on every query to this endpoint."
        ),
    )

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, v: Any) -> str:
        """Validate the slug."""
        if not isinstance(v, str):
            raise ValueError("Slug must be a string")
        if not v:
            raise ValueError("Slug is required")

        _slug = v.lower()
        if len(_slug) < 3:
            raise ValueError("Slug must be at least 3 characters long")
        if len(_slug) > 64:
            raise ValueError("Slug must be at most 64 characters long")
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", _slug):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens "
                "(no leading/trailing/consecutive hyphens)"
            )

        return _slug

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
                "published": True,
                "tags": "legal,qa,documents",
            }
        }


class UpdateEndpointRequest(BaseModel):
    """Request model for updating an endpoint (partial update)."""

    name: str | None = Field(None, description="New endpoint name")
    summary: str | None = Field(None, description="Updated summary")
    description: str | None = Field(None, description="Updated markdown description")
    system_prompt: str | None = Field(
        None,
        description=(
            "Updated custom system prompt. Pass an empty string to clear the "
            "override and fall back to the model's default system prompt."
        ),
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateEndpointRequest":
        """Ensure at least one field is provided for update."""
        if (
            self.name is None
            and self.summary is None
            and self.description is None
            and self.system_prompt is None
        ):
            raise ValueError(
                "At least one field (name, summary, description, or "
                "system_prompt) must be provided"
            )
        return self

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Updated Endpoint Name",
                "summary": "Updated summary text",
                "description": "# Updated Description\nMarkdown content here",
            }
        }


class AttachedModel(BaseModel):
    """Response model for attached model."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Model name")
    dtype: str = Field(..., description="Model type name")
    configuration: dict[str, Any] = Field(..., description="Configuration")

    class Config:
        """Pydantic config."""

        from_attributes = True

    @model_validator(mode="after")
    def _redact_configuration(self) -> "AttachedModel":
        """Strip credentials before the embedded config leaves the API."""
        self.configuration = redact_model_config(self.configuration, self.dtype)
        return self


class AttachedDataset(BaseModel):
    """Response model for attached dataset."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Dataset name")
    summary: str = Field(..., description="Dataset summary")
    dtype: str = Field(..., description="Dataset type")
    configuration: dict[str, Any] = Field(..., description="Configuration")

    class Config:
        """Pydantic config."""

        from_attributes = True

    @model_validator(mode="after")
    def _redact_configuration(self) -> "AttachedDataset":
        """Strip credentials before the embedded config leaves the API."""
        self.configuration = redact_dataset_config(self.configuration, self.dtype)
        return self


class EndpointResponse(BaseModel):
    """Response model for endpoint details."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Endpoint name")
    slug: str = Field(..., description="Unique URL slug")
    description: str = Field(..., description="Markdown description")
    summary: str = Field(..., description="Brief summary")
    response_type: str = Field(..., description="Type of response")
    published: bool = Field(..., description="Whether published")
    tags: str = Field(..., description="Comma-separated tags")
    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt override (null if using model default)",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class EndpointCreateResponse(EndpointResponse):
    """Response model for creating an endpoint."""

    model_id: UUID | None = Field(default=None, description="Model ID")
    dataset_id: UUID | None = Field(default=None, description="Dataset ID")


class AttachedPolicy(BaseModel):
    """Response model for attached policy."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Policy name")
    policy_type: str = Field(..., description="Policy type name")
    configuration: dict[str, Any] = Field(..., description="Configuration")
    wallet_id: UUID | None = Field(
        default=None, description="Wallet ID for payment policies"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


class EndpointDetailResponse(EndpointResponse):
    """Response model for endpoint details."""

    model: AttachedModel | None = Field(default=None, description="Attached model")
    dataset: AttachedDataset | None = Field(
        default=None, description="Attached dataset"
    )
    policies: list[AttachedPolicy] = Field(
        default_factory=list, description="Attached policies"
    )


class EndpointListItem(BaseModel):
    """Response model for endpoint in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Endpoint name")
    slug: str = Field(..., description="Unique URL slug")
    summary: str = Field(..., description="Brief summary")
    response_type: str = Field(..., description="Type of response")
    published: bool = Field(..., description="Whether published")
    tags: str = Field(..., description="Comma-separated tags")
    system_prompt: str | None = Field(
        default=None, description="Custom system prompt override"
    )
    created_at: datetime = Field(..., description="Creation timestamp")

    model: AttachedModel | None = Field(default=None, description="Attached model")
    dataset: AttachedDataset | None = Field(
        default=None, description="Attached dataset"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


# Query Request/Response Models (based on User Flows.md)


class ChatMessageRequest(BaseModel):
    """Chat message in request."""

    role: str = Field(..., description="Role (user/assistant/system)")
    content: str = Field(..., description="Message content")


class QueryEndpointRequest(BaseModel):
    """Request model for querying an endpoint (client input).

    Note: User identity is not provided in the request body.
    It is derived from the SyftHub satellite token in the Authorization header.
    """

    messages: str | list[ChatMessageRequest] = Field(
        ..., description="Messages or conversation string"
    )
    similarity_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Similarity threshold for matching"
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
        default_factory=list, description="Stop sequences"
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
                "messages": [
                    {"role": "user", "content": "What is the capital of France?"}
                ],
                "similarity_threshold": 0.5,
                "limit": 5,
                "max_tokens": 100,
                "temperature": 0.7,
                "extras": {
                    "reference_options": {},
                    "summarize_options": {},
                },
            }
        }


class AuthenticatedQueryRequest(QueryEndpointRequest):
    """Query request enriched with verified sender identity.

    This is created at the route level by combining QueryEndpointRequest
    with the verified sender email from the SyftHub token.
    """

    sender_email: EmailStr = Field(
        ..., description="Verified sender email from SyftHub token"
    )

    @classmethod
    def from_request(
        cls, request: QueryEndpointRequest, sender_email: str
    ) -> "AuthenticatedQueryRequest":
        """Create authenticated request from base request + verified email.

        Args:
            request: Original query request from client
            sender_email: Verified email from SyftHub token

        Returns:
            AuthenticatedQueryRequest with sender identity
        """
        return cls(**request.model_dump(), sender_email=sender_email)


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

    api_version: str | None = Field(default=None, description="API version used")
    response_time_ms: int | None = Field(
        default=None, description="Response time in milliseconds"
    )
    search_engine: str | None = Field(default=None, description="Search engine used")


class SummaryResponse(BaseModel):
    """OpenAI compatible chat completion response."""

    id: str = Field(..., description="Unique identifier for the response")
    model: str = Field(..., description="Model used for generation")
    message: MessageResponse = Field(..., description="Generated message")
    finish_reason: str = Field(..., description="Reason for completion")
    usage: TokenUsage = Field(..., description="Token usage information")
    logprobs: LogProbs | None = Field(default=None, description="Log probabilities")
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


class QueryEndpointResponse(BaseModel):
    """Response model for endpoint query.

    `cost`/`currency` at the top level represent the *total* the user paid
    for this query, summed across all payment policies that applied. They
    are populated additively by policy post-hooks; absence means the query
    was free.
    """

    summary: SummaryResponse | None = Field(
        default=None, description="Generated response summary (if model enabled)"
    )
    references: ReferencesResponse | None = Field(
        default=None,
        description="Reference documents and search results (if dataset enabled)",
    )
    cost: float | None = Field(
        default=None, description="Total cost of this query across all policies"
    )
    currency: str | None = Field(
        default=None, description="Currency of the cost (ISO code)"
    )
    policy_metadata: PolicyMetadata | None = Field(
        default=None,
        description="Per-policy metadata: what each policy charged, to whom, "
        "transaction ids, and rejection reasons",
    )

    @model_validator(mode="after")
    def _cost_currency_paired(self) -> "QueryEndpointResponse":
        if self.cost is not None and self.currency is None:
            raise ValueError("currency is required when cost is set")
        return self

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
                },
                "cost": 0.0035,
                "currency": "USD",
            }
        }


# Publish Request/Response Models


class PublishEndpointRequest(BaseModel):
    """Request model for publishing an endpoint to marketplace(s)."""

    marketplace_ids: list[UUID] | None = Field(
        default=None,
        description="List of marketplace IDs to publish to (required if publish_to_all_marketplaces is False)",
    )
    publish_to_all_marketplaces: bool = Field(
        default=False,
        description="If true, publishes to all active marketplaces (takes precedence over marketplace_ids)",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "marketplace_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "223e4567-e89b-12d3-a456-426614174001",
                ],
                "publish_to_all_marketplaces": False,
            }
        }


class PublishResult(BaseModel):
    """Result of publishing to a single marketplace."""

    marketplace_id: UUID = Field(..., description="Marketplace ID")
    marketplace_name: str = Field(..., description="Marketplace name")
    success: bool = Field(..., description="Whether publishing succeeded")
    message: str | None = Field(default=None, description="Success message")
    error: str | None = Field(default=None, description="Error message if failed")


class PublishEndpointResponse(BaseModel):
    """Response model for endpoint publish operation."""

    endpoint_slug: str = Field(..., description="Slug of the published endpoint")
    results: list[PublishResult] = Field(
        ..., description="Results for each marketplace"
    )


class UnpublishResult(BaseModel):
    """Result of unpublishing from a single marketplace."""

    marketplace_id: UUID = Field(..., description="Marketplace ID")
    marketplace_name: str = Field(..., description="Marketplace name")
    success: bool = Field(..., description="Whether unpublishing succeeded")
    message: str | None = Field(default=None, description="Success message")
    error: str | None = Field(default=None, description="Error message if failed")


# Slug Availability Check Models
class SlugAvailabilityRequest(BaseModel):
    """Request model for checking slug availability."""

    slug: str = Field(..., description="Slug to check for availability")
    marketplace_ids: list[UUID] | None = Field(
        default=None,
        description="Optional list of marketplace IDs to check availability on",
    )
    check_all_marketplaces: bool = Field(
        default=False,
        description="If true, checks all active marketplaces (takes precedence over marketplace_ids)",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "slug": "my-new-endpoint",
                "marketplace_ids": ["123e4567-e89b-12d3-a456-426614174000"],
                "check_all_marketplaces": False,
            }
        }


class MarketplaceAvailabilityResult(BaseModel):
    """Result of checking slug availability on a single marketplace."""

    marketplace_id: UUID = Field(..., description="Marketplace ID")
    available: bool | None = Field(
        ..., description="True if available, False if exists, None if check failed"
    )
    error: str | None = Field(default=None, description="Error message if check failed")


class SlugAvailabilityResponse(BaseModel):
    """Response model for slug availability check."""

    slug: str = Field(..., description="Slug that was checked")
    local_available: bool = Field(
        ..., description="Whether slug is available locally (not in use)"
    )
    marketplaces: list[MarketplaceAvailabilityResult] | None = Field(
        default=None,
        description="Availability results per marketplace (only if marketplace_ids provided)",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "slug": "my-new-endpoint",
                "local_available": True,
                "marketplaces": [
                    {
                        "marketplace_id": "123e4567-e89b-12d3-a456-426614174000",
                        "available": True,
                        "error": None,
                    }
                ],
            }
        }
