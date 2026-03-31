"""MPP wallet routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.handlers import WalletHandler
from syft_space.components.wallets.mpp.schemas import (
    CreateMppWalletRequest,
    ImportMppWalletRequest,
    MppBalanceResponse,
    TransactionResponse,
    UpdateMppWalletAddressRequest,
)
from syft_space.components.wallets.schemas import WalletResponse
from syft_space.components.wallets.wallet_configs import WalletType


def build_mpp_wallet_routes(handler: WalletHandler) -> APIRouter:
    """Build MPP-specific wallet routes."""
    router = APIRouter(prefix="/mpp", tags=["wallets", "mpp"])

    def get_handler() -> WalletHandler:
        return handler

    @router.post("/", response_model=WalletResponse, status_code=201)
    async def create_mpp_wallet(
        request: CreateMppWalletRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Generate a new MPP wallet keypair."""
        return await handler.create_wallet(
            wallet_type=WalletType.MPP,
            raw_credentials={},
            tenant=tenant,
            name=request.name,
        )

    @router.post("/import", response_model=WalletResponse, status_code=201)
    async def import_mpp_wallet(
        request: ImportMppWalletRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Import an MPP wallet from private key."""
        return await handler.create_wallet(
            wallet_type=WalletType.MPP,
            raw_credentials={"private_key": request.private_key},
            tenant=tenant,
            name=request.name,
        )

    @router.put("/{wallet_id}/address", response_model=WalletResponse)
    async def update_mpp_wallet_address(
        wallet_id: UUID,
        request: UpdateMppWalletAddressRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Update MPP wallet address manually."""
        return await handler.update_mpp_wallet_address(
            wallet_id, request.wallet_address, tenant
        )

    # Temporary — moves to payments component later
    @router.get("/{wallet_id}/balance", response_model=MppBalanceResponse)
    async def get_mpp_balance(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> MppBalanceResponse:
        """Get MPP wallet balance from Tempo blockchain."""
        return await handler.get_mpp_balance(wallet_id, tenant)

    @router.get("/{wallet_id}/transactions", response_model=list[TransactionResponse])
    async def get_mpp_transactions(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> list[TransactionResponse]:
        """Get MPP wallet transactions from Tempo blockchain."""
        return await handler.get_mpp_transactions(wallet_id, tenant)

    return router
