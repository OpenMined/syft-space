"""Policy database entities."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from components.endpoints.entities import Endpoint
    from components.tenants.entities import Tenant


class Policy(SQLModel, table=True):
    """Policy entity representing a configured policy instance."""

    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("endpoint_id", "name", name="uq_policy_endpoint_name"),
        Index("idx_policy_tenant_endpoint", "tenant_id", "endpoint_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
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
        sa_column=Column(ForeignKey("endpoints.id", ondelete="CASCADE")),
        description="ID of the endpoint this policy is attached to",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="policies")
    endpoint: "Endpoint" = Relationship(
        back_populates="policies",
        sa_relationship_kwargs={"foreign_keys": "[Policy.endpoint_id]"},
    )

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
