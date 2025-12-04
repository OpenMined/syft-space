"""Dataset API routes."""

from typing import Any

from fastapi import APIRouter, Body, Depends

from syftai_space.components.datasets.handlers import DatasetHandler
from syftai_space.components.datasets.schemas import (
    CreateDatasetRequest,
    DatasetListItem,
    DatasetResponse,
    DatasetTypeInfoResponse,
    HealthcheckResponse,
    ProvisionerActionResponse,
    ProvisionerInfoResponse,
)
from syftai_space.components.tenants.dependency import get_tenant_dependency
from syftai_space.components.tenants.entities import Tenant


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
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetResponse:
        """Create a new dataset.

        Args:
            request: Dataset creation request with configuration
            tenant: Current tenant (injected)

        Returns:
            Created dataset details
        """
        return handler.create_dataset(request, tenant)

    @router.get("/", response_model=list[DatasetListItem])
    async def list_datasets(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> list[DatasetListItem]:
        """List all datasets.

        Args:
            tenant: Current tenant (injected)

        Returns:
            List of datasets with summary information
        """
        return handler.list_datasets(tenant)

    @router.get("/{name}", response_model=DatasetResponse)
    async def get_dataset(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetResponse:
        """Get details of a specific dataset.

        Args:
            name: Dataset name
            tenant: Current tenant (injected)

        Returns:
            Dataset details including configuration
        """
        return handler.get_dataset(name, tenant)

    @router.delete("/{name}", response_model=dict[str, str])
    async def delete_dataset(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a dataset.

        Args:
            name: Dataset name
            tenant: Current tenant (injected)

        Returns:
            Success message
        """
        return handler.delete_dataset(name, tenant)

    @router.get("/{name}/health", response_model=HealthcheckResponse)
    async def healthcheck(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> HealthcheckResponse:
        """Check the health of a dataset.

        Args:
            name: Dataset name
            tenant: Current tenant (injected)

        Returns:
            Healthcheck response
        """
        return handler.healthcheck(name, tenant)

    # ============== Admin Provisioner Endpoints ==============

    @router.get("/provisioners/", response_model=list[ProvisionerInfoResponse])
    async def list_provisioners(
        handler: DatasetHandler = Depends(get_handler),
    ) -> list[ProvisionerInfoResponse]:
        """List all provisioners and their status.

        Admin endpoint to view all provisioner states, their status,
        and how many datasets are using each one.
        """
        return handler.list_provisioners()

    @router.post(
        "/provisioners/{dtype}/start", response_model=ProvisionerActionResponse
    )
    async def start_provisioner(
        dtype: str,
        config: dict[str, Any] = Body(default={}),
        handler: DatasetHandler = Depends(get_handler),
    ) -> ProvisionerActionResponse:
        """Start a provisioner for a specific dataset type.

        Admin endpoint to manually start a provisioner.

        Args:
            dtype: Dataset type name (e.g., 'weaviate_local')
            config: Optional configuration with connection settings (httpPort, grpcPort, etc.)

        Returns:
            Action response with message and status
        """
        return handler.start_provisioner_by_dtype(dtype, config)

    @router.post("/provisioners/{dtype}/stop", response_model=ProvisionerActionResponse)
    async def stop_provisioner(
        dtype: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> ProvisionerActionResponse:
        """Stop a provisioner for a specific dataset type.

        Admin endpoint to manually stop a provisioner.
        The provisioner state record is kept for later restart.

        Args:
            dtype: Dataset type name (e.g., 'weaviate_local')

        Returns:
            Action response with message and status
        """
        return handler.stop_provisioner_by_dtype(dtype)

    @router.delete("/provisioners/{dtype}", response_model=ProvisionerActionResponse)
    async def delete_provisioner(
        dtype: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> ProvisionerActionResponse:
        """Delete a provisioner for a specific dataset type.

        Admin endpoint to stop and delete a provisioner state record.
        Only succeeds if no datasets are attached to this provisioner.

        Args:
            dtype: Dataset type name (e.g., 'weaviate_local')

        Returns:
            Action response with message and status

        Raises:
            409 Conflict: If datasets are still attached to the provisioner
        """
        return handler.delete_provisioner_by_dtype(dtype)

    @router.get("/provisioners/{dtype}/status", response_model=ProvisionerInfoResponse)
    async def get_provisioner_status(
        dtype: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> ProvisionerInfoResponse:
        """Get detailed status of a provisioner.

        Args:
            dtype: Dataset type name

        Returns:
            Detailed provisioner status including actual running status,
            dataset count, connection config, timestamps, and any errors.
        """
        return handler.get_provisioner_status_by_dtype(dtype)

    return router
