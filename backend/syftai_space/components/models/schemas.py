"""Model API schemas for request/response models."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ModelTypeInfoResponse(BaseModel):
    """Response model for model type information."""

    name: str = Field(..., description="Name of the model type")
    description: str = Field(..., description="Description of the model type")
    config_schema: dict[str, Any] = Field(
        ..., description="Configuration schema for the model type"
    )
    icon: str = Field(..., description="Icon for the model type")
    enabled: bool = Field(..., description="Whether the model type is enabled")


class CreateModelRequest(BaseModel):
    """Request model for creating a model."""

    name: str = Field(..., description="Unique name for the model")
    dtype: str = Field(..., description="Model type name")
    configuration: dict[str, Any] = Field(
        ..., description="Filled configuration schema"
    )
    summary: str = Field(default="", description="Brief summary of the model")
    tags: str = Field(
        default="", description="Comma-separated tags (e.g., 'openai,gpt-4')"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "gpt-4-assistant",
                "dtype": "openai",
                "configuration": {
                    "api_key": "sk-...",
                    "model": "gpt-4",
                    "base_url": "https://api.openai.com/v1",
                },
                "summary": "GPT-4 model for assistance",
                "tags": "openai,gpt-4,assistant",
            }
        }


class UpdateModelRequest(BaseModel):
    """Request model for updating a model (partial update)."""

    name: Optional[str] = Field(
        None, description="New model name (must be unique per tenant)"
    )
    summary: Optional[str] = Field(None, description="Updated summary")
    tags: Optional[str] = Field(None, description="Updated tags (e.g., 'openai,gpt-4')")

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateModelRequest":
        """Ensure at least one field is provided for update."""
        if self.name is None and self.summary is None and self.tags is None:
            raise ValueError(
                "At least one field (name, summary, or tags) must be provided"
            )
        return self


class EndpointListItem(BaseModel):
    """Response model for endpoint in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Endpoint name")
    slug: str = Field(..., description="Unique URL slug")

    class Config:
        """Pydantic config."""

        from_attributes = True


class ModelResponse(BaseModel):
    """Response model for model details."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Model name")
    dtype: str = Field(..., description="Model type name")
    configuration: dict[str, Any] = Field(..., description="Configuration")
    summary: str = Field(..., description="Model summary")
    tags: str = Field(..., description="Comma-separated tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class ModelResponseWithEndpoints(ModelResponse):
    connected_endpoints: list[EndpointListItem] = Field(
        ...,
        alias="endpoints",
        serialization_alias="connected_endpoints",
        description="Connected endpoints",
    )

    class Config:
        """Pydantic config."""

        from_attributes = True
        populate_by_name = True


class ModelListItem(BaseModel):
    """Response model for model in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Model name")
    dtype: str = Field(..., description="Model type name")
    configuration: dict[str, Any] = Field(..., description="Configuration")
    summary: str = Field(..., description="Model summary")
    tags: str = Field(..., description="Comma-separated tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    connected_endpoints: list[EndpointListItem] = Field(
        ...,
        alias="endpoints",
        serialization_alias="connected_endpoints",
        description="Connected endpoints",
    )

    class Config:
        """Pydantic config."""

        from_attributes = True
        populate_by_name = True
