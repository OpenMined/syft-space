"""Dataset handlers for business logic."""

from typing import Any

from fastapi import HTTPException, UploadFile
from loguru import logger

from components.dataset_types.interfaces import IngestFile, IngestRequest
from components.dataset_types.registry import DatasetTypeRegistry
from components.shared.domain_types import Context, HealthcheckStatus

from .entities import Dataset
from .repository import DatasetRepository
from .schemas import (
    CreateDatasetRequest,
    DatasetListItem,
    DatasetResponse,
    DatasetTypeInfoResponse,
    HealthcheckResponse,
    IngestFileResponse,
)


class DatasetHandler:
    """Handler for dataset business logic."""

    def __init__(self, registry: DatasetTypeRegistry, repository: DatasetRepository):
        """Initialize the dataset handler.

        Args:
            registry: Dataset type registry
            repository: Dataset repository
        """
        self.registry = registry
        self.repository = repository

    def list_dataset_types(self) -> list[DatasetTypeInfoResponse]:
        """List all available dataset types.

        Returns:
            List of dataset type information
        """
        type_names = self.registry.list_dataset_types()
        types_info = []

        for name in type_names:
            dataset_type_cls = self.registry.get_dataset_type(name)
            types_info.append(
                DatasetTypeInfoResponse(
                    name=dataset_type_cls.name(),
                    description=dataset_type_cls.description(),
                    config_schema=dataset_type_cls.configuration_schema(),
                    icon=dataset_type_cls.icon(),
                    enabled=dataset_type_cls.enabled(),
                )
            )

        return types_info

    def get_dataset_type(self, name: str) -> DatasetTypeInfoResponse:
        """Get information about a specific dataset type.

        Args:
            name: Dataset type name

        Returns:
            Dataset type information

        Raises:
            HTTPException: If dataset type not found
        """
        try:
            dataset_type_cls = self.registry.get_dataset_type(name)
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"Dataset type '{name}' not found"
            ) from None

        return DatasetTypeInfoResponse(
            name=dataset_type_cls.name(),
            description=dataset_type_cls.description(),
            config_schema=dataset_type_cls.configuration_schema(),
            icon=dataset_type_cls.icon(),
            enabled=dataset_type_cls.enabled(),
        )

    def create_dataset(self, request: CreateDatasetRequest) -> DatasetResponse:
        """Create a new dataset.

        Args:
            request: Dataset creation request

        Returns:
            Created dataset

        Raises:
            HTTPException: If dataset type not found or name already exists
        """
        # Verify dataset type exists
        try:
            dataset_type = self.registry.get_dataset_type(request.dtype)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Dataset type '{request.dtype}' not found"
            ) from None

        # Validate configuration
        try:
            dataset_type.validate_configuration(request.configuration)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid configuration: {str(e)}"
            ) from e

        # Check if name already exists
        existing = self.repository.get_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Dataset '{request.name}' already exists"
            )

        # Start provisioner if available
        provisioner_state = None
        provisioner_cls = self.registry.get_provisioner(request.dtype)

        if provisioner_cls is not None:
            try:
                # Add dataset_name to config for unique resource naming
                logger.info(f"Starting provisioner: {request.configuration}")
                provisioner_config = {
                    **request.configuration,
                    "dataset_name": request.name,
                }
                provisioner_state = provisioner_cls.start(provisioner_config)
                logger.info(f"Provisioner started: {provisioner_state}")
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to provision '{request.dtype}' dataset: {str(e)}",
                ) from e

        # Create dataset entity
        dataset = Dataset(
            name=request.name,
            dtype=request.dtype,
            configuration=request.configuration,
            summary=request.summary,
            tags=request.tags,
            provisioner_state=provisioner_state,
        )

        # Save to database
        created = self.repository.create(dataset)

        return DatasetResponse.model_validate(created)

    def list_datasets(self) -> list[DatasetListItem]:
        """List all datasets.

        Returns:
            List of datasets
        """
        datasets = self.repository.get_all()
        return [DatasetListItem.model_validate(ds) for ds in datasets]

    def get_dataset(self, name: str) -> DatasetResponse:
        """Get a specific dataset by name.

        Args:
            name: Dataset name

        Returns:
            Dataset details

        Raises:
            HTTPException: If dataset not found
        """
        dataset = self.repository.get_by_name(name)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        return DatasetResponse.model_validate(dataset)

    def get_dataset_provisioner_status(self, name: str) -> dict:
        """Get provisioner status for a dataset.

        For datasets without provisioners (e.g., remote datasets), all provisioner
        fields will be None/False.

        Args:
            name: Dataset name

        Returns:
            Dictionary with provisioner status info

        Raises:
            HTTPException: If dataset not found
        """
        dataset = self.repository.get_by_name(name)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        provisioner_status = None
        provisioner_running = False

        # Check provisioner status if provisioner state exists
        if dataset.provisioner_state:
            provisioner_cls = self.registry.get_provisioner(dataset.dtype)
            if provisioner_cls is not None:
                try:
                    provisioner_running = provisioner_cls.is_running(
                        dataset.provisioner_state
                    )
                    provisioner_status = provisioner_cls.status(
                        dataset.provisioner_state
                    )
                except Exception as e:
                    from loguru import logger

                    logger.error(f"Failed to check provisioner status: {e}")
                    provisioner_status = "error"

        return {
            "name": dataset.name,
            "type": dataset.dtype,
            "provisioner_running": provisioner_running,
            "provisioner_status": provisioner_status,
            "provisioner_state": dataset.provisioner_state,
        }

    def delete_dataset(self, name: str) -> dict:
        """Delete a dataset by name.

        Args:
            name: Dataset name

        Returns:
            Success message

        Raises:
            HTTPException: If dataset not found
        """
        # Get dataset first to check provisioner state
        dataset = self.repository.get_by_name(name)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        # Stop provisioner if it exists and was provisioned
        if dataset.provisioner_state:
            provisioner_cls = self.registry.get_provisioner(dataset.dtype)
            if provisioner_cls is not None:
                try:
                    provisioner_cls.stop(dataset.provisioner_state)
                except Exception as e:
                    # Log but don't fail - we still want to delete the dataset
                    from loguru import logger

                    logger.error(
                        f"Failed to stop provisioner for dataset '{name}': {e}"
                    )

        # Delete from database
        deleted = self.repository.delete_by_name(name)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        return {"message": f"Successfully deleted dataset '{name}'"}

    def ingest_file(
        self,
        name: str,
        file: UploadFile,
        metadata: dict[str, Any],
        sender_email: str,
    ) -> IngestFileResponse:
        """Ingest a file into dataset.

        Converts FastAPI UploadFile to framework-agnostic IngestFile,
        then delegates to dataset type's ingest method.

        Args:
            name: Dataset name
            file: Uploaded file
            metadata: Enriched metadata dictionary
            sender_email: Email of the user performing ingestion

        Returns:
            Ingestion response with file details

        Raises:
            HTTPException: If dataset not found or ingestion fails
        """
        # Get dataset
        dataset = self.repository.get_by_name(name)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        # Get dataset type
        try:
            dataset_type_cls = self.registry.get_dataset_type(dataset.dtype)
        except KeyError:
            raise HTTPException(
                status_code=500, detail=f"Dataset type '{dataset.dtype}' not registered"
            ) from None

        # Check if enabled
        if not dataset_type_cls.enabled():
            raise HTTPException(
                status_code=503,
                detail=f"Dataset type '{dataset.dtype}' is not enabled. Install required dependencies.",
            )

        # Create dataset type instance
        dataset_instance = dataset_type_cls(dataset.configuration)

        # Convert to domain model (framework-agnostic)
        ingest_file_obj = IngestFile(
            file_handle=file.file,
            filename=file.filename,
            content_type=file.content_type,
            file_size=file.size,
            metadata=metadata,
        )

        # Create domain request
        ingest_request = IngestRequest(files=[ingest_file_obj])

        # Perform ingestion
        ctx = Context(sender=sender_email)
        try:
            dataset_instance.ingest(ctx, ingest_request)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Ingestion failed: {str(e)}"
            ) from e

        return IngestFileResponse(
            filename=file.filename,
            message=f"Successfully ingested file into dataset '{name}'",
        )

    def healthcheck(self, name: str) -> HealthcheckResponse:
        """Check the health of a dataset.

        Args:
            name: Dataset name

        Returns:
            Healthcheck response
        """
        message = ""
        try:
            dataset = self.repository.get_by_name(name)
            if not dataset:
                raise HTTPException(
                    status_code=404, detail=f"Dataset '{name}' not found"
                )

            dataset_type_cls = self.registry.get_dataset_type(dataset.dtype)
            provisioner_cls = self.registry.get_provisioner(dataset.dtype)

            dataset_type = dataset_type_cls(dataset.configuration)
            healthcheck_response = dataset_type.healthcheck()

            message += f"Dataset type healthcheck: {healthcheck_response.message}. "

            if dataset.provisioner_state is not None:
                try:
                    provisioner_status = provisioner_cls.status(
                        dataset.provisioner_state
                    )
                    message += f"Provisioner status: {provisioner_status}. "
                except Exception as e:
                    provisioner_status = HealthcheckStatus.UNHEALTHY
                    message += f"Failed to check provisioner status: {str(e)}"
            else:
                provisioner_status = None

            return HealthcheckResponse(
                dataset_type_status=healthcheck_response.status,
                provisioner_status=provisioner_status,
                message=message,
            )
        except Exception as e:
            message += f"Failed to healthcheck dataset '{name}': {str(e)}"
            return HealthcheckResponse(
                dataset_type_status=HealthcheckStatus.UNHEALTHY,
                provisioner_status=None,
                message=message,
            )
