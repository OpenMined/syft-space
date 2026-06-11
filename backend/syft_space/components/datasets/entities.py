"""Dataset database entities."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
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


class ProvisionerBusyError(Exception):
    """Raised when provisioner is busy (STARTING/STOPPING) and cannot accept new operations."""


class InvalidProvisionerTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""


class Dataset(SQLModel, table=True):
    """Dataset entity representing a configured dataset instance."""

    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dataset_tenant_name"),
        Index("idx_dataset_tenant_name", "tenant_id", "name"),
        Index("idx_dataset_provisioner_state_id", "provisioner_state_id"),
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional FK to shared provisioner state (many datasets can share one provisioner)
    provisioner_state_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("provisioner_states.id", ondelete="SET NULL"), nullable=True
        ),
        description="Reference to shared provisioner state (optional, for local types)",
    )

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="datasets")
    endpoints: list["Endpoint"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={
            "foreign_keys": "[Endpoint.dataset_id]",
            "cascade": "all, delete",
        },
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
    """Provisioner state tracking for shared vector-store provisioners.

    One provisioner state per ``vector_store_type``; every binding that
    composes that vector store shares the row (so e.g. a future
    ``wordpress_chromadb`` binding shares the running chroma subprocess
    with the existing ``local_file`` binding).
    """

    __tablename__ = "provisioner_states"
    __table_args__ = (
        UniqueConstraint("vector_store_type", name="uq_provisioner_vector_store_type"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    # Primary lookup key — name of the vector store this provisioner serves.
    vector_store_type: str = Field(
        ...,
        description="Vector store this provisioner serves (e.g. 'chromadb_local')",
    )

    # Provisioner state including connection config and runtime state
    # Connection fields (httpPort, grpcPort, etc.) are included with keys matching configuration_schema
    state: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Provisioner state including connection config and runtime info (container_id, ports, etc.)",
    )

    # Lifecycle tracking
    status: str = Field(
        default=ProvisionerStatus.STOPPED.value,
        description="Current provisioner lifecycle status",
    )
    started_at: datetime | None = Field(
        default=None, description="When provisioner was last started"
    )
    stopped_at: datetime | None = Field(
        default=None, description="When provisioner was last stopped"
    )
    error: str | None = Field(
        default=None, description="Error message if status is ERROR"
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationship for reverse lookup (provisioner -> datasets)
    datasets: list["Dataset"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Dataset.provisioner_state_id]"}
    )
