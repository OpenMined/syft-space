"""Dataset API schemas for request/response models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from syftai_space.components.datasets.entities import ProvisionerStatus
from syftai_space.components.shared.domain_types import HealthcheckStatus

if TYPE_CHECKING:
    from syftai_space.components.datasets.entities import Dataset, ProvisionerState


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

    name: Optional[str] = Field(
        None, description="New dataset name (must be unique per tenant)"
    )
    summary: Optional[str] = Field(None, description="Updated summary")
    tags: Optional[str] = Field(
        None, description="Updated tags (e.g., 'legal,documents')"
    )

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
    state: Optional[dict[str, Any]] = Field(None, description="Provisioner state")
    started_at: Optional[datetime] = Field(None, description="Start time")
    stopped_at: Optional[datetime] = Field(None, description="Stop time")
    error: Optional[str] = Field(None, description="Error message")

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


class DatasetResponse(BaseModel):
    """Response model for dataset details."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Dataset name")
    dtype: str = Field(..., description="Dataset type name")
    configuration: dict[str, Any] = Field(..., description="Configuration")
    summary: str = Field(..., description="Dataset summary")
    tags: str = Field(..., description="Comma-separated tags")
    provisioner_state: Optional[ProvisionerStateResponse] = Field(
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
            configuration=dataset.configuration,
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
    provisioner_status: Optional[ProvisionerStateResponse] = Field(
        None, description="Provisioner status"
    )

    @classmethod
    def from_dataset(
        cls,
        dataset: "Dataset",
        provisioner_state: Optional["ProvisionerState"] = None,
    ) -> "DatasetListItem":
        """Create DatasetListItem from Dataset entity."""
        provisioner_state_response = None
        if provisioner_state:
            provisioner_state_response = ProvisionerStateResponse.model_validate(
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
            provisioner_status=provisioner_state_response,
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
    provisioner_status: Optional[HealthcheckStatus] = Field(
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
    dtype: str = Field(..., description="Dataset type this provisioner serves")
    status: str = Field(
        ..., description="Database status (starting/running/stopped/error)"
    )
    actual_status: Optional[str] = Field(
        None, description="Live status from provisioner (e.g., container running)"
    )
    dataset_count: int = Field(
        ..., description="Number of datasets using this provisioner"
    )
    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Provisioner state (ports, container_id, etc.)",
    )
    started_at: Optional[datetime] = Field(
        None, description="When provisioner was started"
    )
    stopped_at: Optional[datetime] = Field(
        None, description="When provisioner was stopped"
    )
    error: Optional[str] = Field(None, description="Error message if status is ERROR")

    class Config:
        """Pydantic config."""

        from_attributes = True

    @classmethod
    def from_state(
        cls,
        state: "ProvisionerState",
        actual_status: Optional[str],
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
            dtype=state.dtype,
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


# ============== File Browser Schemas ==============


class FileItem(BaseModel):
    """Response model for a single file or directory item."""

    name: str = Field(..., description="File or folder name")
    path: str = Field(..., description="Full absolute path")
    is_dir: bool = Field(..., description="True if this is a directory")
    size: Optional[int] = Field(
        None, description="File size in bytes (None for directories)"
    )
    modified: datetime = Field(..., description="Last modified timestamp")
    extension: Optional[str] = Field(
        None, description="File extension without dot (None for directories)"
    )


class BrowseResponse(BaseModel):
    """Response model for directory browsing."""

    path: str = Field(..., description="Current directory path")
    parent: Optional[str] = Field(
        None, description="Parent directory path (None if at home directory root)"
    )
    items: list[FileItem] = Field(
        default_factory=list, description="List of files and directories"
    )
