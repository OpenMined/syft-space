"""Tenant repository for database operations."""

from typing import Optional

from syftai_space.components.shared.database import BaseRepository, Database
from syftai_space.components.tenants.entities import Tenant


class TenantRepository(BaseRepository[Tenant]):
    """Repository for Tenant CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the tenant repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Tenant)

    def get_by_name(self, name: str) -> Optional[Tenant]:
        """Get a tenant by name.

        Args:
            name: Tenant name

        Returns:
            Tenant if found, None otherwise
        """
        return self.get_by_field("name", name)

    def get_by_domain(self, domain: str) -> Optional[Tenant]:
        """Get a tenant by domain.

        Args:
            domain: Tenant domain

        Returns:
            Tenant if found, None otherwise
        """
        return self.get_by_field("domain", domain)
