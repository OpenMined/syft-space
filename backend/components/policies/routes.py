"""Policy API routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from .handlers import PolicyHandler
from .schemas import (
    CreatePolicyRequest,
    PolicyListItem,
    PolicyResponse,
    PolicyTypeInfoResponse,
)


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
        handler: PolicyHandler = Depends(get_handler),
    ) -> PolicyResponse:
        """Create a new policy.

        Args:
            request: Policy creation request with configuration

        Returns:
            Created policy details
        """
        return handler.create_policy(request)

    @router.get("/", response_model=list[PolicyListItem])
    async def list_policies(
        handler: PolicyHandler = Depends(get_handler),
    ) -> list[PolicyListItem]:
        """List all policies.

        Returns:
            List of policies with summary information
        """
        return handler.list_policies()

    @router.get("/{policy_id}", response_model=PolicyResponse)
    async def get_policy(
        policy_id: UUID,
        handler: PolicyHandler = Depends(get_handler),
    ) -> PolicyResponse:
        """Get details of a specific policy.

        Args:
            policy_id: Policy UUID

        Returns:
            Policy details including configuration
        """
        return handler.get_policy(policy_id)

    @router.delete("/{policy_id}", response_model=dict[str, str])
    async def delete_policy(
        policy_id: UUID,
        handler: PolicyHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a policy.

        Args:
            policy_id: Policy UUID

        Returns:
            Success message
        """
        return handler.delete_policy(policy_id)

    return router
