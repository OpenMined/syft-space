"""Tenant handlers for business logic."""

from fastapi import HTTPException

from syft_space.components.tenants.entities import Tenant
from syft_space.components.tenants.repository import TenantRepository
from syft_space.components.tenants.schemas import (
    CreateTenantRequest,
    TenantListItem,
    TenantResponse,
)
from syft_space.config import app_settings


class TenantHandler:
    """Handler for tenant business logic."""

    def __init__(self, repository: TenantRepository):
        """Initialize the tenant handler.
        cc
                Args:
                    repository: Tenant repository
        """
        self.repository = repository

    def create_tenant(self, request: CreateTenantRequest) -> TenantResponse:
        """Create a new tenant.

        Args:
            request: Tenant creation request

        Returns:
            Created tenant

        Raises:
            HTTPException: If multi-tenancy is disabled or name already exists
        """
        # Check if multi-tenancy is enabled
        if not app_settings.enable_multi_tenancy:
            raise HTTPException(
                status_code=403,
                detail="Multi-tenancy is disabled. Cannot create new tenants.",
            )

        # Check if name already exists
        existing = self.repository.get_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Tenant '{request.name}' already exists"
            )

        # Check if domain already exists (if provided)
        if request.domain:
            existing_domain = self.repository.get_by_domain(request.domain)
            if existing_domain:
                raise HTTPException(
                    status_code=409,
                    detail=f"Domain '{request.domain}' already in use",
                )

        # Create tenant entity
        tenant = Tenant(
            name=request.name,
            display_name=request.display_name,
            domain=request.domain,
            meta=request.meta,
            is_active=True,
        )

        # Save to database
        created = self.repository.create(tenant)

        return TenantResponse.model_validate(created)

    def list_tenants(self) -> list[TenantListItem]:
        """List all tenants.

        Returns:
            List of tenants
        """
        tenants = self.repository.get_all()
        return [TenantListItem.model_validate(t) for t in tenants]

    def get_tenant(self, name: str) -> TenantResponse:
        """Get a specific tenant by name.

        Args:
            name: Tenant name

        Returns:
            Tenant details

        Raises:
            HTTPException: If tenant not found
        """
        tenant = self.repository.get_by_name(name)
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Tenant '{name}' not found")

        return TenantResponse.model_validate(tenant)
