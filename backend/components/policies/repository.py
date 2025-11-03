"""Policy repository for database operations."""

from typing import Optional
from uuid import UUID

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

    def get_by_endpoint_id(self, endpoint_id: UUID) -> list[Policy]:
        """Get all policies for a specific endpoint.

        Args:
            endpoint_id: Endpoint UUID

        Returns:
            List of policies
        """
        with self.db.get_session() as session:
            from sqlmodel import select

            statement = select(Policy).where(Policy.endpoint_id == endpoint_id)
            return list(session.exec(statement).all())

    def get_by_type(self, type_name: str) -> list[Policy]:
        """Get all policies of a specific type.

        Args:
            type_name: Policy type name

        Returns:
            List of policies
        """
        with self.db.get_session() as session:
            from sqlmodel import select

            statement = select(Policy).where(Policy.ptype == type_name)
            return list(session.exec(statement).all())

    def get_by_name(self, name: str) -> Optional[Policy]:
        """Get a policy by name.

        Args:
            name: Policy name

        Returns:
            Policy if found, None otherwise
        """
        return self.get_by_field("name", name)
