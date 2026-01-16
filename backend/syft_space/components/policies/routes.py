"""Policy API routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from syft_space.components.policies.handlers import PolicyHandler
from syft_space.components.policies.schemas import (
    CreatePolicyRequest,
    PolicyListItem,
    PolicyResponse,
    PolicyTypeInfoResponse,
    UpdatePolicyRequest,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_policy_routes(handler: PolicyHandler) -> APIRouter:
    """Build the policy routes.

    Args:
        handler: Policy handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/policies", tags=["policies"])

    def get_handler() -> PolicyHandler:
        """Dependency to get the policy handler."""
        return handler

    @router.get("/types/", response_model=list[PolicyTypeInfoResponse])
    async def list_policy_types(
        handler: PolicyHandler = Depends(get_handler),
    ) -> list[PolicyTypeInfoResponse]:
        """List all available policy types.

        Returns:
            List of policy type information including configuration schemas
        """
        return handler.list_policy_types()

    @router.get("/types/{name}", response_model=PolicyTypeInfoResponse)
    async def get_policy_type(
        name: str,
        handler: PolicyHandler = Depends(get_handler),
    ) -> PolicyTypeInfoResponse:
        """Get information about a specific policy type.

        Args:
            name: Policy type name

        Returns:
            Policy type information
        """
        return handler.get_policy_type(name)

    @router.get("/types/{name}/schema", response_model=dict[str, Any])
    async def get_policy_type_schema(
        name: str,
        handler: PolicyHandler = Depends(get_handler),
    ) -> dict[str, Any]:
        """Get the configuration schema for a specific policy type.

        Args:
            name: Policy type name

        Returns:
            Configuration schema dictionary
        """
        type_info = handler.get_policy_type(name)
        return type_info.config_schema

    @router.post("/", response_model=PolicyResponse, status_code=201)
    async def create_policy(
        request: CreatePolicyRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PolicyHandler = Depends(get_handler),
    ) -> PolicyResponse:
        """Create a new policy.

        Args:
            request: Policy creation request with configuration
            tenant: Current tenant (injected)

        Returns:
            Created policy details
        """
        return handler.create_policy(request, tenant)

    @router.get("/", response_model=list[PolicyListItem])
    async def list_policies(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PolicyHandler = Depends(get_handler),
    ) -> list[PolicyListItem]:
        """List all policies.

        Args:
            tenant: Current tenant (injected)

        Returns:
            List of policies with summary information
        """
        return handler.list_policies(tenant)

    @router.get("/{policy_id}", response_model=PolicyResponse)
    async def get_policy(
        policy_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PolicyHandler = Depends(get_handler),
    ) -> PolicyResponse:
        """Get details of a specific policy.

        Args:
            policy_id: Policy UUID
            tenant: Current tenant (injected)

        Returns:
            Policy details including configuration
        """
        return handler.get_policy(policy_id, tenant)

    @router.patch("/{policy_id}", response_model=PolicyResponse)
    async def update_policy(
        policy_id: UUID,
        request: UpdatePolicyRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PolicyHandler = Depends(get_handler),
    ) -> PolicyResponse:
        """Update a policy (partial update).

        Args:
            policy_id: Policy UUID
            request: Update request with optional name and configuration
            tenant: Current tenant (injected)

        Returns:
            Updated policy details
        """
        return handler.update_policy(policy_id, request, tenant)

    @router.delete("/{policy_id}", response_model=dict[str, str])
    async def delete_policy(
        policy_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PolicyHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a policy.

        Args:
            policy_id: Policy UUID
            tenant: Current tenant (injected)

        Returns:
            Success message
        """
        return handler.delete_policy(policy_id, tenant)

    return router
