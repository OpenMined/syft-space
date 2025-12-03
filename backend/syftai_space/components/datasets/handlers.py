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

    def _get_provisioner_state_for_dataset(self, dataset: Dataset):
        """Get provisioner state for a dataset if it has one."""
        if dataset.provisioner_state_id:
            return self.provisioner_state_repository.get_by_id(
                dataset.provisioner_state_id
            )
        return None

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

        For local (provisioned) types:
        1. Check if provisioner already exists and is running
        2. If yes: link dataset to existing provisioner, override connection config
        3. If no: create new provisioner, start it, then link dataset

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

        # Get provisioner class (None if remote type)
        provisioner_cls = self.registry.get_provisioner(request.dtype)

        # Determine final configuration
        final_config = request.configuration.copy()
        provisioner_state = None

        if provisioner_cls is not None:
            # LOCAL TYPE: Check for existing running provisioner
            existing_state = self.provisioner_state_repository.get_running_by_dtype(
                request.dtype
            )

            if existing_state:
                # Provisioner already running - reuse it
                logger.info(f"Reusing existing provisioner for dtype '{request.dtype}'")
                provisioner_state = existing_state

                # Override connection fields from existing provisioner state
                connection_fields = dataset_type.connection_fields()
                for field in connection_fields:
                    if field in existing_state.state:
                        final_config[field] = existing_state.state[field]

                logger.info(
                    f"Overriding connection fields from state: {existing_state.state}"
                )
            else:
                # No running provisioner - need to start one
                logger.info(f"Starting new provisioner for dtype '{request.dtype}'")

                # Check if stopped provisioner exists (reuse record)
                stopped_state = self.provisioner_state_repository.get_by_dtype(
                    request.dtype
                )

                if stopped_state:
                    # Update existing record to STARTING
                    self.provisioner_state_repository.update(
                        state_id=stopped_state.id,
                        status=ProvisionerStatus.STARTING,
                        state={},
                    )
                    provisioner_state = stopped_state
                else:
                    # Create new provisioner state record
                    provisioner_state = self.provisioner_state_repository.create(
                        dtype=request.dtype,
                        state={},
                        status=ProvisionerStatus.STARTING,
                    )

                try:
                    # Start the provisioner
                    provisioner_config = {**request.configuration}
                    new_state = provisioner_cls.start(provisioner_config)
                    logger.info(f"Provisioner started: {new_state}")

                    # Update to RUNNING status with actual state
                    self.provisioner_state_repository.update(
                        state_id=provisioner_state.id,
                        status=ProvisionerStatus.RUNNING,
                        state=new_state,
                    )
                    # Refresh to get updated record
                    provisioner_state = self.provisioner_state_repository.get_by_dtype(
                        request.dtype
                    )
                except Exception as e:
                    self.provisioner_state_repository.update(
                        state_id=provisioner_state.id,
                        status=ProvisionerStatus.ERROR,
                        error=str(e),
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to provision '{request.dtype}' dataset: {str(e)}",
                    ) from e

        # Create dataset entity with final config
        dataset = Dataset(
            name=request.name,
            dtype=request.dtype,
            configuration=final_config,
            summary=request.summary,
            tags=request.tags,
            tenant_id=tenant.id,
            provisioner_state_id=provisioner_state.id if provisioner_state else None,
        )

        # Save to database
        self.repository.create(dataset)

        # Re-fetch and build response with provisioner state
        created_dataset = self.repository.get_by_name(request.name, tenant.id)
        provisioner_state = self._get_provisioner_state_for_dataset(created_dataset)
        return DatasetResponse.from_dataset(created_dataset, provisioner_state)

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

        provisioner_state = self._get_provisioner_state_for_dataset(dataset)
        return DatasetResponse.from_dataset(dataset, provisioner_state)

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

        # Check provisioner state via the relationship
        if dataset.provisioner_state_id:
            provisioner_state = self.provisioner_state_repository.get_by_id(
                dataset.provisioner_state_id
            )

            if provisioner_state:
                provisioner_cls = self.registry.get_provisioner(dataset.dtype)
                if provisioner_cls is not None:
                    try:
                        provisioner_running = provisioner_cls.is_running(
                            provisioner_state.state
                        )
                        provisioner_status = provisioner_cls.status(
                            provisioner_state.state
                        )
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

        IMPORTANT: Does NOT stop the provisioner. Resource lifecycle is independent.
        Admin must explicitly stop/delete provisioners via separate endpoints.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Success message

        Raises:
            HTTPException: If dataset not found
        """
        # Get dataset first
        dataset = self.repository.get_by_name(name, tenant.id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        # DO NOT stop provisioner - resource lifecycle is independent
        # The provisioner continues running for other datasets of the same type
        # or until an admin explicitly stops it
        if dataset.provisioner_state_id:
            logger.info(
                f"Dataset '{name}' was linked to provisioner state "
                f"{dataset.provisioner_state_id}, keeping provisioner running"
            )

        # Delete from database (just unlinks from provisioner state)
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

            # Check provisioner state via FK
            provisioner_status = None
            if dataset.provisioner_state_id:
                provisioner_state = self.provisioner_state_repository.get_by_id(
                    dataset.provisioner_state_id
                )
                if provisioner_state is not None and provisioner_cls is not None:
                    try:
                        provisioner_status = provisioner_cls.status(
                            provisioner_state.state
                        )
                        message += f"Provisioner status: {provisioner_status}. "
                    except Exception as e:
                        provisioner_status = HealthcheckStatus.UNHEALTHY
                        message += f"Failed to check provisioner status: {str(e)}"

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

    # ============== Admin Provisioner Lifecycle Methods ==============

    def list_provisioners(self) -> list[dict]:
        """List all provisioner states with their status.

        Admin endpoint to view all provisioner states.

        Returns:
            List of provisioner info dictionaries
        """
        states = self.provisioner_state_repository.get_all_provisioner_states()
        result = []
        for state in states:
            provisioner_cls = self.registry.get_provisioner(state.dtype)
            actual_status = None
            if provisioner_cls and state.state:
                try:
                    actual_status = provisioner_cls.status(state.state)
                except Exception:
                    actual_status = "unknown"

            # Count datasets using this provisioner
            dataset_count = (
                self.provisioner_state_repository.count_datasets_by_provisioner(
                    state.id
                )
            )

            result.append(
                {
                    "id": str(state.id),
                    "dtype": state.dtype,
                    "status": state.status,
                    "actual_status": actual_status,
                    "dataset_count": dataset_count,
                    "state": state.state,
                    "started_at": state.started_at.isoformat()
                    if state.started_at
                    else None,
                    "stopped_at": state.stopped_at.isoformat()
                    if state.stopped_at
                    else None,
                    "error": state.error,
                }
            )
        return result

    def start_provisioner_by_dtype(self, dtype: str, config: dict[str, Any]) -> dict:
        """Start a provisioner for a specific dtype (admin action).

        Args:
            dtype: Dataset type name
            config: Configuration with connection settings

        Returns:
            Status dictionary
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if not provisioner_cls:
            raise HTTPException(
                status_code=400, detail=f"No provisioner registered for dtype '{dtype}'"
            )

        # Check if already running
        existing = self.provisioner_state_repository.get_running_by_dtype(dtype)
        if existing:
            return {
                "message": f"Provisioner for '{dtype}' is already running",
                "status": "running",
            }

        # Check if stopped provisioner state exists
        existing_state = self.provisioner_state_repository.get_by_dtype(dtype)

        if existing_state:
            # Update existing to STARTING
            self.provisioner_state_repository.update(
                state_id=existing_state.id,
                status=ProvisionerStatus.STARTING,
                state={},
            )
            state_id = existing_state.id
        else:
            # Create new
            new_state = self.provisioner_state_repository.create(
                dtype=dtype,
                state={},
                status=ProvisionerStatus.STARTING,
            )
            state_id = new_state.id

        try:
            provisioner_state = provisioner_cls.start(config)
            self.provisioner_state_repository.update(
                state_id=state_id,
                status=ProvisionerStatus.RUNNING,
                state=provisioner_state,
            )
            return {
                "message": f"Provisioner for '{dtype}' started",
                "status": "running",
            }
        except Exception as e:
            self.provisioner_state_repository.update(
                state_id=state_id,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to start provisioner: {str(e)}"
            ) from e

    def stop_provisioner_by_dtype(self, dtype: str) -> dict:
        """Stop a provisioner for a specific dtype (admin action).

        Just stops the provisioner but keeps the state record.

        Args:
            dtype: Dataset type name

        Returns:
            Status dictionary
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if not provisioner_cls:
            raise HTTPException(
                status_code=400, detail=f"No provisioner registered for dtype '{dtype}'"
            )

        existing = self.provisioner_state_repository.get_by_dtype(dtype)
        if not existing:
            return {
                "message": f"No provisioner found for '{dtype}'",
                "status": "not_found",
            }

        if existing.status == ProvisionerStatus.STOPPED.value:
            return {
                "message": f"Provisioner for '{dtype}' is already stopped",
                "status": "stopped",
            }

        try:
            self.provisioner_state_repository.update(
                state_id=existing.id,
                status=ProvisionerStatus.STOPPING,
            )

            provisioner_cls.stop(existing.state)

            self.provisioner_state_repository.update(
                state_id=existing.id,
                status=ProvisionerStatus.STOPPED,
            )
            return {
                "message": f"Provisioner for '{dtype}' stopped",
                "status": "stopped",
            }
        except Exception as e:
            self.provisioner_state_repository.update(
                state_id=existing.id,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            return {
                "message": f"Error stopping provisioner: {str(e)}",
                "status": "error",
            }

    def delete_provisioner_by_dtype(self, dtype: str) -> dict:
        """Delete a provisioner for a specific dtype (admin action).

        Stops and deletes the provisioner state record.
        Only succeeds if no datasets are attached.

        Args:
            dtype: Dataset type name

        Returns:
            Status dictionary

        Raises:
            HTTPException: If datasets are still attached (409 Conflict)
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if not provisioner_cls:
            raise HTTPException(
                status_code=400, detail=f"No provisioner registered for dtype '{dtype}'"
            )

        existing = self.provisioner_state_repository.get_by_dtype(dtype)
        if not existing:
            return {
                "message": f"No provisioner found for '{dtype}'",
                "status": "not_found",
            }

        # Check if any datasets are attached
        dataset_count = self.provisioner_state_repository.count_datasets_by_provisioner(
            existing.id
        )
        if dataset_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete provisioner for '{dtype}': {dataset_count} dataset(s) still attached. Delete the datasets first.",
            )

        # Stop if running
        if existing.status in (
            ProvisionerStatus.RUNNING.value,
            ProvisionerStatus.STARTING.value,
        ):
            try:
                provisioner_cls.stop(existing.state)
            except Exception as e:
                logger.warning(f"Error stopping provisioner during delete: {e}")

        # Delete the record
        self.provisioner_state_repository.delete_by_dtype(dtype)

        return {
            "message": f"Provisioner for '{dtype}' stopped and deleted",
            "status": "deleted",
        }

    def get_provisioner_status_by_dtype(self, dtype: str) -> dict:
        """Get detailed status of a provisioner by dtype.

        Args:
            dtype: Dataset type name

        Returns:
            Status dictionary

        Raises:
            HTTPException: If provisioner not found
        """
        existing = self.provisioner_state_repository.get_by_dtype(dtype)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Provisioner for '{dtype}' not found"
            )

        provisioner_cls = self.registry.get_provisioner(dtype)
        actual_status = None
        if provisioner_cls and existing.state:
            try:
                actual_status = provisioner_cls.status(existing.state)
            except Exception:
                actual_status = "unknown"

        dataset_count = self.provisioner_state_repository.count_datasets_by_provisioner(
            existing.id
        )

        return {
            "id": str(existing.id),
            "dtype": existing.dtype,
            "status": existing.status,
            "actual_status": actual_status,
            "dataset_count": dataset_count,
            "state": existing.state,
            "started_at": existing.started_at.isoformat()
            if existing.started_at
            else None,
            "stopped_at": existing.stopped_at.isoformat()
            if existing.stopped_at
            else None,
            "error": existing.error,
        }

    # ============== Methods for ProvisionerManager ==============

    def get_all_provisioner_states_with_datasets(self) -> list:
        """Get all provisioner states that have at least one dataset attached.

        Used by ProvisionerManager during startup.

        Returns:
            List of ProvisionerState records with attached datasets
        """
        return self.provisioner_state_repository.get_all_with_datasets()

    def start_provisioner_for_state(self, state) -> None:
        """Start provisioner for a specific state record.

        Used by ProvisionerManager during startup.

        Args:
            state: ProvisionerState entity

        Raises:
            Exception: If provisioner fails to start
        """
        provisioner_cls = self.registry.get_provisioner(state.dtype)
        if not provisioner_cls:
            logger.warning(f"No provisioner registered for dtype '{state.dtype}'")
            return

        # Check if already running
        if state.state and provisioner_cls.is_running(state.state):
            logger.info(f"Provisioner for '{state.dtype}' is already running")
            return

        # Mark as STARTING
        self.provisioner_state_repository.update(
            state_id=state.id,
            status=ProvisionerStatus.STARTING,
        )

        try:
            # Build config from state (includes connection fields)
            config = state.state.copy() if state.state else {}
            new_state = provisioner_cls.start(config)

            # Update to RUNNING
            self.provisioner_state_repository.update(
                state_id=state.id,
                status=ProvisionerStatus.RUNNING,
                state=new_state,
            )
            logger.info(f"Started provisioner for '{state.dtype}'")
        except Exception as e:
            self.provisioner_state_repository.update(
                state_id=state.id,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            logger.error(f"Failed to start provisioner for '{state.dtype}': {e}")
            raise

    def stop_provisioner_for_state(self, state) -> None:
        """Stop provisioner for a specific state record.

        Used by ProvisionerManager during shutdown.

        Args:
            state: ProvisionerState entity
        """
        provisioner_cls = self.registry.get_provisioner(state.dtype)
        if not provisioner_cls:
            logger.warning(f"No provisioner registered for dtype '{state.dtype}'")
            return

        try:
            self.provisioner_state_repository.update(
                state_id=state.id,
                status=ProvisionerStatus.STOPPING,
            )

            provisioner_cls.stop(state.state)

            self.provisioner_state_repository.update(
                state_id=state.id,
                status=ProvisionerStatus.STOPPED,
            )
            logger.info(f"Stopped provisioner for '{state.dtype}'")
        except Exception as e:
            self.provisioner_state_repository.update(
                state_id=state.id,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            logger.error(f"Failed to stop provisioner for '{state.dtype}': {e}")
            # Don't raise - best effort shutdown
