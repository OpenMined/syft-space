"""Model database entities."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from components.endpoints.entities import Endpoint


class Model(SQLModel, table=True):
    """Model entity representing a configured model instance."""

    __tablename__ = "models"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(..., unique=True, index=True, description="Unique model name")
    dtype: str = Field(..., description="Model type name (references model type)")
    configuration: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Filled configuration schema",
    )
    summary: str = Field(default="", description="Brief summary of the model")
    tags: str = Field(default="", description="Comma-separated tags")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Reverse relationship: all endpoints using this model
    endpoints: list["Endpoint"] = Relationship(
        back_populates="model",
        sa_relationship_kwargs={"foreign_keys": "[Endpoint.model_id]"},
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
