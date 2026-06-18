"""Dataset API schemas for request/response models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from syft_space.components.dataset_types.redaction import redact_config
from syft_space.components.datasets.entities import ProvisionerStatus
from syft_space.components.shared.domain_types import HealthcheckStatus
from syft_space.components.sources.interfaces import SourceItem

if TYPE_CHECKING:
    from syft_space.components.datasets.entities import Dataset, ProvisionerState


class DatasetTypeInfoResponse(BaseModel):
    """Response model for dataset type information."""

    name: str = Field(..., description="Name of the dataset type")
    description: str = Field(..., description="Description of the dataset type")
    config_schema: dict[str, Any] = Field(
        ..., description="Configuration schema for the dataset type"
    )
    icon: str = Field(..., description="Icon for the dataset type")
    enabled: bool = Field(..., description="Whether the dataset type is enabled")


class CreateDatasetRequest(BaseModel):
    """Request model for creating a dataset."""

    name: str = Field(..., description="Unique name for the dataset")
    dtype: str = Field(..., description="Dataset type name")
    configuration: dict[str, Any] = Field(
        ..., description="Filled configuration schema"
    )
    summary: str = Field(default="", description="Brief summary of the dataset")
    tags: str = Field(
        default="", description="Comma-separated tags (e.g., 'legal,documents')"
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
                "summary": "Legal documents for RAG analysis",
                "tags": "legal,documents,analysis",
            }
        }


class UpdateDatasetRequest(BaseModel):
    """Request model for updating a dataset (partial update)."""

    name: str | None = Field(
        None, description="New dataset name (must be unique per tenant)"
    )
    summary: str | None = Field(None, description="Updated summary")
    tags: str | None = Field(None, description="Updated tags (e.g., 'legal,documents')")

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateDatasetRequest":
        """Ensure at least one field is provided for update."""
        if self.name is None and self.summary is None and self.tags is None:
            raise ValueError(
                "At least one field (name, summary, or tags) must be provided"
            )
        return self

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "legal-docs-updated",
                "summary": "Updated legal documents for RAG analysis",
                "tags": "legal,documents,analysis,updated",
            }
        }


class ProvisionerStateResponse(BaseModel):
    """Response model for provisioner state."""

    status: ProvisionerStatus = Field(
        default=ProvisionerStatus.STOPPED, description="Provisioner status"
    )
    state: dict[str, Any] | None = Field(None, description="Provisioner state")
    started_at: datetime | None = Field(None, description="Start time")
    stopped_at: datetime | None = Field(None, description="Stop time")
    error: str | None = Field(None, description="Error message")

    class Config:
        """Pydantic config."""

        from_attributes = True


class EndpointListItem(BaseModel):
    """Response model for endpoint in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Endpoint name")
    slug: str = Field(..., description="Unique URL slug")

    class Config:
        """Pydantic config."""

        from_attributes = True


class ProvisionerStatusResponse(BaseModel):
    """Response model for dataset provisioner status."""

    status: ProvisionerStatus = Field(..., description="Provisioner status")
    error: str | None = Field(None, description="Error message")

    class Config:
        """Pydantic config."""

        from_attributes = True


class DatasetResponse(BaseModel):
    """Response model for dataset details."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Dataset name")
    dtype: str = Field(..., description="Dataset type name")
    configuration: dict[str, Any] = Field(..., description="Configuration")
    summary: str = Field(..., description="Dataset summary")
    tags: str = Field(..., description="Comma-separated tags")
    provisioner_state: ProvisionerStateResponse | None = Field(
        None, description="Provisioner state"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    connected_endpoints: list[EndpointListItem] = Field(
        ..., description="Connected endpoints"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True

    @classmethod
    def from_dataset(
        cls,
        dataset: "Dataset",
        provisioner_state: Optional["ProvisionerState"] = None,
    ) -> "DatasetResponse":
        """Create DatasetResponse from Dataset entity.

        Args:
            dataset: Dataset entity
            provisioner_state: Optional ProvisionerState entity

        Returns:
            DatasetResponse with provisioner_state populated if provided
        """
        provisioner_state_response = None
        if provisioner_state:
            provisioner_state_response = ProvisionerStateResponse.model_validate(
                provisioner_state
            )

        return cls(
            id=dataset.id,
            name=dataset.name,
            dtype=dataset.dtype,
            configuration=redact_config(dataset.configuration, dataset.dtype),
            summary=dataset.summary,
            tags=dataset.tags,
            provisioner_state=provisioner_state_response,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
            connected_endpoints=dataset.endpoints,
        )


class DatasetListItem(BaseModel):
    """Response model for dataset in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Dataset name")
    dtype: str = Field(..., description="Dataset type name")
    summary: str = Field(..., description="Dataset summary")
    tags: str = Field(..., description="Comma-separated tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    connected_endpoints: list[EndpointListItem] = Field(
        ..., description="Connected endpoints"
    )
    provisioner_status: ProvisionerStatusResponse | None = Field(
        None, description="Provisioner status"
    )
    configuration: dict[str, Any] = Field(..., description="Dataset configuration")

    @classmethod
    def from_dataset(
        cls,
        dataset: "Dataset",
        provisioner_state: Optional["ProvisionerState"] = None,
    ) -> "DatasetListItem":
        """Create DatasetListItem from Dataset entity."""
        provisioner_status_response = None
        if provisioner_state:
            provisioner_status_response = ProvisionerStatusResponse.model_validate(
                provisioner_state
            )

        return cls(
            id=dataset.id,
            name=dataset.name,
            dtype=dataset.dtype,
            summary=dataset.summary,
            tags=dataset.tags,
            created_at=dataset.created_at,
            connected_endpoints=dataset.endpoints,
            provisioner_status=provisioner_status_response,
            configuration=redact_config(dataset.configuration, dataset.dtype),
        )


class IngestFileResponse(BaseModel):
    """Response for file ingestion."""

    filename: str = Field(..., description="Uploaded filename")
    message: str = Field(..., description="Success message")


class HealthcheckResponse(BaseModel):
    """Response for healthcheck."""

    # dataset type status and provisioner status
    dataset_type_status: HealthcheckStatus = Field(
        ..., description="Dataset type health status"
    )
    provisioner_status: HealthcheckStatus | None = Field(
        None, description="Provisioner health status"
    )
    message: str = Field(..., description="Health message")


# ============== Admin Provisioner Schemas ==============


class ProvisionerInfoResponse(BaseModel):
    """Response model for provisioner information (admin endpoints).

    Used by list_provisioners() and get_provisioner_status_by_dtype().
    Extends ProvisionerStateResponse with additional computed fields.
    """

    id: UUID = Field(..., description="Provisioner state ID")
    vector_store_type: str = Field(
        ..., description="Vector store this provisioner serves"
    )
    status: str = Field(
        ..., description="Database status (starting/running/stopped/error)"
    )
    actual_status: str | None = Field(
        None, description="Live status from provisioner (e.g., container running)"
    )
    dataset_count: int = Field(
        ..., description="Number of datasets using this provisioner"
    )
    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Provisioner state (ports, container_id, etc.)",
    )
    started_at: datetime | None = Field(
        None, description="When provisioner was started"
    )
    stopped_at: datetime | None = Field(
        None, description="When provisioner was stopped"
    )
    error: str | None = Field(None, description="Error message if status is ERROR")

    class Config:
        """Pydantic config."""

        from_attributes = True

    @classmethod
    def from_state(
        cls,
        state: "ProvisionerState",
        actual_status: str | None,
        dataset_count: int,
    ) -> "ProvisionerInfoResponse":
        """Create ProvisionerInfoResponse from ProvisionerState entity.

        Args:
            state: ProvisionerState entity
            actual_status: Live status from provisioner (computed)
            dataset_count: Number of datasets using this provisioner (computed)

        Returns:
            ProvisionerInfoResponse with all fields populated
        """
        return cls(
            id=state.id,
            vector_store_type=state.vector_store_type,
            status=state.status,
            actual_status=actual_status,
            dataset_count=dataset_count,
            state=state.state,
            started_at=state.started_at,
            stopped_at=state.stopped_at,
            error=state.error,
        )


class ProvisionerActionResponse(BaseModel):
    """Response model for provisioner actions (start/stop/delete).

    Used by start_provisioner_by_dtype(), stop_provisioner_by_dtype(),
    and delete_provisioner_by_dtype().
    """

    message: str = Field(..., description="Human-readable result message")
    status: str = Field(
        ...,
        description="Action result status (running/stopped/deleted/not_found/error)",
    )


# ============== Source Browser Schemas ==============


class SourceBrowseRequest(BaseModel):
    """Request model for source-typed browsing.

    Drives the picker pre-create: caller picks a source type, supplies the
    same configuration shape the source uses at ingestion time, and walks
    its containers by passing back ``parent_id`` from prior responses.
    """

    dtype: str = Field(..., description="Source type registered in SOURCE_REGISTRY")
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific configuration (credentials, options)",
    )
    parent_id: str | None = Field(
        default=None,
        description="Container id to list. Null lists the source's top level.",
    )
    cursor: str | None = Field(
        default=None,
        description=(
            "Opaque resume token from a prior response's next_cursor. Null "
            "fetches the first page of the requested level."
        ),
    )


class SourceBrowseResponse(BaseModel):
    """Response model for source-typed browsing."""

    parent_id: str | None = Field(
        default=None, description="Echoes the requested parent_id"
    )
    items: list[SourceItem] = Field(
        default_factory=list,
        description="Containers and leaves at the requested level",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for sources that page. Null when exhausted.",
    )
