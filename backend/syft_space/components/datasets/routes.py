"""Dataset API routes."""

from typing import TYPE_CHECKING, Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse

from syft_space.components.auth.public import public_route
from syft_space.components.datasets.handlers import DatasetHandler
from syft_space.components.datasets.schemas import (
    AddSelectionRequest,
    CreateDatasetRequest,
    DatasetBrowseRequest,
    DatasetListItem,
    DatasetResponse,
    DatasetTypeInfoResponse,
    HealthcheckResponse,
    ProvisionerActionResponse,
    ProvisionerInfoResponse,
    RemoveSelectionRequest,
    SelectionIdsResponse,
    SelectionPageResponse,
    SelectionResponse,
    SourceBrowseRequest,
    SourceBrowseResponse,
    UpdateDatasetRequest,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant

if TYPE_CHECKING:
    from syft_space.components.ingestion.manager import IngestionManager


def build_dataset_routes(
    handler: DatasetHandler,
    ingestion_manager: Optional["IngestionManager"] = None,
) -> APIRouter:
    """Build the dataset routes.

    Args:
        handler: Dataset handler instance
        ingestion_manager: Optional ingestion manager for auto-starting ingestion

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

    # ============== Source Browser Endpoint ==============

    @router.post("/browse", response_model=SourceBrowseResponse)
    async def browse_source(
        req: SourceBrowseRequest,
        handler: DatasetHandler = Depends(get_handler),
    ) -> SourceBrowseResponse:
        """Browse a source by dtype.

        Generic picker endpoint: caller supplies the source type and its
        configuration; the handler dispatches to that source's
        ``list_items`` for one level of containers/leaves.
        """
        return await handler.browse_source(
            req.dtype, req.configuration, req.parent_id, req.cursor
        )

    @router.post("/{name}/browse", response_model=SourceBrowseResponse)
    async def browse_dataset_source(
        name: str,
        req: DatasetBrowseRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> SourceBrowseResponse:
        """Browse an existing dataset's source using its stored credentials.

        Drives the "add source" picker: the server reads connection details
        from the dataset's stored configuration, so credentials are never
        sent to (or required from) the client.
        """
        return await handler.browse_dataset_source(
            name, tenant, req.parent_id, req.cursor
        )

    # ============== Image Serving Endpoint ==============

    @public_route
    @router.get("/{dataset_id}/images/{doc_id}/{filename}")
    async def serve_image(
        dataset_id: str,
        doc_id: str,
        filename: str,
        handler: DatasetHandler = Depends(get_handler),
        tenant: Tenant = Depends(get_tenant_dependency),
    ) -> FileResponse:
        """Serve a document image (page render or extracted picture).

        Images are saved to disk during ingestion and served via this endpoint.
        Search results return URIs pointing here so clients can fetch images.
        Uses dataset_id (not collection_name) in the URL to avoid leaking
        internal collection names.

        Args:
            dataset_id: Dataset UUID (resolved to collection_name internally)
            doc_id: Hash-based document identifier (16-char hex)
            filename: Image filename (32-char hex UUID, e.g., a1b2c3d4e5f67890abcdef1234567890.png)

        Returns:
            PNG image file
        """
        image_path = await handler.serve_image(dataset_id, doc_id, filename, tenant)
        return FileResponse(image_path, media_type="image/png")

    # ============== Dataset CRUD Endpoints ==============

    @router.post("/", response_model=DatasetResponse, status_code=201)
    async def create_dataset(
        request: CreateDatasetRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetResponse:
        """Create a new dataset.

        Automatically kicks off ingestion for bindings whose source
        emits a change stream (scans existing items, starts the
        watcher / poller).

        Args:
            request: Dataset creation request with configuration
            tenant: Current tenant (injected)

        Returns:
            Created dataset details
        """
        response = await handler.create_dataset(request, tenant)

        # Auto-start ingestion for bindings whose source emits a change stream
        if ingestion_manager:
            await ingestion_manager.start_ingestion_by_id(response.id, tenant.id)

        return response

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
        return await handler.list_datasets(tenant)

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
        return await handler.get_dataset(name, tenant)

    @router.patch("/{name}", response_model=DatasetResponse)
    async def update_dataset(
        name: str,
        request: UpdateDatasetRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetResponse:
        """Update a dataset (partial update).

        Allows updating name, summary, and/or tags. Name must remain unique per tenant.

        Args:
            name: Current dataset name
            request: Update request with fields to update
            tenant: Current tenant (injected)

        Returns:
            Updated dataset details

        Raises:
            422 Unprocessable Entity: If no fields provided (Pydantic validation)
            404 Not Found: If dataset not found
            409 Conflict: If new name already exists
        """
        return await handler.update_dataset(name, request, tenant)

    @router.delete("/{name}", response_model=dict[str, str])
    async def delete_dataset(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a dataset.

        Stops any active/pending ingestion before cleaning up resources.

        Args:
            name: Dataset name
            tenant: Current tenant (injected)

        Returns:
            Success message
        """
        # Stop ingestion (cancel pending jobs, stop file watcher) before
        # deleting so that a queued job cannot recreate the collection after
        # we clean it up.
        if ingestion_manager:
            dataset = await handler.repository.get_by_name(name, tenant.id)
            if dataset:
                await ingestion_manager.stop_dataset_ingestion(dataset.id)

        return await handler.delete_dataset(name, tenant)

    # ============== Selection Endpoints ==============

    @router.get("/{name}/selection", response_model=SelectionPageResponse)
    async def get_selection(
        name: str,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> SelectionPageResponse:
        """A page of a dataset's selection picks.

        The selection is no longer inlined in the dataset/endpoint payload;
        detail views fetch and page through it here.

        Args:
            name: Dataset name
            limit: Max picks to return (1-200)
            offset: Picks to skip
            tenant: Current tenant (injected)

        Returns:
            The requested page plus the total pick count
        """
        return await handler.get_selection_page(name, tenant, limit, offset)

    @router.get("/{name}/selection/ids", response_model=SelectionIdsResponse)
    async def get_selection_ids(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> SelectionIdsResponse:
        """Every selected item id for a dataset (unpaged).

        For the "add source" picker, which pre-checks already-selected items
        and so needs the complete id set rather than a page.

        Args:
            name: Dataset name
            tenant: Current tenant (injected)

        Returns:
            All selected item ids
        """
        return await handler.get_selection_ids(name, tenant)

    @router.post("/{name}/selection", response_model=SelectionResponse)
    async def add_selection(
        name: str,
        request: AddSelectionRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> SelectionResponse:
        """Add picks to a dataset's selection.

        Idempotent per item. Restarts the dataset's ingestion stream so the
        new picks are scanned immediately and watched from now on.

        Args:
            name: Dataset name
            request: Picks to add (item_id + optional description)
            tenant: Current tenant (injected)

        Returns:
            The dataset's full selection after the add
        """
        response = await handler.add_selection(name, request, tenant)

        if ingestion_manager:
            dataset = await handler.repository.get_by_name(name, tenant.id)
            if dataset:
                await ingestion_manager.restart_dataset_ingestion(dataset.id, tenant.id)

        return response

    @router.delete("/{name}/selection", response_model=SelectionResponse)
    async def remove_selection(
        name: str,
        request: RemoveSelectionRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> SelectionResponse:
        """Remove picks from a dataset's selection.

        Tombstones the ingestion jobs the removed picks produced (their
        vectors are removed once vector-store deletion lands), then restarts
        the stream with the remaining picks. Items covered by both a removed
        and a remaining pick are re-ingested by the restarted stream's
        initial scan.

        Args:
            name: Dataset name
            request: Item ids to remove
            tenant: Current tenant (injected)

        Returns:
            The dataset's remaining selection
        """
        response, removed_ids = await handler.remove_selection(name, request, tenant)

        if ingestion_manager and removed_ids:
            dataset = await handler.repository.get_by_name(name, tenant.id)
            if dataset:
                await ingestion_manager.apply_unselection(
                    dataset.id, tenant.id, removed_ids
                )
                await ingestion_manager.restart_dataset_ingestion(dataset.id, tenant.id)

        return response

    @public_route
    @router.get("/{name}/health", response_model=HealthcheckResponse)
    async def healthcheck(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: DatasetHandler = Depends(get_handler),
    ) -> HealthcheckResponse:
        """Check the health of a dataset (PUBLIC, no auth required).

        Args:
            name: Dataset name
            tenant: Current tenant (injected)

        Returns:
            Healthcheck response
        """
        return await handler.healthcheck(name, tenant)

    # ============== Admin Provisioner Endpoints ==============

    @router.get("/provisioners/", response_model=list[ProvisionerInfoResponse])
    async def list_provisioners(
        handler: DatasetHandler = Depends(get_handler),
    ) -> list[ProvisionerInfoResponse]:
        """List all provisioners and their status.

        Admin endpoint to view all provisioner states, their status,
        and how many datasets are using each one.
        """
        return await handler.list_provisioners()

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
            dtype: Dataset type name (e.g., 'local_file')
            config: Optional configuration with connection settings (httpPort, grpcPort, etc.)

        Returns:
            Action response with message and status
        """
        return await handler.start_provisioner_by_dtype(dtype, config)

    @router.post("/provisioners/{dtype}/stop", response_model=ProvisionerActionResponse)
    async def stop_provisioner(
        dtype: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> ProvisionerActionResponse:
        """Stop a provisioner for a specific dataset type.

        Admin endpoint to manually stop a provisioner.
        The provisioner state record is kept for later restart.

        Args:
            dtype: Dataset type name (e.g., 'local_file')

        Returns:
            Action response with message and status
        """
        return await handler.stop_provisioner_by_dtype(dtype)

    @router.delete("/provisioners/{dtype}", response_model=ProvisionerActionResponse)
    async def delete_provisioner(
        dtype: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> ProvisionerActionResponse:
        """Delete a provisioner for a specific dataset type.

        Admin endpoint to stop and delete a provisioner state record.
        Only succeeds if no datasets are attached to this provisioner.

        Args:
            dtype: Dataset type name (e.g., 'local_file')

        Returns:
            Action response with message and status

        Raises:
            409 Conflict: If datasets are still attached to the provisioner
        """
        return await handler.delete_provisioner_by_dtype(dtype)

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
        return await handler.get_provisioner_status_by_dtype(dtype)

    return router
