"""Model database entities."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from components.endpoints.entities import Endpoint
    from components.tenants.entities import Tenant


class Model(SQLModel, table=True):
    """Model entity representing a configured model instance."""

    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_model_tenant_name"),
        Index("idx_model_tenant_name", "tenant_id", "name"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    name: str = Field(..., description="Model name (unique per tenant)")
    dtype: str = Field(..., description="Model type name (references model type)")
    configuration: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Filled configuration schema",
    )
    summary: str = Field(default="", description="Brief summary of the model")
    tags: str = Field(default="", description="Comma-separated tags")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="models")
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
