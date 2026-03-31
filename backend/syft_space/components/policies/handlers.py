"""Policy handlers for business logic."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException

from syft_space.components.policies.entities import Policy
from syft_space.components.policies.repository import PolicyRepository
from syft_space.components.policies.schemas import (
    CreatePolicyRequest,
    PolicyListItem,
    PolicyResponse,
    PolicyTypeInfoResponse,
    UpdatePolicyRequest,
)
from syft_space.components.policy_types.registry import PolicyTypeRegistry
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.repository import WalletRepository

# Policy types that require a wallet_id
PAYMENT_POLICY_TYPES = {"mpp_accounting", "xendit"}


class PolicyHandler:
    """Handler for policy business logic."""

    def __init__(
        self,
        registry: PolicyTypeRegistry,
        repository: PolicyRepository,
        wallet_repository: WalletRepository,
    ):
        """Initialize the policy handler.

        Args:
            registry: Policy type registry
            repository: Policy repository
            wallet_repository: Wallet repository for payment policy validation
        """
        self.registry = registry
        self.repository = repository
        self.wallet_repository = wallet_repository

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

    async def create_policy(
        self, request: CreatePolicyRequest, tenant: Tenant
    ) -> PolicyResponse:
        """Create a new policy.

        Args:
            request: Policy creation request
            tenant: Tenant context

        Returns:
            Created policy

        Raises:
            HTTPException: If policy type not found or config invalid
        """
        # Verify policy type exists
        try:
            policy_type_cls = self.registry.get_policy_type(request.policy_type)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Policy type '{request.policy_type}' not found"
            ) from None

        # Validate configuration against policy type schema
        try:
            validated_config = await policy_type_cls.validate_config(
                request.configuration
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        # Payment policies require a wallet_id
        if request.policy_type in PAYMENT_POLICY_TYPES:
            if not request.wallet_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"wallet_id is required for {request.policy_type} policies. "
                    "Please create a wallet first.",
                )
            # Verify wallet exists and belongs to tenant
            wallet = await self.wallet_repository.get_by_id(
                request.wallet_id, tenant.id
            )
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            # Enforce: all payment policies on this endpoint must use the same wallet
            existing = await self.repository.get_by_endpoint_id(
                request.endpoint_id, tenant.id
            )
            for p in existing:
                if p.wallet_id and p.wallet_id != request.wallet_id:
                    raise HTTPException(
                        status_code=400,
                        detail="All payment policies on an endpoint must use the same wallet.",
                    )
        elif request.wallet_id:
            raise HTTPException(
                status_code=400,
                detail=f"wallet_id is not applicable for {request.policy_type} policies.",
            )

        # Create policy entity with validated config
        policy = Policy(
            name=request.name,
            policy_type=request.policy_type,
            configuration=validated_config,
            endpoint_id=request.endpoint_id,
            wallet_id=request.wallet_id,
            tenant_id=tenant.id,
        )

        # Save to database
        created = await self.repository.create(policy)

        return PolicyResponse.model_validate(created)

    async def list_policies(self, tenant: Tenant) -> list[PolicyListItem]:
        """List all policies for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of policies
        """
        policies = await self.repository.get_all(tenant.id)
        return [PolicyListItem.model_validate(p) for p in policies]

    async def get_policy(self, policy_id: UUID, tenant: Tenant) -> PolicyResponse:
        """Get a specific policy by ID within a tenant.

        Args:
            policy_id: Policy UUID
            tenant: Tenant context

        Returns:
            Policy details

        Raises:
            HTTPException: If policy not found
        """
        policy = await self.repository.get_by_id(policy_id, tenant.id)
        if not policy:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_id}' not found"
            )

        return PolicyResponse.model_validate(policy)

    async def update_policy(
        self, policy_id: UUID, request: UpdatePolicyRequest, tenant: Tenant
    ) -> PolicyResponse:
        """Update a policy (partial update).

        Args:
            policy_id: Policy UUID
            request: Update request with optional fields
            tenant: Tenant context

        Returns:
            Updated policy

        Raises:
            HTTPException: If policy not found or validation fails
        """
        # Get existing policy
        policy = await self.repository.get_by_id(policy_id, tenant.id)
        if not policy:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_id}' not found"
            )

        # Update name if provided
        if request.name is not None:
            policy.name = request.name

        # Merge and validate configuration if provided
        if request.configuration is not None:
            # Shallow merge: update keys override existing
            merged_config = {**policy.configuration, **request.configuration}

            # Validate against policy type schema
            try:
                policy_type_cls = self.registry.get_policy_type(policy.policy_type)
                validated_config = await policy_type_cls.validate_config(merged_config)
                policy.configuration = validated_config
            except KeyError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy type '{policy.policy_type}' not found",
                ) from None
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None

        # Update timestamp
        policy.updated_at = datetime.now(timezone.utc)

        # Save updates
        updated = await self.repository.update(policy)
        return PolicyResponse.model_validate(updated)

    async def delete_policy(self, policy_id: UUID, tenant: Tenant) -> dict:
        """Delete a policy by ID within a tenant.

        Args:
            policy_id: Policy UUID
            tenant: Tenant context

        Returns:
            Success message

        Raises:
            HTTPException: If policy not found
        """
        # First get the policy to verify it exists and belongs to tenant
        policy = await self.repository.get_by_id(policy_id, tenant.id)
        if not policy:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_id}' not found"
            )

        # Now delete it using the base repository method
        deleted = await self.repository.delete(policy_id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_id}' not found"
            )

        return {"message": f"Successfully deleted policy '{policy_id}'"}

    async def get_policies_by_endpoint(
        self, endpoint_id: UUID, tenant: Tenant
    ) -> list[PolicyResponse]:
        """Get all policies for a specific endpoint within a tenant.

        Args:
            endpoint_id: Endpoint UUID
            tenant: Tenant context

        Returns:
            List of policies
        """
        policies = await self.repository.get_by_endpoint_id(endpoint_id, tenant.id)
        return [PolicyResponse.model_validate(p) for p in policies]
