"""Dataset handlers for business logic."""

import re
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from loguru import logger

from syft_space.components.dataset_types.interfaces import IngestableDatasetType
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
    CreateDatasetRequest,
    DatasetListItem,
    DatasetResponse,
    DatasetTypeInfoResponse,
    HealthcheckResponse,
    ProvisionerActionResponse,
    ProvisionerInfoResponse,
    SourceBrowseResponse,
    UpdateDatasetRequest,
)
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.shared.domain_types import HealthcheckStatus
from syft_space.components.shared.ingest_types import IngestContext
from syft_space.components.sources.registry import SOURCE_REGISTRY
from syft_space.components.tenants.entities import Tenant
from syft_space.components.vector_stores.chunking import PAGE_IMAGES_BASE_DIR
from syft_space.components.vector_stores.interfaces import BaseVectorStoreProvisioner
from syft_space.components.vector_stores.registry import VECTOR_STORE_REGISTRY


class DatasetHandler:
    """Handler for dataset business logic."""

    def __init__(
        self,
        registry: DatasetTypeRegistry,
        repository: DatasetRepository,
        provisioner_state_repository: ProvisionerStateRepository,
        endpoint_repository: EndpointRepository | None = None,
    ):
        """Initialize the dataset handler.

        Args:
            registry: Dataset type registry
            repository: Dataset repository
            provisioner_state_repository: Provisioner state repository
            endpoint_repository: Endpoint repository (used to guard against deleting datasets in use)
        """
        self.registry = registry
        self.repository = repository
        self.provisioner_state_repository = provisioner_state_repository
        self.endpoint_repository = endpoint_repository

    # ============== Private Provisioner Lifecycle Methods ==============

    def _get_provisioner_cls(
        self, vector_store_type: str
    ) -> type[BaseVectorStoreProvisioner] | None:
        """Resolve the provisioner class for a vector store.

        Provisioners are owned by ``BaseVectorStore`` (one provisioner
        per vector store type, shared across every binding that
        composes that vector store). Returns ``None`` for unknown or
        read-only (provisioner-less) vector stores — callers treat
        both as "skip the provisioner step".

        Concrete vector stores MUST declare ``PROVISIONER_CLS`` (set to
        ``None`` when no provisioner is needed); a missing declaration
        surfaces here as ``AttributeError`` so the misconfiguration
        fails loudly rather than silently skipping the provisioner.
        """
        try:
            vector_store_cls = VECTOR_STORE_REGISTRY.get(vector_store_type)
        except KeyError:
            return None
        return vector_store_cls.PROVISIONER_CLS

    def _get_vector_store_type(self, dtype: str) -> str | None:
        """Resolve the vector store name for ``dtype``.

        The ``provisioner_states`` row is keyed by ``vector_store_type``
        (e.g. ``"chromadb_local"``); the handler accepts the binding
        name (``dtype``, e.g. ``"local_file"``) at its public surface
        and translates here. Returns ``None`` when the dtype is unknown.
        """
        try:
            dataset_type_cls = self.registry.get_dataset_type(dtype)
        except KeyError:
            return None
        return dataset_type_cls.VECTOR_STORE_CLS.NAME

    async def _ensure_provisioner_running(
        self, vector_store_type: str, config: dict[str, Any]
    ) -> ProvisionerState | None:
        """Ensure a provisioner is running for the given vector store.

        This is the single source of truth for starting provisioners. It:
        1. Checks if already running -> returns existing state
        2. Transitions state to STARTING (with guards)
        3. Starts the provisioner
        4. Transitions state to RUNNING with actual state dict

        Args:
            vector_store_type: Vector store name (e.g. ``"chromadb_local"``)
            config: Configuration for the provisioner

        Returns:
            ProvisionerState if the vector store has a provisioner, ``None``
            for read-only / unknown vector stores.

        Raises:
            HTTPException 409: If provisioner is busy (STARTING/STOPPING) or invalid transition
            HTTPException 500: If provisioner fails to start
        """
        provisioner_cls = self._get_provisioner_cls(vector_store_type)
        if provisioner_cls is None:
            # Read-only vector store - no provisioner needed
            return None

        # Check if already running (verify actual process, not just DB state)
        existing = (
            await self.provisioner_state_repository.get_running_by_vector_store_type(
                vector_store_type
            )
        )
        if existing:
            state = existing.state or {}
            if await provisioner_cls.is_running(state):
                # Process is alive, but the server may still be booting
                # (e.g. after an app restart the OS process survives but
                # ChromaDB's HTTP server hasn't finished starting yet).
                # Wait for it to be healthy before returning.
                try:
                    await provisioner_cls.wait_until_ready(state)
                except Exception as exc:
                    logger.warning(
                        f"Provisioner for '{vector_store_type}' process alive but "
                        f"not ready ({exc}), restarting..."
                    )
                    await provisioner_cls.stop(state)
                    # Force-reset: normal RUNNING→STOPPED transition is
                    # not allowed by the state machine (must go via STOPPING).
                    # This is a recovery path so we bypass the guards.
                    await self.provisioner_state_repository.force_status_update(
                        vector_store_type=vector_store_type,
                        status=ProvisionerStatus.STOPPED,
                    )
                    # Fall through to start a new one
                else:
                    logger.info(
                        f"Reusing existing provisioner for '{vector_store_type}'"
                    )
                    return existing
            else:
                logger.warning(
                    f"Provisioner for '{vector_store_type}' marked as running in DB "
                    f"but process is dead, restarting..."
                )
                # Force-reset: normal RUNNING→STOPPED transition is
                # not allowed by the state machine (must go via STOPPING).
                # This is a recovery path so we bypass the guards.
                await self.provisioner_state_repository.force_status_update(
                    vector_store_type=vector_store_type,
                    status=ProvisionerStatus.STOPPED,
                )

        # Transition to STARTING (creates or updates, guards checked)
        logger.info(f"Starting provisioner for '{vector_store_type}'")
        try:
            await self.provisioner_state_repository.upsert_status(
                vector_store_type=vector_store_type,
                status=ProvisionerStatus.STARTING,
            )
        except ProvisionerBusyError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except InvalidProvisionerTransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

        try:
            # Start the provisioner
            new_state_dict = await provisioner_cls.start(config)
            logger.info(
                f"Provisioner started for '{vector_store_type}': {new_state_dict}"
            )

            # Transition to RUNNING with actual state
            return await self.provisioner_state_repository.upsert_status(
                vector_store_type=vector_store_type,
                status=ProvisionerStatus.RUNNING,
                state=new_state_dict,
            )
        except Exception as e:
            logger.exception(
                f"Failed to start provisioner for '{vector_store_type}': {e}"
            )
            await self.provisioner_state_repository.upsert_status(
                vector_store_type=vector_store_type,
                status=ProvisionerStatus.ERROR,
                error=str(e),
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start provisioner for '{vector_store_type}': {str(e)}",
            ) from e

    async def _stop_provisioner(self, vector_store_type: str) -> None:
        """Stop a provisioner for the given vector store.

        This is the single source of truth for stopping provisioners. It:
        1. Gets current state
        2. Transitions to STOPPING (with guards)
        3. Stops the provisioner
        4. Transitions to STOPPED

        Args:
            vector_store_type: Vector store name (e.g. ``"chromadb_local"``)

        Raises:
            HTTPException 409: If provisioner is busy (STARTING/STOPPING) or invalid transition
        """
        provisioner_cls = self._get_provisioner_cls(vector_store_type)
        if provisioner_cls is None:
            return  # Read-only vector store - nothing to stop

        state = await self.provisioner_state_repository.get_by_vector_store_type(
            vector_store_type
        )
        if not state:
            return  # No provisioner state exists

        if state.status == ProvisionerStatus.STOPPED.value:
            return  # Already stopped

        # Transition to STOPPING (guards checked)
        logger.info(f"Stopping provisioner for '{vector_store_type}'")
        try:
            await self.provisioner_state_repository.upsert_status(
                vector_store_type=vector_store_type,
                status=ProvisionerStatus.STOPPING,
            )
        except ProvisionerBusyError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except InvalidProvisionerTransitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

        try:
            # Stop the provisioner
            await provisioner_cls.stop(state.state)
            logger.info(f"Provisioner stopped for '{vector_store_type}'")

            # Transition to STOPPED
            await self.provisioner_state_repository.upsert_status(
                vector_store_type=vector_store_type,
                status=ProvisionerStatus.STOPPED,
            )
        except Exception as e:
            logger.exception(
                f"Failed to stop provisioner for '{vector_store_type}': {e}"
            )
            await self.provisioner_state_repository.upsert_status(
                vector_store_type=vector_store_type,
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
                    f"Provisioner '{state.vector_store_type}' stuck in {state.status}, "
                    "resetting to ERROR for recovery"
                )
                await self.provisioner_state_repository.force_status_update(
                    vector_store_type=state.vector_store_type,
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
                    f"Skipping provisioner '{state.vector_store_type}' - no datasets attached"
                )
                continue

            # Skip if already running
            if state.status == ProvisionerStatus.RUNNING.value:
                provisioner_cls = self._get_provisioner_cls(state.vector_store_type)
                if provisioner_cls:
                    is_running = await provisioner_cls.is_running(state.state)
                    if is_running:
                        logger.info(
                            f"Provisioner '{state.vector_store_type}' is already running"
                        )
                        continue

            try:
                # Use state.state as config (contains connection fields from last run)
                config = state.state.copy() if state.state else {}
                await self._ensure_provisioner_running(state.vector_store_type, config)
            except Exception as e:
                logger.exception(
                    f"Failed to start provisioner '{state.vector_store_type}' "
                    f"during startup: {e}"
                )
                # Continue starting other provisioners

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
                await self._stop_provisioner(state.vector_store_type)
            except Exception as e:
                logger.exception(
                    f"Failed to stop provisioner '{state.vector_store_type}': {e}"
                )
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

        # Ensure provisioner is running (for local types).
        # ``vector_store_type`` is guaranteed known: dtype was just resolved
        # via ``registry.get_dataset_type`` above, which would have raised
        # for unknown bindings.
        vector_store_type = self._get_vector_store_type(request.dtype)
        assert vector_store_type is not None
        provisioner_state = await self._ensure_provisioner_running(
            vector_store_type, request.configuration
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
            provisioner_state = await self.provisioner_state_repository.get_by_id(
                dataset.provisioner_state_id
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
            provisioner_state = await self.provisioner_state_repository.get_by_id(
                updated_dataset.provisioner_state_id
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

        if self.endpoint_repository:
            attached = await self.endpoint_repository.get_by_dataset_id(
                dataset.id, tenant.id
            )
            if attached:
                names = ", ".join(f"'{e.name}'" for e in attached)
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot delete data source '{name}': it is used by {len(attached)} API(s): {names}. Remove it from those APIs first.",
                )

        if dataset.provisioner_state_id:
            logger.info(
                f"Dataset '{name}' was linked to provisioner, keeping provisioner running"
            )

        # Clean up dataset type resources (collection, images) before deleting the record
        try:
            dataset_type_cls = self.registry.get_dataset_type(dataset.dtype)
            if dataset.provisioner_state_id and issubclass(
                dataset_type_cls, IngestableDatasetType
            ):
                dataset_type = dataset_type_cls(dataset.configuration)
                ctx = IngestContext(
                    sender="system@openmined.org",
                    dataset_id=dataset.id,
                )
                await dataset_type.delete(ctx)
        except KeyError:
            logger.warning(
                f"Dataset type '{dataset.dtype}' not registered, skipping resource cleanup"
            )
        except Exception as e:
            logger.exception(f"Failed to clean up resources for dataset '{name}': {e}")

        deleted = await self.repository.delete_by_name(name, tenant.id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")

        return {"message": f"Successfully deleted dataset '{name}'"}

    async def healthcheck(self, name: str, tenant: Tenant) -> HealthcheckResponse:
        """Check the health of a dataset.
        Returns the health of the dataset type and the provisioner if it exists.

        Args:
            name: Dataset name
            tenant: Tenant context

        Returns:
            Healthcheck response
        """
        message = ""

        dataset = await self.repository.get_by_name(name, tenant.id)
        if not dataset:
            raise HTTPException(
                status_code=404, detail=f"Dataset '{name}' not found"
            ) from None

        dataset_type_cls = self.registry.get_dataset_type(dataset.dtype)
        dataset_type = dataset_type_cls(dataset.configuration)

        # Check if dataset type connection is healthy
        try:
            healthcheck_response = await dataset_type.healthcheck()
            message += f"Dataset type healthcheck: {healthcheck_response.message}. "
        except Exception as e:
            message += f"Failed to healthcheck dataset '{name}': {str(e)}"
            return HealthcheckResponse(
                dataset_type_status=HealthcheckStatus.UNHEALTHY,
                provisioner_status=None,
                message=message,
            )

        # Check provisioner status, if exists
        provisioner_health = None

        provisioner_state = (
            await self.provisioner_state_repository.get_by_id(
                dataset.provisioner_state_id
            )
            if dataset.provisioner_state_id
            else None
        )
        provisioner_cls = (
            self._get_provisioner_cls(provisioner_state.vector_store_type)
            if provisioner_state is not None
            else None
        )

        if provisioner_cls is not None and provisioner_state is not None:
            try:
                provisioner_status = await provisioner_cls.status(
                    provisioner_state.state
                )
                provisioner_health = (
                    HealthcheckStatus.HEALTHY.value
                    if provisioner_status
                    in (
                        ProvisionerStatus.RUNNING.value,
                        ProvisionerStatus.STARTING.value,
                    )
                    else HealthcheckStatus.UNHEALTHY.value
                )
            except Exception as e:
                provisioner_health = HealthcheckStatus.UNHEALTHY.value
                message += f"Failed to check provisioner status: {str(e)}"

        return HealthcheckResponse(
            dataset_type_status=healthcheck_response.status,
            provisioner_status=provisioner_health,
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
        provisioner_cls = self._get_provisioner_cls(state.vector_store_type)
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
        vector_store_type = self._get_vector_store_type(dtype)
        if not vector_store_type or not self._get_provisioner_cls(vector_store_type):
            raise HTTPException(
                status_code=400,
                detail=f"No provisioner registered for dtype '{dtype}'",
            )

        # Check if already running
        existing = (
            await self.provisioner_state_repository.get_running_by_vector_store_type(
                vector_store_type
            )
        )
        if existing:
            return ProvisionerActionResponse(
                message=f"Provisioner for '{vector_store_type}' is already running",
                status="running",
            )

        # Use the shared method
        await self._ensure_provisioner_running(vector_store_type, config)

        return ProvisionerActionResponse(
            message=f"Provisioner for '{vector_store_type}' started",
            status="running",
        )

    async def stop_provisioner_by_dtype(self, dtype: str) -> ProvisionerActionResponse:
        """Stop a provisioner for a specific dtype (admin action).

        Args:
            dtype: Dataset type name

        Returns:
            Action response with message and status
        """
        vector_store_type = self._get_vector_store_type(dtype)
        if not vector_store_type or not self._get_provisioner_cls(vector_store_type):
            raise HTTPException(
                status_code=400,
                detail=f"No provisioner registered for dtype '{dtype}'",
            )

        state = await self.provisioner_state_repository.get_by_vector_store_type(
            vector_store_type
        )
        if not state:
            return ProvisionerActionResponse(
                message=f"No provisioner found for '{vector_store_type}'",
                status="not_found",
            )

        if state.status == ProvisionerStatus.STOPPED.value:
            return ProvisionerActionResponse(
                message=f"Provisioner for '{vector_store_type}' is already stopped",
                status="stopped",
            )

        try:
            await self._stop_provisioner(vector_store_type)
            return ProvisionerActionResponse(
                message=f"Provisioner for '{vector_store_type}' stopped",
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
        vector_store_type = self._get_vector_store_type(dtype)
        if not vector_store_type or not self._get_provisioner_cls(vector_store_type):
            raise HTTPException(
                status_code=400,
                detail=f"No provisioner registered for dtype '{dtype}'",
            )

        existing = await self.provisioner_state_repository.get_by_vector_store_type(
            vector_store_type
        )
        if not existing:
            return ProvisionerActionResponse(
                message=f"No provisioner found for '{vector_store_type}'",
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
                detail=(
                    f"Cannot delete provisioner for '{vector_store_type}': "
                    f"{dataset_count} dataset(s) still attached. Delete the datasets first."
                ),
            )

        # Stop if running (use shared method)
        if existing.status in (
            ProvisionerStatus.RUNNING.value,
            ProvisionerStatus.STARTING.value,
        ):
            try:
                await self._stop_provisioner(vector_store_type)
            except Exception as e:
                logger.warning(f"Error stopping provisioner during delete: {e}")

        # Delete the record
        await self.provisioner_state_repository.delete_by_vector_store_type(
            vector_store_type
        )

        return ProvisionerActionResponse(
            message=f"Provisioner for '{vector_store_type}' stopped and deleted",
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
        vector_store_type = self._get_vector_store_type(dtype)
        if vector_store_type is None:
            raise HTTPException(
                status_code=404, detail=f"Provisioner for '{dtype}' not found"
            )

        state = await self.provisioner_state_repository.get_by_vector_store_type(
            vector_store_type
        )
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Provisioner for '{vector_store_type}' not found",
            )

        actual_status = await self._get_actual_provisioner_status(state)
        dataset_count = (
            await self.provisioner_state_repository.count_datasets_by_provisioner(
                state.id
            )
        )

        return ProvisionerInfoResponse.from_state(state, actual_status, dataset_count)

    # ============== Source Browser Methods ==============

    async def browse_source(
        self,
        dtype: str,
        configuration: dict[str, Any],
        parent_id: str | None,
    ) -> SourceBrowseResponse:
        """Return one level of items from a source, starting at ``parent_id``.

        Validation runs only at the top level (``parent_id is None``): the
        first call probes the credentials so bad ones fail as a 400.
        Drill-downs reuse those validated creds and skip the probe —
        ``list_items`` surfaces any failure on its own.
        """
        try:
            provider = SOURCE_REGISTRY.get(dtype)
        except KeyError as e:
            raise HTTPException(
                status_code=404, detail=f"Unknown source type: {dtype}"
            ) from e

        # Probe credentials once, on the first (top-level) call only.
        if parent_id is None:
            try:
                await provider.validate_browse_config(configuration)
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid browse configuration: {e}"
                ) from e

        try:
            browser = provider.for_browse(configuration)
            items = await browser.list_items(parent_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except NotADirectoryError as e:
            raise HTTPException(status_code=400, detail=f"Not a container: {e}") from e
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        return SourceBrowseResponse(parent_id=parent_id, items=items)

    async def serve_image(
        self, dataset_id: str, doc_id: str, filename: str, tenant: Tenant
    ) -> Path:
        """Validate and return the filesystem path for a document image.

        Resolves dataset_id to collection_name internally so that collection
        names are never exposed in public URLs.

        Args:
            dataset_id: Dataset ID
            doc_id: Hash-based document identifier (16-char hex)
            filename: Image filename (32-char hex UUID .png)
            tenant: Tenant
        Returns:
            Resolved Path to the image file

        Raises:
            HTTPException 400: If any parameter format is invalid
            HTTPException 404: If the dataset or image file does not exist
        """
        # Validate dataset_id format: UUID hex (32 chars or with dashes)
        if not re.match(
            r"^[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}$",
            dataset_id,
        ):
            raise HTTPException(status_code=400, detail="Invalid dataset ID format")

        # Validate doc_id format: 16-char lowercase hex
        if not re.match(r"^[a-f0-9]{16}$", doc_id):
            raise HTTPException(status_code=400, detail="Invalid document ID format")

        # Validate filename format: {uuid_hex}.png (32-char lowercase hex)
        if not re.match(r"^[a-f0-9]{32}\.png$", filename):
            raise HTTPException(status_code=400, detail="Invalid filename format")

        # Resolve dataset_id to collection_name via the dataset type
        dataset = await self.repository.get_by_id(UUID(dataset_id), tenant.id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        try:
            dataset_type_cls = self.registry.get_dataset_type(dataset.dtype)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Dataset type '{dataset.dtype}' not registered"
            ) from None

        dataset_instance = dataset_type_cls(dataset.configuration)
        collection_name = getattr(dataset_instance, "collection_name", None)
        if not collection_name:
            raise HTTPException(
                status_code=404, detail="Dataset has no collection configured"
            )

        # Resolve path and prevent traversal
        image_path = (
            PAGE_IMAGES_BASE_DIR / collection_name / doc_id / filename
        ).resolve()
        if not image_path.is_relative_to(PAGE_IMAGES_BASE_DIR.resolve()):
            raise HTTPException(status_code=400, detail="Invalid path")

        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        return image_path
