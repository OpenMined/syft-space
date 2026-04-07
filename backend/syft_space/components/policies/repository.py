"""Policy repository for database operations."""

from collections import defaultdict
from uuid import UUID

from sqlmodel import select

from syft_space.components.policies.entities import Policy
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class PolicyRepository(AsyncBaseRepository[Policy]):
    """Repository for Policy CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        """Initialize the policy repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Policy)

    async def get_all(self, tenant_id: UUID) -> list[Policy]:
        """Get all policies for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of policies
        """
        async with self.db.get_session() as session:
            statement = select(Policy).where(Policy.tenant_id == tenant_id)
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_id(self, id: int, tenant_id: UUID) -> Policy | None:
        """Get a policy by ID within a tenant.

        Args:
            id: Policy ID
            tenant_id: Tenant ID

        Returns:
            Policy if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.id == id, Policy.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_endpoint_id(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> list[Policy]:
        """Get all policies for a specific endpoint within a tenant.

        Args:
            endpoint_id: Endpoint UUID
            tenant_id: Tenant ID

        Returns:
            List of policies
        """
        async with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.endpoint_id == endpoint_id, Policy.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_endpoint_and_type(
        self, endpoint_id: UUID, policy_type: str, tenant_id: UUID
    ) -> Policy | None:
        """Get a policy by endpoint ID and policy type within a tenant."""
        async with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.endpoint_id == endpoint_id,
                Policy.policy_type == policy_type,
                Policy.tenant_id == tenant_id,
            )
            result = await session.exec(statement)
            return result.first()

    async def has_different_wallet(
        self, endpoint_id: UUID, tenant_id: UUID, wallet_id: UUID
    ) -> bool:
        """Check if any policy on this endpoint uses a different wallet.

        Returns True if a conflicting wallet_id exists.
        """
        async with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.endpoint_id == endpoint_id,
                Policy.tenant_id == tenant_id,
                Policy.wallet_id.is_not(None),
                Policy.wallet_id != wallet_id,
            )
            result = await session.exec(statement)
            return result.first() is not None

    async def get_by_endpoint_id_grouped(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> dict[str, list[Policy]]:
        """Get all policies for a specific endpoint within a tenant, grouped by policy_type.

        Args:
            endpoint_id: Endpoint UUID
            tenant_id: Tenant ID

        Returns:
            Dictionary mapping policy_type to list of policies
        """
        async with self.db.get_session() as session:
            statement = (
                select(Policy)
                .where(Policy.endpoint_id == endpoint_id, Policy.tenant_id == tenant_id)
                .order_by(Policy.policy_type)
            )
            result = await session.exec(statement)
            policies = list(result.all())

            # Group policies by policy_type
            grouped: dict[str, list[Policy]] = defaultdict(list)
            for policy in policies:
                grouped[policy.policy_type].append(policy)

            return grouped

    async def get_by_type(self, type_name: str, tenant_id: UUID) -> list[Policy]:
        """Get all policies of a specific type within a tenant.

        Args:
            type_name: Policy type name
            tenant_id: Tenant ID

        Returns:
            List of policies
        """
        async with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.policy_type == type_name, Policy.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_name(self, name: str, tenant_id: UUID) -> Policy | None:
        """Get a policy by name within a tenant.

        Args:
            name: Policy name
            tenant_id: Tenant ID

        Returns:
            Policy if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.name == name, Policy.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()
