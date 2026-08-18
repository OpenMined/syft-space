"""MPP wallet routes — credential management only."""

from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends
from loguru import logger

from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.handlers import WalletHandler
from syft_space.components.wallets.mpp.schemas import (
    CreateMppWalletRequest,
    ImportMppWalletRequest,
    UpdateMppWalletAddressRequest,
)
from syft_space.components.wallets.schemas import WalletResponse

TEMPO_FAUCET_URL = "https://docs.tempo.xyz/api/faucet"


async def _fund_via_tempo_faucet(address: str) -> None:
    """Best-effort top-up of a freshly created MPP wallet from the Tempo faucet."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(TEMPO_FAUCET_URL, json={"address": address})
        if response.is_success:
            logger.info(f"wallet.faucet_funded address={address}")
        else:
            logger.warning(
                f"wallet.faucet_non_2xx address={address} "
                f"status_code={response.status_code} body={response.text[:500]}"
            )
    except Exception as exc:
        logger.warning(f"wallet.faucet_failed address={address} error={exc}")


def build_mpp_wallet_routes(handler: WalletHandler) -> APIRouter:
    """Build MPP-specific wallet routes (credential management)."""
    router = APIRouter(prefix="/mpp", tags=["wallets", "mpp"])

    def get_handler() -> WalletHandler:
        return handler

    @router.post("/", response_model=WalletResponse, status_code=201)
    async def create_mpp_wallet(
        request: CreateMppWalletRequest,
        background_tasks: BackgroundTasks,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Generate a new MPP wallet keypair."""
        wallet = await handler.create_wallet(
            wallet_type="mpp",
            raw_credentials={},
            tenant=tenant,
            name=request.name,
        )
        address = wallet.display.get("wallet_address") if wallet.display else None
        if address:
            background_tasks.add_task(_fund_via_tempo_faucet, address)
        return wallet

    @router.post("/import", response_model=WalletResponse, status_code=201)
    async def import_mpp_wallet(
        request: ImportMppWalletRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Import an MPP wallet from private key."""
        return await handler.create_wallet(
            wallet_type="mpp",
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
        return await handler.update_wallet_credentials(
            wallet_id,
            {"wallet_address": request.wallet_address},
            tenant,
        )

    return router
