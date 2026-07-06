"""Endpoint CRUD handler — create, read, update, delete, archive."""

from datetime import datetime, timezone

from fastapi import HTTPException

from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.datasets.selection_repository import (
    DatasetSelectionRepository,
)
from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.interfaces import DeletionCheck
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.schemas import (
    CreateEndpointRequest,
    EndpointCreateResponse,
    EndpointDetailResponse,
    EndpointListItem,
    UpdateEndpointRequest,
)
from syft_space.components.models.repository import ModelRepository
from syft_space.components.tenants.entities import Tenant


class EndpointHandler:
    """Handler for endpoint CRUD and lifecycle operations."""

    def __init__(
        self,
        endpoint_repository: EndpointRepository,
        dataset_repository: DatasetRepository,
        model_repository: ModelRepository,
        selection_repository: DatasetSelectionRepository,
        deletion_check: DeletionCheck | None = None,
    ):
        self.endpoint_repository = endpoint_repository
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.selection_repository = selection_repository
        self.deletion_check = deletion_check

    async def _to_detail(self, endpoint: Endpoint) -> EndpointDetailResponse:
        """Build a detail response, populating the attached dataset's
        selection count from the selection repository (computed in the DB;
        no selection rows are loaded)."""
        response = EndpointDetailResponse.model_validate(endpoint)
        if response.dataset is not None:
            counts = await self.selection_repository.count_by_datasets(
                [response.dataset.id]
            )
            response.dataset.selected_items_count = counts.get(response.dataset.id, 0)
        return response

    async def create_endpoint(
        self, request: CreateEndpointRequest, tenant: Tenant
    ) -> EndpointCreateResponse:
        """Create a new endpoint."""
        # Validate at least one of dataset_id or model_id is provided
        if request.dataset_id is None and request.model_id is None:
            raise HTTPException(
                status_code=400,
                detail="At least one of dataset_id or model_id must be provided",
            )

        # Check if slug already exists within tenant
        existing = await self.endpoint_repository.get_by_slug(request.slug, tenant.id)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Endpoint slug '{request.slug}' already exists"
            )

        # Verify dataset exists if provided (within tenant)
        if request.dataset_id:
            dataset = await self.dataset_repository.get_by_id(
                request.dataset_id, tenant.id
            )
            if not dataset:
                raise HTTPException(
                    status_code=404, detail=f"Dataset '{request.dataset_id}' not found"
                )

        # Verify model exists if provided (within tenant)
        if request.model_id:
            model = await self.model_repository.get_by_id(request.model_id, tenant.id)
            if not model:
                raise HTTPException(
                    status_code=404, detail=f"Model '{request.model_id}' not found"
                )

        # Create endpoint entity
        endpoint = Endpoint(
            name=request.name,
            slug=request.slug,
            description=request.description,
            summary=request.summary,
            dataset_id=request.dataset_id,
            model_id=request.model_id,
            response_type=request.response_type,
            published=request.published,
            tags=request.tags,
            system_prompt=request.system_prompt,
            tenant_id=tenant.id,
        )

        created = await self.endpoint_repository.create(endpoint)
        return EndpointCreateResponse.model_validate(created)

    async def list_endpoints(self, tenant: Tenant) -> list[EndpointListItem]:
        """List all endpoints for a tenant."""
        endpoints = await self.endpoint_repository.get_all(tenant.id)
        items = [EndpointListItem.model_validate(ep) for ep in endpoints]

        # Selection counts are computed in one grouped DB query (no rows
        # loaded) and composed in — the selection aggregate owns that data.
        dataset_ids = [ep.dataset.id for ep in endpoints if ep.dataset]
        counts = await self.selection_repository.count_by_datasets(dataset_ids)
        for item in items:
            if item.dataset is not None:
                item.dataset.selected_items_count = counts.get(item.dataset.id, 0)
        return items

    async def get_endpoint(self, slug: str, tenant: Tenant) -> EndpointDetailResponse:
        """Get a specific endpoint by slug within a tenant."""
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")
        return await self._to_detail(endpoint)

    async def update_endpoint(
        self, slug: str, request: UpdateEndpointRequest, tenant: Tenant
    ) -> EndpointDetailResponse:
        """Update an endpoint by slug within a tenant."""
        updated_endpoint = await self.endpoint_repository.update_by_slug(
            slug,
            tenant.id,
            name=request.name,
            summary=request.summary,
            description=request.description,
            system_prompt=request.system_prompt,
        )
        if not updated_endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")
        return await self._to_detail(updated_endpoint)

    async def delete_endpoint(self, slug: str, tenant: Tenant) -> dict:
        """Delete an endpoint by slug within a tenant.

        Uses deletion_check callback (wired in main.py) to guard against
        deleting endpoints with active financial state.
        """
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        if self.deletion_check:
            error = await self.deletion_check(endpoint.id, tenant.id)
            if error:
                raise HTTPException(status_code=409, detail=error)

        deleted = await self.endpoint_repository.delete_by_slug(slug, tenant.id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        return {"message": f"Successfully deleted endpoint '{slug}'"}

    async def archive_endpoint(
        self, slug: str, tenant: Tenant
    ) -> EndpointDetailResponse:
        """Archive an endpoint — blocks new purchases but allows existing queries."""
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")
        if endpoint.archived:
            raise HTTPException(status_code=400, detail="Endpoint is already archived")

        endpoint.archived = True
        endpoint.updated_at = datetime.now(timezone.utc)
        updated = await self.endpoint_repository.update(endpoint)
        return await self._to_detail(updated)

    async def unarchive_endpoint(
        self, slug: str, tenant: Tenant
    ) -> EndpointDetailResponse:
        """Unarchive an endpoint — re-enables purchases."""
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")
        if not endpoint.archived:
            raise HTTPException(status_code=400, detail="Endpoint is not archived")

        endpoint.archived = False
        endpoint.updated_at = datetime.now(timezone.utc)
        updated = await self.endpoint_repository.update(endpoint)
        return await self._to_detail(updated)
