"""Bundle service for reserve/settle/cancel operations.

Shared stateless orchestrator. Balance is tracked as money (float).
"""

from uuid import UUID

from syft_space.components.payments.gateway.bundle_usage_repository import (
    BundleUsageRepository,
)


class BundleService:
    """Manages money balance operations at query time.

    Provides reserve/settle/cancel semantics:
    - reserve: Atomically deduct money (pre-hook)
    - settle: Refund money (post-hook, if applicable)
    - cancel: Full rollback on error
    """

    def __init__(self, bundle_usage_repository: BundleUsageRepository):
        self.repo = bundle_usage_repository

    async def reserve(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        amount: float,
    ) -> bool:
        """Reserve money by atomically deducting from balance.

        Returns True if deduction succeeded, False if insufficient balance.
        """
        return await self.repo.atomic_deduct(user_email, endpoint_id, tenant_id, amount)

    async def settle(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        refund_amount: float,
    ) -> None:
        """Settle by refunding unused portion after query completion."""
        if refund_amount > 0:
            await self.repo.atomic_restore(
                user_email, endpoint_id, tenant_id, refund_amount
            )

    async def cancel(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
        amount: float,
    ) -> None:
        """Cancel reservation by restoring full reserved amount."""
        await self.repo.atomic_restore(user_email, endpoint_id, tenant_id, amount)

    async def get_balance(
        self,
        user_email: str,
        endpoint_id: UUID,
        tenant_id: UUID,
    ) -> float:
        """Get remaining money balance for a user+endpoint."""
        usage = await self.repo.get_by_user_endpoint(user_email, endpoint_id, tenant_id)
        return usage.remaining_balance if usage else 0.0
