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

    def __init__(self, dtype: str, current_status: str):
        self.dtype = dtype
        self.current_status = current_status
        super().__init__(f"Provisioner for '{dtype}' is busy ({current_status})")


class InvalidProvisionerTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, dtype: str, from_status: str | None, to_status: str):
        self.dtype = dtype
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Cannot transition provisioner for '{dtype}' from {from_status} to {to_status}"
        )


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


class ProvisionerState(SQLModel, table=True):
    """Provisioner state tracking for shared dataset provisioners.

    One provisioner state per dtype - multiple datasets can share the same provisioner.
    """

    __tablename__ = "provisioner_states"
    __table_args__ = (
        # Unique constraint on dtype ensures one provisioner per dataset type
        UniqueConstraint("dtype", name="uq_provisioner_dtype"),
        Index("idx_provisioner_dtype", "dtype"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    # Dtype-based identification (one provisioner per dtype)
    dtype: str = Field(..., description="Dataset type this provisioner serves")

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
