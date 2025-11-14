"""Dataset API routes."""

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from .handlers import DatasetHandler
from .schemas import (
    CreateDatasetRequest,
    DatasetListItem,
    DatasetResponse,
    DatasetTypeInfoResponse,
    HealthcheckResponse,
    IngestFileResponse,
)


def build_dataset_routes(handler: DatasetHandler) -> APIRouter:
    """Build the dataset routes.

    Args:
        handler: Dataset handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/datasets", tags=["datasets"])

    def get_handler() -> DatasetHandler:
        """Dependency to get the dataset handler."""
        return handler

    @router.get("/types/", response_model=list[DatasetTypeInfoResponse])
    async def list_dataset_types(
        handler: DatasetHandler = Depends(get_handler),
    ) -> list[DatasetTypeInfoResponse]:
        """List all available dataset types.

        Returns:
            List of dataset type information including configuration schemas
        """
        return handler.list_dataset_types()

    @router.get("/types/{name}", response_model=DatasetTypeInfoResponse)
    async def get_dataset_type(
        name: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetTypeInfoResponse:
        """Get information about a specific dataset type.

        Args:
            name: Dataset type name

        Returns:
            Dataset type information
        """
        return handler.get_dataset_type(name)

    @router.get("/types/{name}/schema", response_model=dict[str, Any])
    async def get_dataset_type_schema(
        name: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> dict[str, Any]:
        """Get the configuration schema for a specific dataset type.

        Args:
            name: Dataset type name

        Returns:
            Configuration schema dictionary
        """
        type_info = handler.get_dataset_type(name)
        return type_info.config_schema

    @router.post("/", response_model=DatasetResponse, status_code=201)
    async def create_dataset(
        request: CreateDatasetRequest,
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetResponse:
        """Create a new dataset.

        Args:
            request: Dataset creation request with configuration

        Returns:
            Created dataset details
        """
        return handler.create_dataset(request)

    @router.get("/", response_model=list[DatasetListItem])
    async def list_datasets(
        handler: DatasetHandler = Depends(get_handler),
    ) -> list[DatasetListItem]:
        """List all datasets.

        Returns:
            List of datasets with summary information
        """
        return handler.list_datasets()

    @router.get("/{name}", response_model=DatasetResponse)
    async def get_dataset(
        name: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetResponse:
        """Get details of a specific dataset.

        Args:
            name: Dataset name

        Returns:
            Dataset details including configuration
        """
        return handler.get_dataset(name)

    @router.post("/{name}/ingest", response_model=IngestFileResponse)
    async def ingest_file(
        name: str,
        file: UploadFile = File(...),
        metadata: str = Form("{}"),
        handler: DatasetHandler = Depends(get_handler),
    ) -> IngestFileResponse:
        """Ingest a single file into dataset.

        Args:
            name: Dataset name
            file: Uploaded file
            metadata: JSON string with custom metadata

        Returns:
            Ingestion result with file details
        """
        # Parse and enrich metadata
        metadata_dict = json.loads(metadata)
        metadata_dict["filename"] = file.filename
        metadata_dict["content_type"] = file.content_type
        metadata_dict["file_size"] = file.size

        # TODO: Get sender_email from auth context when auth is implemented
        sender_email = "admin@example.com"
        return handler.ingest_file(name, file, metadata_dict, sender_email)

    @router.delete("/{name}", response_model=dict[str, str])
    async def delete_dataset(
        name: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a dataset.

        Args:
            name: Dataset name

        Returns:
            Success message
        """
        return handler.delete_dataset(name)

    @router.get("/{name}/health", response_model=HealthcheckResponse)
    async def healthcheck(
        name: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> HealthcheckResponse:
        """Check the health of a dataset.

        Returns:
            Healthcheck response
        """
        return handler.healthcheck(name)

    return router
