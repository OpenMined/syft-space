"""MPP wallet routes — credential management only."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.handlers import WalletHandler
from syft_space.components.wallets.mpp.schemas import (
    CreateMppWalletRequest,
    ImportMppWalletRequest,
    UpdateMppWalletAddressRequest,
)
from syft_space.components.wallets.schemas import WalletResponse
from syft_space.components.wallets.wallet_configs import WalletType


def build_mpp_wallet_routes(handler: WalletHandler) -> APIRouter:
    """Build MPP-specific wallet routes (credential management)."""
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

    return router
