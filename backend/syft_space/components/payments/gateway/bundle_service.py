"""Bundle service for reserve/settle/cancel operations.

Shared stateless orchestrator used by any bundle-based policy type.
"""

from uuid import UUID

from syft_space.components.payments.gateway.bundle_usage_repository import (
    BundleUsageRepository,
)


class BundleService:
    """Manages bundle balance operations at query time.

    Provides reserve/settle/cancel semantics:
    - reserve: Atomically deduct units (pre-hook)
    - settle: Refund unused portion (post-hook, actual < reserved)
    - cancel: Full rollback on error
    """

    def __init__(self, bundle_usage_repository: BundleUsageRepository):
        self.repo = bundle_usage_repository

    async def reserve(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        unit_type: str,
        amount: int,
    ) -> bool:
        """Reserve units by atomically deducting from balance.

        Returns True if deduction succeeded, False if insufficient balance.
        """
        return await self.repo.atomic_deduct(
            user_email, endpoint_id, tenant_id, unit_type, amount
        )

    async def settle(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        unit_type: str,
        refund_amount: int,
    ) -> None:
        """Settle by refunding unused portion after query completion."""
        if refund_amount > 0:
            await self.repo.atomic_restore(
                user_email, endpoint_id, tenant_id, unit_type, refund_amount
            )

    async def cancel(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        unit_type: str,
        amount: int,
    ) -> None:
        """Cancel reservation by restoring full reserved amount."""
        await self.repo.atomic_restore(
            user_email, endpoint_id, tenant_id, unit_type, amount
        )

    async def get_balance(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        unit_type: str,
    ) -> int:
        """Get remaining balance for a user+endpoint+unit_type."""
        usage = await self.repo.get_by_user_endpoint(
            user_email, endpoint_id, tenant_id, unit_type
        )
        return usage.remaining_units if usage else 0
