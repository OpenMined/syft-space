"""Policy repository for database operations."""

from typing import Optional
from uuid import UUID

from sqlmodel import select

from components.shared.database import BaseRepository, Database

from .entities import Policy


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

    def get_by_id(self, id: int, tenant_id: UUID) -> Optional[Policy]:
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

    def get_by_name(self, name: str, tenant_id: UUID) -> Optional[Policy]:
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
