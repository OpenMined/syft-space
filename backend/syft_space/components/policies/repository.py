"""Policy repository for database operations."""

from collections import defaultdict
from uuid import UUID

from sqlmodel import select

from syft_space.components.policies.entities import Policy
from syft_space.components.shared.database import BaseRepository, Database


class PolicyRepository(BaseRepository[Policy]):
    """Repository for Policy CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the policy repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Policy)

    def get_all(self, tenant_id: UUID) -> list[Policy]:
        """Get all policies for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of policies
        """
        with self.db.get_session() as session:
            statement = select(Policy).where(Policy.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_by_id(self, id: int, tenant_id: UUID) -> Policy | None:
        """Get a policy by ID within a tenant.

        Args:
            id: Policy ID
            tenant_id: Tenant ID

        Returns:
            Policy if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.id == id, Policy.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def get_by_endpoint_id(self, endpoint_id: UUID, tenant_id: UUID) -> list[Policy]:
        """Get all policies for a specific endpoint within a tenant.

        Args:
            endpoint_id: Endpoint UUID
            tenant_id: Tenant ID

        Returns:
            List of policies
        """
        with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.endpoint_id == endpoint_id, Policy.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())

    def get_by_endpoint_id_grouped(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> dict[str, list[Policy]]:
        """Get all policies for a specific endpoint within a tenant, grouped by policy_type.

        Args:
            endpoint_id: Endpoint UUID
            tenant_id: Tenant ID

        Returns:
            Dictionary mapping policy_type to list of policies
        """
        with self.db.get_session() as session:
            statement = (
                select(Policy)
                .where(Policy.endpoint_id == endpoint_id, Policy.tenant_id == tenant_id)
                .order_by(Policy.policy_type)
            )
            policies = list(session.exec(statement).all())

            # Group policies by policy_type
            grouped: dict[str, list[Policy]] = defaultdict(list)
            for policy in policies:
                grouped[policy.policy_type].append(policy)

            return grouped

    def get_by_type(self, type_name: str, tenant_id: UUID) -> list[Policy]:
        """Get all policies of a specific type within a tenant.

        Args:
            type_name: Policy type name
            tenant_id: Tenant ID

        Returns:
            List of policies
        """
        with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.policy_type == type_name, Policy.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())

    def get_by_name(self, name: str, tenant_id: UUID) -> Policy | None:
        """Get a policy by name within a tenant.

        Args:
            name: Policy name
            tenant_id: Tenant ID

        Returns:
            Policy if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(Policy).where(
                Policy.name == name, Policy.tenant_id == tenant_id
            )
            return session.exec(statement).first()
