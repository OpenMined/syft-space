"""Wallet API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.handlers import WalletHandler
from syft_space.components.wallets.schemas import (
    CreateWalletRequest,
    WalletCreateResponse,
    WalletListItem,
    WalletResponse,
)


def build_wallet_routes(handler: WalletHandler) -> APIRouter:
    """Build the wallet routes.

    Args:
        handler: Wallet handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/wallets", tags=["wallets"])

    def get_handler() -> WalletHandler:
        """Dependency to get the wallet handler."""
        return handler

    @router.post("/", response_model=WalletCreateResponse, status_code=201)
    async def create_wallet(
        request_data: CreateWalletRequest,
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletCreateResponse:
        """Create a new payment wallet.

        Returns the webhook URL and callback token (shown once).
        Configure both in the provider's dashboard.
        """
        return await handler.create_wallet(request_data, tenant, request)

    @router.get("/", response_model=list[WalletListItem])
    async def list_wallets(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> list[WalletListItem]:
        """List all payment wallets."""
        return await handler.list_wallets(tenant)

    @router.get("/{wallet_id}", response_model=WalletResponse)
    async def get_wallet(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Get details of a specific wallet."""
        return await handler.get_wallet(wallet_id, tenant)

    @router.delete("/{wallet_id}", response_model=dict[str, str])
    async def delete_wallet(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a payment wallet."""
        return await handler.delete_wallet(wallet_id, tenant)

    return router
