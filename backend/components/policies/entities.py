"""Policy database entities."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from components.endpoints.entities import Endpoint


class Policy(SQLModel, table=True):
    """Policy entity representing a configured policy instance."""

    __tablename__ = "policies"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(..., description="Name of the policy")
    policy_type: str = Field(
        ..., description="Policy type name (references policy type)"
    )
    configuration: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Filled configuration schema",
    )
    endpoint_id: UUID = Field(
        ...,
        description="ID of the endpoint this policy is attached to",
    )
    # Reverse relationship: all policies for an endpoint
    endpoint: "Endpoint" = Relationship(
        back_populates="policies",
        sa_relationship_kwargs={"foreign_keys": "[Policy.endpoint_id]"},
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Rate limit 100/min",
                "policy_type": "rate_limit",
                "configuration": {
                    "rate": "100/m",
                },
                "endpoint_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
