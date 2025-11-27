"""Dataset handlers for business logic."""

from typing import Any

from fastapi import HTTPException, UploadFile
from loguru import logger

from syftai_space.components.dataset_types.interfaces import IngestFile, IngestRequest
from syftai_space.components.dataset_types.registry import DatasetTypeRegistry
from syftai_space.components.datasets.entities import Dataset, ProvisionerStatus
from syftai_space.components.datasets.provisioner_state_repository import (
    ProvisionerStateRepository,
)
from syftai_space.components.datasets.repository import DatasetRepository
from syftai_space.components.datasets.schemas import (
    CreateDatasetRequest,
    DatasetListItem,
    DatasetResponse,
    DatasetTypeInfoResponse,
    HealthcheckResponse,
    IngestFileResponse,
)
from syftai_space.components.shared.domain_types import Context, HealthcheckStatus
from syftai_space.components.tenants.entities import Tenant


class DatasetHandler:
    """Handler for dataset business logic."""

    def __init__(
        self,
        registry: DatasetTypeRegistry,
        repository: DatasetRepository,
        provisioner_state_repository: ProvisionerStateRepository,
    ):
        """Initialize the dataset handler.

        Args:
            registry: Dataset type registry
            repository: Dataset repository
            provisioner_state_repository: Provisioner state repository
        """
        self.registry = registry
        self.repository = repository
        self.provisioner_state_repository = provisioner_state_repository

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

    def create_dataset(
        self, request: CreateDatasetRequest, tenant: Tenant
    ) -> DatasetResponse:
        """Create a new dataset.

        Args:
            request: Dataset creation request
            tenant: Tenant context

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

        # Check if name already exists within tenant
        existing = self.repository.get_by_name(request.name, tenant.id)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Dataset '{request.name}' already exists"
            )

        # Create dataset entity (without provisioner state)
        dataset = Dataset(
            name=request.name,
            dtype=request.dtype,
            configuration=request.configuration,
            summary=request.summary,
            tags=request.tags,
            tenant_id=tenant.id,
        )

        # Save to database first
        created = self.repository.create(dataset)

        # Start provisioner if available
        provisioner_cls = self.registry.get_provisioner(request.dtype)
        if provisioner_cls is not None:
            # Add dataset_name to config for unique resource naming
            logger.info(f"Starting provisioner: {request.configuration}")
            provisioner_config = {
                **request.configuration,
                "dataset_name": request.name,
            }

            # Create initial state as STARTING (outside try - if this fails, let it propagate)
            self.provisioner_state_repository.create(
                dataset_id=created.id,
                state={},
                status=ProvisionerStatus.STARTING,
            )

            try:
                # Start the provisioner
                provisioner_state = provisioner_cls.start(provisioner_config)
                logger.info(f"Provisioner started: {provisioner_state}")

                # Update to RUNNING status with actual state
                self.provisioner_state_repository.update(
                    dataset_id=created.id,
                    status=ProvisionerStatus.RUNNING,
                    state=provisioner_state,
                )
            except Exception as e:
                # Update to ERROR status (record exists since create succeeded above)
                self.provisioner_state_repository.update(
                    dataset_id=created.id,
                    status=ProvisionerStatus.ERROR,
                    error=str(e),
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to provision '{request.dtype}' dataset: {str(e)}",
                ) from e

        return DatasetResponse.model_validate(created)

    def list_datasets(self, tenant: Tenant) -> list[DatasetListItem]:
        """List all datasets for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of datasets
        """
        datasets = self.repository.get_all(tenant.id)
        return [DatasetListItem.model_validate(ds) for ds in datasets]

    def get_dataset(self, name: str, tenant: Tenant) -> DatasetResponse:
        """Get a specific dataset by name within a tenant.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Dataset details

        Raises:
            HTTPException: If dataset not found
        """
        dataset = self.repository.get_by_name(name, tenant.id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        return DatasetResponse.model_validate(dataset)

    def get_dataset_provisioner_status(self, name: str, tenant: Tenant) -> dict:
        """Get provisioner status for a dataset.

        For datasets without provisioners (e.g., remote datasets), all provisioner
        fields will be None/False.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Dictionary with provisioner status info

        Raises:
            HTTPException: If dataset not found
        """
        dataset = self.repository.get_by_name(name, tenant.id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        provisioner_status = None
        provisioner_running = False
        provisioner_state_dict = None

        # Check provisioner state from separate table
        provisioner_state = self.provisioner_state_repository.get_by_dataset_id(
            dataset.id
        )

        if provisioner_state:
            provisioner_cls = self.registry.get_provisioner(dataset.dtype)
            if provisioner_cls is not None:
                try:
                    provisioner_running = provisioner_cls.is_running(
                        provisioner_state.state
                    )
                    provisioner_status = provisioner_cls.status(provisioner_state.state)
                except Exception as e:
                    logger.error(f"Failed to check provisioner status: {e}")
                    provisioner_status = "error"

            provisioner_state_dict = {
                "status": provisioner_state.status,
                "state": provisioner_state.state,
                "started_at": provisioner_state.started_at,
                "stopped_at": provisioner_state.stopped_at,
                "error": provisioner_state.error,
            }

        return {
            "name": dataset.name,
            "type": dataset.dtype,
            "provisioner_running": provisioner_running,
            "provisioner_status": provisioner_status,
            "provisioner_state": provisioner_state_dict,
        }

    def delete_dataset(self, name: str, tenant: Tenant) -> dict:
        """Delete a dataset by name within a tenant.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Success message

        Raises:
            HTTPException: If dataset not found
        """
        # Get dataset first to check provisioner state
        dataset = self.repository.get_by_name(name, tenant.id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        # Stop provisioner if it exists
        provisioner_state = self.provisioner_state_repository.get_by_dataset_id(
            dataset.id
        )
        if provisioner_state:
            provisioner_cls = self.registry.get_provisioner(dataset.dtype)
            if provisioner_cls is not None:
                try:
                    provisioner_cls.stop(provisioner_state.state)
                except Exception as e:
                    # Log but don't fail - we still want to delete the dataset
                    logger.error(
                        f"Failed to stop provisioner for dataset '{name}': {e}"
                    )

            # Delete provisioner state (will cascade when dataset is deleted anyway)
            self.provisioner_state_repository.delete_by_dataset_id(dataset.id)

        # Delete from database
        deleted = self.repository.delete_by_name(name, tenant.id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        return {"message": f"Successfully deleted dataset '{name}'"}

    def ingest_file(
        self,
        name: str,
        file: UploadFile,
        metadata: dict[str, Any],
        sender_email: str,
        tenant: Tenant,
    ) -> IngestFileResponse:
        """Ingest a file into dataset.

        Converts FastAPI UploadFile to framework-agnostic IngestFile,
        then delegates to dataset type's ingest method.

        Args:
            name: Dataset name
            file: Uploaded file
            metadata: Enriched metadata dictionary
            sender_email: Email of the user performing ingestion
            tenant: Tenant context

        Returns:
            Ingestion response with file details

        Raises:
            HTTPException: If dataset not found or ingestion fails
        """
        # Get dataset
        dataset = self.repository.get_by_name(name, tenant.id)
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

    def healthcheck(self, name: str, tenant: Tenant) -> HealthcheckResponse:
        """Check the health of a dataset.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Healthcheck response
        """
        message = ""
        try:
            dataset = self.repository.get_by_name(name, tenant.id)
            if not dataset:
                raise HTTPException(
                    status_code=404, detail=f"Dataset '{name}' not found"
                )

            dataset_type_cls = self.registry.get_dataset_type(dataset.dtype)
            provisioner_cls = self.registry.get_provisioner(dataset.dtype)

            dataset_type = dataset_type_cls(dataset.configuration)
            healthcheck_response = dataset_type.healthcheck()

            message += f"Dataset type healthcheck: {healthcheck_response.message}. "

            # Check provisioner state from separate table
            provisioner_state = self.provisioner_state_repository.get_by_dataset_id(
                dataset.id
            )
            if provisioner_state is not None:
                try:
                    provisioner_status = provisioner_cls.status(provisioner_state.state)
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

    def get_all_datasets_with_provisioners(self) -> list[Dataset]:
        """Get all datasets that have provisioners across all tenants.

        Returns:
            List of datasets with provisioner state
        """
        return self.repository.get_all_with_provisioners()

    def start_provisioner_for_dataset(self, dataset: Dataset) -> None:
        """Start provisioner for a specific dataset.

        Args:
            dataset: Dataset entity

        Raises:
            Exception: If provisioner fails to start
        """
        provisioner_cls = self.registry.get_provisioner(dataset.dtype)
        if not provisioner_cls:
            logger.warning(
                f"No provisioner registered for dataset type '{dataset.dtype}'"
            )
            return

        # Get existing provisioner state
        existing_state = self.provisioner_state_repository.get_by_dataset_id(dataset.id)

        # Check if already running
        if existing_state and provisioner_cls.is_running(existing_state.state):
            logger.info(f"Provisioner for dataset '{dataset.name}' is already running")
            return

        # Mark as STARTING using upsert (state might or might not exist - restart scenario)
        # Outside try block - if this fails, let it propagate
        self.provisioner_state_repository.upsert(
            dataset_id=dataset.id,
            state=existing_state.state if existing_state else {},
            status=ProvisionerStatus.STARTING,
        )

        try:
            # Start provisioner
            logger.info(f"Starting provisioner for dataset '{dataset.name}'")
            provisioner_config = {
                **dataset.configuration,
                "dataset_name": dataset.name,
            }
            new_state = provisioner_cls.start(provisioner_config)

            # Update to RUNNING status (record exists since upsert succeeded above)
            self.provisioner_state_repository.update(
                dataset_id=dataset.id,
                status=ProvisionerStatus.RUNNING,
                state=new_state,
            )

            logger.info(
                f"Successfully started provisioner for dataset '{dataset.name}'"
            )
        except Exception as e:
            # Update to ERROR status (record exists since upsert succeeded above)
            self.provisioner_state_repository.update(
                dataset_id=dataset.id,
                status=ProvisionerStatus.ERROR,
                state=existing_state.state if existing_state else {},
                error=str(e),
            )
            logger.error(
                f"Failed to start provisioner for dataset '{dataset.name}': {e}"
            )
            raise

    def stop_provisioner_for_dataset(self, dataset: Dataset) -> None:
        """Stop provisioner for a specific dataset.

        Args:
            dataset: Dataset entity
        """
        provisioner_cls = self.registry.get_provisioner(dataset.dtype)
        if not provisioner_cls:
            logger.warning(
                f"No provisioner registered for dataset type '{dataset.dtype}'"
            )
            return

        # Get provisioner state
        existing_state = self.provisioner_state_repository.get_by_dataset_id(dataset.id)
        if not existing_state:
            logger.info(
                f"No provisioner state found for dataset '{dataset.name}', nothing to stop"
            )
            return

        try:
            # Mark as STOPPING (we know state exists - just fetched it)
            self.provisioner_state_repository.update(
                dataset_id=dataset.id,
                status=ProvisionerStatus.STOPPING,
            )

            logger.info(f"Stopping provisioner for dataset '{dataset.name}'")
            provisioner_cls.stop(existing_state.state)

            # Mark as STOPPED (state exists)
            self.provisioner_state_repository.update(
                dataset_id=dataset.id,
                status=ProvisionerStatus.STOPPED,
            )

            logger.info(
                f"Successfully stopped provisioner for dataset '{dataset.name}'"
            )
        except Exception as e:
            # Mark as ERROR but still consider it stopped (state exists)
            self.provisioner_state_repository.update(
                dataset_id=dataset.id,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            logger.error(
                f"Failed to stop provisioner for dataset '{dataset.name}': {e}"
            )
            # Don't raise - best effort shutdown
