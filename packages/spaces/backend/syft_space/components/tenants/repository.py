"""Tenant repository for database operations."""

from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase
from syft_space.components.tenants.entities import Tenant


class TenantRepository(AsyncBaseRepository[Tenant]):
    """Repository for Tenant CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        """Initialize the tenant repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Tenant)

    async def get_by_name(self, name: str) -> Tenant | None:
        """Get a tenant by name.

        Args:
            name: Tenant name

        Returns:
            Tenant if found, None otherwise
        """
        return await self.get_by_field("name", name)

    async def get_by_domain(self, domain: str) -> Tenant | None:
        """Get a tenant by domain.

        Args:
            domain: Tenant domain

        Returns:
            Tenant if found, None otherwise
        """
        return await self.get_by_field("domain", domain)
