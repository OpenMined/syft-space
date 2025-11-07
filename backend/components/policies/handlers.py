"""Policy handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException

from components.policy_types.registry import PolicyTypeRegistry

from .entities import Policy
from .repository import PolicyRepository
from .schemas import (
    CreatePolicyRequest,
    PolicyListItem,
    PolicyResponse,
    PolicyTypeInfoResponse,
)


class PolicyHandler:
    """Handler for policy business logic."""

    def __init__(self, registry: PolicyTypeRegistry, repository: PolicyRepository):
        """Initialize the policy handler.

        Args:
            registry: Policy type registry
            repository: Policy repository
        """
        self.registry = registry
        self.repository = repository

    def list_policy_types(self) -> list[PolicyTypeInfoResponse]:
        """List all available policy types.

        Returns:
            List of policy type information
        """
        type_names = self.registry.list_policy_types()
        types_info = []

        for name in type_names:
            policy_type_cls = self.registry.get_policy_type(name)
            types_info.append(
                PolicyTypeInfoResponse(
                    name=policy_type_cls.name(),
                    description=policy_type_cls.description(),
                    config_schema=policy_type_cls.configuration_schema(),
                    icon=policy_type_cls.icon(),
                    enabled=policy_type_cls.enabled(),
                )
            )

        return types_info

    def get_policy_type(self, name: str) -> PolicyTypeInfoResponse:
        """Get information about a specific policy type.

        Args:
            name: Policy type name

        Returns:
            Policy type information

        Raises:
            HTTPException: If policy type not found
        """
        try:
            policy_type_cls = self.registry.get_policy_type(name)
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"Policy type '{name}' not found"
            ) from None

        return PolicyTypeInfoResponse(
            name=policy_type_cls.name(),
            description=policy_type_cls.description(),
            config_schema=policy_type_cls.configuration_schema(),
            icon=policy_type_cls.icon(),
            enabled=policy_type_cls.enabled(),
        )

    def create_policy(self, request: CreatePolicyRequest) -> PolicyResponse:
        """Create a new policy.

        Args:
            request: Policy creation request

        Returns:
            Created policy

        Raises:
            HTTPException: If policy type not found
        """
        # Verify policy type exists
        try:
            self.registry.get_policy_type(request.policy_type)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Policy type '{request.policy_type}' not found"
            ) from None

        # TODO: Verify endpoint exists when endpoint repository is available

        # Create policy entity
        policy = Policy(
            name=request.name,
            policy_type=request.policy_type,
            configuration=request.configuration,
            endpoint_id=request.endpoint_id,
        )

        # Save to database
        created = self.repository.create(policy)

        return PolicyResponse.model_validate(created)

    def list_policies(self) -> list[PolicyListItem]:
        """List all policies.

        Returns:
            List of policies
        """
        policies = self.repository.get_all()
        return [PolicyListItem.model_validate(p) for p in policies]

    def get_policy(self, policy_id: UUID) -> PolicyResponse:
        """Get a specific policy by ID.

        Args:
            policy_id: Policy UUID

        Returns:
            Policy details

        Raises:
            HTTPException: If policy not found
        """
        policy = self.repository.get_by_id(policy_id)
        if not policy:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_id}' not found"
            )

        return PolicyResponse.model_validate(policy)

    def delete_policy(self, policy_id: UUID) -> dict:
        """Delete a policy by ID.

        Args:
            policy_id: Policy UUID

        Returns:
            Success message

        Raises:
            HTTPException: If policy not found
        """
        deleted = self.repository.delete(policy_id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_id}' not found"
            )

        return {"message": f"Successfully deleted policy '{policy_id}'"}

    def get_policies_by_endpoint(self, endpoint_id: UUID) -> list[PolicyResponse]:
        """Get all policies for a specific endpoint.

        Args:
            endpoint_id: Endpoint UUID

        Returns:
            List of policies
        """
        policies = self.repository.get_by_endpoint_id(endpoint_id)
        return [PolicyResponse.model_validate(p) for p in policies]
