"""MPP payment routes — balance and transaction queries."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_space.components.payments.mpp.handlers import MppPaymentHandler
from syft_space.components.payments.mpp.schemas import (
    MppBalanceResponse,
    TransactionResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_mpp_payment_routes(handler: MppPaymentHandler) -> APIRouter:
    """Build MPP payment routes (balance + transactions)."""
    router = APIRouter(prefix="/mpp", tags=["payments", "mpp"])

    def get_handler() -> MppPaymentHandler:
        return handler

    @router.get("/{wallet_id}/balance", response_model=MppBalanceResponse)
    async def get_mpp_balance(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MppPaymentHandler = Depends(get_handler),
    ) -> MppBalanceResponse:
        """Get MPP wallet balance from Tempo blockchain."""
        return await handler.get_balance(wallet_id, tenant)

    @router.get("/{wallet_id}/transactions", response_model=list[TransactionResponse])
    async def get_mpp_transactions(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MppPaymentHandler = Depends(get_handler),
    ) -> list[TransactionResponse]:
        """Get MPP wallet transactions from Tempo blockchain."""
        return await handler.get_transactions(wallet_id, tenant)

    return router
