"""Endpoint database entities."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlmodel import JSON, Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from components.datasets.entities import Dataset
    from components.models.entities import Model
    from components.policies.entities import Policy


class ResponseType(str, Enum):
    """Type of response for an endpoint."""

    RAW = "raw"  # Only dataset search results
    SUMMARY = "summary"  # Only model chat results
    BOTH = "both"  # Both dataset search + model chat


class Endpoint(SQLModel, table=True):
    """Endpoint entity representing a configured endpoint instance."""

    __tablename__ = "endpoints"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(..., description="Name of the endpoint")
    slug: str = Field(..., unique=True, index=True, description="Unique URL slug")
    description: str = Field(default="", description="Markdown description")
    summary: str = Field(default="", description="Brief summary")
    dataset_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(ForeignKey("datasets.id", ondelete="SET NULL")),
        description="ID of linked dataset (optional)",
    )
    model_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(ForeignKey("models.id", ondelete="SET NULL")),
        description="ID of linked model (optional)",
    )
    response_type: str = Field(
        default=ResponseType.BOTH.value,
        description="Type of response (raw/summary/both)",
    )
    visibility: list = Field(
        default_factory=lambda: ["*"],
        sa_column=Column(JSON),
        description="List of allowed emails/patterns (* for public)",
    )
    published: bool = Field(default=False, description="Whether endpoint is published")
    tags: str = Field(default="", description="Comma-separated tags")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships: access linked dataset and model objects
    dataset: Optional["Dataset"] = Relationship(
        back_populates="endpoints",
        sa_relationship_kwargs={"foreign_keys": "[Endpoint.dataset_id]"},
    )
    model: Optional["Model"] = Relationship(
        back_populates="endpoints",
        sa_relationship_kwargs={"foreign_keys": "[Endpoint.model_id]"},
    )
    policies: list["Policy"] = Relationship(
        back_populates="endpoint",
        sa_relationship_kwargs={"foreign_keys": "[Policy.endpoint_id]"},
    )

    @field_validator("response_type")
    @classmethod
    def validate_response_type(cls, v: str) -> str:
        """Validate response type is valid."""
        if v not in [rt.value for rt in ResponseType]:
            raise ValueError(
                f"response_type must be one of {[rt.value for rt in ResponseType]}"
            )
        return v

    def model_post_init(self, __context: any) -> None:
        """Validate at least one of dataset_id or model_id is provided."""
        if self.dataset_id is None and self.model_id is None:
            raise ValueError("At least one of dataset_id or model_id must be provided")

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
