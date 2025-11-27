"""Dataset database entities."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from components.endpoints.entities import Endpoint
    from components.tenants.entities import Tenant


class ProvisionerStatus(str, Enum):
    """Provisioner lifecycle status."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


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

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="datasets")
    endpoints: list["Endpoint"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"foreign_keys": "[Endpoint.dataset_id]"},
    )
    provisioner_state: Optional["ProvisionerState"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
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


class ProvisionerState(SQLModel, table=True):
    """Provisioner state tracking for dataset provisioners."""

    __tablename__ = "provisioner_states"
    __table_args__ = (Index("idx_provisioner_dataset_id", "dataset_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    dataset_id: UUID = Field(
        ...,
        sa_column=Column(
            ForeignKey("datasets.id", ondelete="CASCADE"), unique=True, nullable=False
        ),
        description="Dataset this provisioner belongs to (one-to-one)",
    )

    # Flexible state for custom provisioners (container_id, process_id, image, ports, etc.)
    state: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Provisioner-specific state (container_id, pid, ports, etc.)",
    )

    # Lifecycle tracking
    status: str = Field(
        default=ProvisionerStatus.STOPPED.value,
        description="Current provisioner lifecycle status",
    )
    started_at: Optional[datetime] = Field(
        default=None, description="When provisioner was last started"
    )
    stopped_at: Optional[datetime] = Field(
        default=None, description="When provisioner was last stopped"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if status is ERROR"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    dataset: Dataset = Relationship(back_populates="provisioner_state")
