"""Dataset database entities."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from components.endpoints.entities import Endpoint
    from components.tenants.entities import Tenant


class Dataset(SQLModel, table=True):
    """Dataset entity representing a configured dataset instance."""

    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dataset_tenant_name"),
        Index("idx_dataset_tenant_name", "tenant_id", "name"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    name: str = Field(..., description="Dataset name (unique per tenant)")
    dtype: str = Field(..., description="Dataset type name (references dataset type)")
    configuration: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Filled configuration schema",
    )
    summary: str = Field(default="", description="Brief summary of the dataset")
    tags: str = Field(default="", description="Comma-separated tags")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    provisioner_state: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Provisioner tracking state (container_id, pid, port, etc.) for re-discovery",
    )

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="datasets")
    endpoints: list["Endpoint"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"foreign_keys": "[Endpoint.dataset_id]"},
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "legal-docs",
                "dtype": "weaviate",
                "configuration": {
                    "httpPort": 8080,
                    "grpcPort": 50051,
                    "collectionName": "LegalDocuments",
                    "ingestionPath": "/data/legal",
                },
                "summary": "Legal documents for analysis",
                "tags": "legal,documents,analysis",
            }
        }
