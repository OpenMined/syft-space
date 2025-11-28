"""Dataset API schemas for request/response models."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from syftai_space.components.datasets.entities import ProvisionerStatus
from syftai_space.components.shared.domain_types import HealthcheckStatus


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

    class Config:
        """Pydantic config."""

        from_attributes = True


class DatasetListItem(BaseModel):
    """Response model for dataset in list view."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Dataset name")
    dtype: str = Field(..., description="Dataset type name")
    summary: str = Field(..., description="Dataset summary")
    tags: str = Field(..., description="Comma-separated tags")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


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
