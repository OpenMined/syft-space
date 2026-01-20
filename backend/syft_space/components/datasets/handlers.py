"""Dataset handlers for business logic."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from loguru import logger

from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.entities import (
    Dataset,
    InvalidProvisionerTransitionError,
    ProvisionerBusyError,
    ProvisionerState,
    ProvisionerStatus,
)
from syft_space.components.datasets.provisioner_state_repository import (
    ProvisionerStateRepository,
)
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.datasets.schemas import (
    BrowseResponse,
    CreateDatasetRequest,
    DatasetListItem,
    DatasetResponse,
    DatasetTypeInfoResponse,
    FileItem,
    HealthcheckResponse,
    ProvisionerActionResponse,
    ProvisionerInfoResponse,
    UpdateDatasetRequest,
)
from syft_space.components.shared.domain_types import HealthcheckStatus
from syft_space.components.tenants.entities import Tenant


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

    # ============== Private Provisioner Lifecycle Methods ==============

    async def _ensure_provisioner_running(
        self, dtype: str, config: dict[str, Any]
    ) -> ProvisionerState | None:
        """Ensure a provisioner is running for the given dtype.

        This is the single source of truth for starting provisioners. It:
        1. Checks if already running -> returns existing state
        2. Transitions state to STARTING (with guards)
        3. Starts the provisioner
        4. Transitions state to RUNNING with actual state dict

        Args:
            dtype: Dataset type name
            config: Configuration for the provisioner

        Returns:
            ProvisionerState if provisioner exists for dtype, None for remote types

        Raises:
            HTTPException 409: If provisioner is busy (STARTING/STOPPING) or invalid transition
            HTTPException 500: If provisioner fails to start
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if provisioner_cls is None:
            # Remote type - no provisioner needed
            return None

        # Check if already running
        existing = await self.provisioner_state_repository.get_running_by_dtype(dtype)
        if existing:
            logger.info(f"Reusing existing provisioner for dtype '{dtype}'")
            return existing

        # Transition to STARTING (creates or updates, guards checked)
        logger.info(f"Starting provisioner for dtype '{dtype}'")
        try:
            await self.provisioner_state_repository.upsert_status(
                dtype=dtype,
                status=ProvisionerStatus.STARTING,
            )
        except ProvisionerBusyError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except InvalidProvisionerTransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

        try:
            # Start the provisioner
            new_state_dict = await provisioner_cls.start(config)
            logger.info(f"Provisioner started for '{dtype}': {new_state_dict}")

            # Transition to RUNNING with actual state
            return await self.provisioner_state_repository.upsert_status(
                dtype=dtype,
                status=ProvisionerStatus.RUNNING,
                state=new_state_dict,
            )
        except Exception as e:
            logger.error(f"Failed to start provisioner for '{dtype}': {e}")
            await self.provisioner_state_repository.upsert_status(
                dtype=dtype,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start provisioner for '{dtype}': {str(e)}",
            ) from e

    async def _stop_provisioner(self, dtype: str) -> None:
        """Stop a provisioner for the given dtype.

        This is the single source of truth for stopping provisioners. It:
        1. Gets current state
        2. Transitions to STOPPING (with guards)
        3. Stops the provisioner
        4. Transitions to STOPPED

        Args:
            dtype: Dataset type name

        Raises:
            HTTPException 409: If provisioner is busy (STARTING/STOPPING) or invalid transition
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if provisioner_cls is None:
            return  # Remote type - nothing to stop

        state = await self.provisioner_state_repository.get_by_dtype(dtype)
        if not state:
            return  # No provisioner state exists

        if state.status == ProvisionerStatus.STOPPED.value:
            return  # Already stopped

        # Transition to STOPPING (guards checked)
        logger.info(f"Stopping provisioner for dtype '{dtype}'")
        try:
            await self.provisioner_state_repository.upsert_status(
                dtype=dtype,
                status=ProvisionerStatus.STOPPING,
            )
        except ProvisionerBusyError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except InvalidProvisionerTransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

        try:
            # Stop the provisioner
            await provisioner_cls.stop(state.state)
            logger.info(f"Provisioner stopped for '{dtype}'")

            # Transition to STOPPED
            await self.provisioner_state_repository.upsert_status(
                dtype=dtype,
                status=ProvisionerStatus.STOPPED,
            )
        except Exception as e:
            logger.error(f"Failed to stop provisioner for '{dtype}': {e}")
            await self.provisioner_state_repository.upsert_status(
                dtype=dtype,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            raise

    # ============== ProvisionerManager Interface ==============

    async def startup_all_provisioners(self) -> None:
        """Start all provisioners that have datasets attached.

        Called by ProvisionerManager during app startup. Iterates over all
        provisioner states and starts those with attached datasets.

        Also performs recovery for provisioners stuck in transient states
        (STOPPING/STARTING) from interrupted previous shutdown.
        """
        states = await self.provisioner_state_repository.get_all()

        # RECOVERY: Reset stuck STOPPING/STARTING states from interrupted shutdown
        # This can happen if uvicorn reload kills the process during provisioner stop
        recovery_needed = False
        for state in states:
            if state.status in (
                ProvisionerStatus.STOPPING.value,
                ProvisionerStatus.STARTING.value,
            ):
                logger.warning(
                    f"Provisioner '{state.dtype}' stuck in {state.status}, "
                    "resetting to ERROR for recovery"
                )
                await self.provisioner_state_repository.force_status_update(
                    dtype=state.dtype,
                    status=ProvisionerStatus.ERROR,
                    error=f"Reset from stuck {state.status} state during startup recovery",
                )
                recovery_needed = True

        # Re-fetch states after recovery to get updated status
        if recovery_needed:
            states = await self.provisioner_state_repository.get_all()

        for state in states:
            # Skip provisioners with no datasets attached
            dataset_count = (
                await self.provisioner_state_repository.count_datasets_by_provisioner(
                    state.id
                )
            )
            if dataset_count == 0:
                logger.info(
                    f"Skipping provisioner '{state.dtype}' - no datasets attached"
                )
                continue

            # Skip if already running
            if state.status == ProvisionerStatus.RUNNING.value:
                provisioner_cls = self.registry.get_provisioner(state.dtype)
                if provisioner_cls:
                    is_running = await provisioner_cls.is_running(state.state)
                    if is_running:
                        logger.info(f"Provisioner '{state.dtype}' is already running")
                        continue

            try:
                # Use state.state as config (contains connection fields from last run)
                config = state.state.copy() if state.state else {}
                await self._ensure_provisioner_running(state.dtype, config)
            except Exception as e:
                logger.error(f"Failed to start provisioner '{state.dtype}': {e}")
                # Continue with other provisioners

    async def shutdown_all_provisioners(self) -> None:
        """Stop all running provisioners.

        Called by ProvisionerManager during app shutdown. Iterates over all
        provisioner states and stops those that are running.
        """
        states = await self.provisioner_state_repository.get_all()

        for state in states:
            if state.status not in (
                ProvisionerStatus.RUNNING.value,
                ProvisionerStatus.STARTING.value,
            ):
                continue

            try:
                await self._stop_provisioner(state.dtype)
            except Exception as e:
                logger.error(f"Failed to stop provisioner '{state.dtype}': {e}")
                # Continue with other provisioners - best effort shutdown

    # ============== Dataset Type Methods ==============

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

    # ============== Dataset CRUD Methods ==============

    async def create_dataset(
        self, request: CreateDatasetRequest, tenant: Tenant
    ) -> DatasetResponse:
        """Create a new dataset.

        For local (provisioned) types:
        1. Ensures provisioner is running (starts if needed, reuses if exists)
        2. Overrides connection fields from provisioner state
        3. Creates dataset linked to provisioner

        Args:
            request: Dataset creation request
            tenant: Tenant context

        Returns:
            Created dataset

        Raises:
            HTTPException: If dataset type not found, name already exists, or provisioner fails
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
            await dataset_type.validate_configuration(request.configuration)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid configuration: {str(e)}"
            ) from e

        # Check if name already exists within tenant
        existing = await self.repository.get_by_name(request.name, tenant.id)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Dataset '{request.name}' already exists"
            )

        # Ensure provisioner is running (for local types)
        provisioner_state = await self._ensure_provisioner_running(
            request.dtype, request.configuration
        )

        # Build final config, overriding connection fields from provisioner state
        final_config = request.configuration.copy()
        if provisioner_state:
            connection_fields = dataset_type.connection_fields()
            for field in connection_fields:
                if field in provisioner_state.state:
                    final_config[field] = provisioner_state.state[field]
            logger.info(
                f"Connection fields overridden from provisioner state: {connection_fields}"
            )

        # Create dataset entity
        dataset = Dataset(
            name=request.name,
            dtype=request.dtype,
            configuration=final_config,
            summary=request.summary,
            tags=request.tags,
            tenant_id=tenant.id,
            provisioner_state_id=provisioner_state.id if provisioner_state else None,
        )

        # Save to database and build response
        created_dataset = await self.repository.create(dataset)
        return DatasetResponse.from_dataset(created_dataset, provisioner_state)

    async def list_datasets(self, tenant: Tenant) -> list[DatasetListItem]:
        """List all datasets for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of datasets
        """
        datasets = await self.repository.get_all(tenant.id)
        result = []
        for ds in datasets:
            provisioner_state = None
            if ds.provisioner_state_id:
                provisioner_state = await self.provisioner_state_repository.get_by_id(
                    ds.provisioner_state_id
                )
            result.append(DatasetListItem.from_dataset(ds, provisioner_state))
        return result

    async def get_dataset(self, name: str, tenant: Tenant) -> DatasetResponse:
        """Get a specific dataset by name within a tenant.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Dataset details

        Raises:
            HTTPException: If dataset not found
        """
        dataset = await self.repository.get_by_name(name, tenant.id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        provisioner_state = None
        if dataset.provisioner_state_id:
            provisioner_state = await self.provisioner_state_repository.get_by_dtype(
                dataset.dtype
            )

        return DatasetResponse.from_dataset(dataset, provisioner_state)

    async def update_dataset(
        self, name: str, request: UpdateDatasetRequest, tenant: Tenant
    ) -> DatasetResponse:
        """Update a dataset by name within a tenant.

        Args:
            name: Current dataset name
            request: Update request with fields to update
            tenant: Tenant context

        Returns:
            Updated dataset details

        Raises:
            HTTPException: If dataset not found or name already exists
            ValidationError: If no fields provided (handled by FastAPI/Pydantic)
        """
        # Update dataset
        try:
            updated_dataset = await self.repository.update_by_name(
                name,
                tenant.id,
                name_new=request.name,
                summary=request.summary,
                tags=request.tags,
            )
        except ValueError as e:
            # Name conflict or constraint violation
            raise HTTPException(status_code=409, detail=str(e)) from e

        if not updated_dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        # Get provisioner state if exists
        provisioner_state = None
        if updated_dataset.provisioner_state_id:
            provisioner_state = await self.provisioner_state_repository.get_by_dtype(
                updated_dataset.dtype
            )

        return DatasetResponse.from_dataset(updated_dataset, provisioner_state)

    async def delete_dataset(self, name: str, tenant: Tenant) -> dict:
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
        dataset = await self.repository.get_by_name(name, tenant.id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        if dataset.provisioner_state_id:
            logger.info(
                f"Dataset '{name}' was linked to provisioner, keeping provisioner running"
            )

        deleted = await self.repository.delete_by_name(name, tenant.id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        return {"message": f"Successfully deleted dataset '{name}'"}

    async def healthcheck(self, name: str, tenant: Tenant) -> HealthcheckResponse:
        """Check the health of a dataset.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Healthcheck response
        """
        message = ""
        try:
            dataset = await self.repository.get_by_name(name, tenant.id)
            if not dataset:
                raise HTTPException(
                    status_code=404, detail=f"Dataset '{name}' not found"
                )

            dataset_type_cls = self.registry.get_dataset_type(dataset.dtype)
            provisioner_cls = self.registry.get_provisioner(dataset.dtype)

            dataset_type = dataset_type_cls(dataset.configuration)
            healthcheck_response = await dataset_type.healthcheck()

            message += f"Dataset type healthcheck: {healthcheck_response.message}. "

            provisioner_status = None
            if dataset.provisioner_state_id:
                provisioner_state = (
                    await self.provisioner_state_repository.get_by_dtype(dataset.dtype)
                )
                if provisioner_state is not None and provisioner_cls is not None:
                    try:
                        provisioner_status = await provisioner_cls.status(
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

    # ============== Admin Provisioner Endpoints ==============

    async def _get_actual_provisioner_status(
        self, state: ProvisionerState
    ) -> str | None:
        """Get the actual live status from a provisioner.

        Args:
            state: ProvisionerState entity

        Returns:
            Live status string or None/unknown on error
        """
        provisioner_cls = self.registry.get_provisioner(state.dtype)
        if not provisioner_cls or not state.state:
            return None
        try:
            return await provisioner_cls.status(state.state)
        except Exception:
            return "unknown"

    async def list_provisioners(self) -> list[ProvisionerInfoResponse]:
        """List all provisioner states with their status.

        Admin endpoint to view all provisioner states.

        Returns:
            List of provisioner info responses
        """
        states = await self.provisioner_state_repository.get_all()
        result = []

        for state in states:
            actual_status = await self._get_actual_provisioner_status(state)
            dataset_count = (
                await self.provisioner_state_repository.count_datasets_by_provisioner(
                    state.id
                )
            )
            result.append(
                ProvisionerInfoResponse.from_state(state, actual_status, dataset_count)
            )

        return result

    async def start_provisioner_by_dtype(
        self, dtype: str, config: dict[str, Any]
    ) -> ProvisionerActionResponse:
        """Start a provisioner for a specific dtype (admin action).

        Args:
            dtype: Dataset type name
            config: Configuration with connection settings

        Returns:
            Action response with message and status
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if not provisioner_cls:
            raise HTTPException(
                status_code=400,
                detail=f"No provisioner registered for dtype '{dtype}'",
            )

        # Check if already running
        existing = await self.provisioner_state_repository.get_running_by_dtype(dtype)
        if existing:
            return ProvisionerActionResponse(
                message=f"Provisioner for '{dtype}' is already running",
                status="running",
            )

        # Use the shared method
        await self._ensure_provisioner_running(dtype, config)

        return ProvisionerActionResponse(
            message=f"Provisioner for '{dtype}' started",
            status="running",
        )

    async def stop_provisioner_by_dtype(self, dtype: str) -> ProvisionerActionResponse:
        """Stop a provisioner for a specific dtype (admin action).

        Args:
            dtype: Dataset type name

        Returns:
            Action response with message and status
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if not provisioner_cls:
            raise HTTPException(
                status_code=400,
                detail=f"No provisioner registered for dtype '{dtype}'",
            )

        state = await self.provisioner_state_repository.get_by_dtype(dtype)
        if not state:
            return ProvisionerActionResponse(
                message=f"No provisioner found for '{dtype}'",
                status="not_found",
            )

        if state.status == ProvisionerStatus.STOPPED.value:
            return ProvisionerActionResponse(
                message=f"Provisioner for '{dtype}' is already stopped",
                status="stopped",
            )

        try:
            await self._stop_provisioner(dtype)
            return ProvisionerActionResponse(
                message=f"Provisioner for '{dtype}' stopped",
                status="stopped",
            )
        except Exception as e:
            return ProvisionerActionResponse(
                message=f"Error stopping provisioner: {str(e)}",
                status="error",
            )

    async def delete_provisioner_by_dtype(
        self, dtype: str
    ) -> ProvisionerActionResponse:
        """Delete a provisioner for a specific dtype (admin action).

        Stops and deletes the provisioner state record.
        Only succeeds if no datasets are attached.

        Args:
            dtype: Dataset type name

        Returns:
            Action response with message and status

        Raises:
            HTTPException: If datasets are still attached (409 Conflict)
        """
        provisioner_cls = self.registry.get_provisioner(dtype)
        if not provisioner_cls:
            raise HTTPException(
                status_code=400,
                detail=f"No provisioner registered for dtype '{dtype}'",
            )

        existing = await self.provisioner_state_repository.get_by_dtype(dtype)
        if not existing:
            return ProvisionerActionResponse(
                message=f"No provisioner found for '{dtype}'",
                status="not_found",
            )

        # Check if any datasets are attached
        dataset_count = (
            await self.provisioner_state_repository.count_datasets_by_provisioner(
                existing.id
            )
        )
        if dataset_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete provisioner for '{dtype}': {dataset_count} dataset(s) still attached. Delete the datasets first.",
            )

        # Stop if running (use shared method)
        if existing.status in (
            ProvisionerStatus.RUNNING.value,
            ProvisionerStatus.STARTING.value,
        ):
            try:
                await self._stop_provisioner(dtype)
            except Exception as e:
                logger.warning(f"Error stopping provisioner during delete: {e}")

        # Delete the record
        await self.provisioner_state_repository.delete_by_dtype(dtype)

        return ProvisionerActionResponse(
            message=f"Provisioner for '{dtype}' stopped and deleted",
            status="deleted",
        )

    async def get_provisioner_status_by_dtype(
        self, dtype: str
    ) -> ProvisionerInfoResponse:
        """Get detailed status of a provisioner by dtype.

        Args:
            dtype: Dataset type name

        Returns:
            Provisioner info response

        Raises:
            HTTPException: If provisioner not found
        """
        state = await self.provisioner_state_repository.get_by_dtype(dtype)
        if not state:
            raise HTTPException(
                status_code=404, detail=f"Provisioner for '{dtype}' not found"
            )

        actual_status = await self._get_actual_provisioner_status(state)
        dataset_count = (
            await self.provisioner_state_repository.count_datasets_by_provisioner(
                state.id
            )
        )

        return ProvisionerInfoResponse.from_state(state, actual_status, dataset_count)

    # ============== File Browser Methods ==============

    def browse_directory(
        self, path: str = "~", show_hidden: bool = False
    ) -> BrowseResponse:
        """Browse a directory on the filesystem.

        Used for selecting files/folders during dataset creation.
        Restricted to user's home directory for security.

        Args:
            path: Directory path to browse (defaults to home directory)
            show_hidden: Whether to include hidden files (dotfiles)

        Returns:
            BrowseResponse with directory contents

        Raises:
            HTTPException 400: If path is outside home directory
            HTTPException 404: If path does not exist
            HTTPException 403: If permission denied
        """
        home = Path.home()

        # Expand ~ and resolve to absolute path
        try:
            requested = Path(path).expanduser().resolve()
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid path format: {str(e)}"
            ) from e

        # Security check: ensure path is under home directory
        try:
            requested.relative_to(home)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Path must be within home directory",
            ) from None

        # Check path exists
        if not requested.exists():
            raise HTTPException(
                status_code=404, detail=f"Path does not exist: {requested}"
            )

        # Check it's a directory
        if not requested.is_dir():
            raise HTTPException(
                status_code=400, detail=f"Path is not a directory: {requested}"
            )

        # List directory contents
        items: list[FileItem] = []
        try:
            for entry in requested.iterdir():
                # Skip hidden files if not requested
                if not show_hidden and entry.name.startswith("."):
                    continue

                try:
                    stat = entry.stat()
                    is_dir = entry.is_dir()

                    # Get extension for files (not directories)
                    extension = None
                    if not is_dir and entry.suffix:
                        extension = entry.suffix.lstrip(".")

                    items.append(
                        FileItem(
                            name=entry.name,
                            path=str(entry),
                            is_dir=is_dir,
                            size=None if is_dir else stat.st_size,
                            modified=datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ),
                            extension=extension,
                        )
                    )
                except (PermissionError, OSError):
                    # Skip entries we can't stat
                    continue

        except PermissionError as e:
            raise HTTPException(
                status_code=403, detail=f"Permission denied: {requested}"
            ) from e

        # Sort: directories first, then alphabetical
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))

        # Calculate parent path (None if at home directory)
        parent = None
        if requested != home:
            parent = str(requested.parent)

        return BrowseResponse(
            path=str(requested),
            parent=parent,
            items=items,
        )
