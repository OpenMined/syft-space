"""Wallet routes — composes generic + category-specific sub-routers."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.gateway.routes import build_gateway_wallet_routes
from syft_space.components.wallets.handlers import WalletHandler
from syft_space.components.wallets.mpp.routes import build_mpp_wallet_routes
from syft_space.components.wallets.schemas import WalletListItem, WalletResponse


def build_wallet_routes(handler: WalletHandler) -> APIRouter:
    """Build all wallet routes (generic + mpp + gateway)."""
    router = APIRouter(prefix="/wallets", tags=["wallets"])

    def get_handler() -> WalletHandler:
        return handler

    # --- Generic routes (all wallet types) ---

    @router.get("/", response_model=list[WalletListItem])
    async def list_wallets(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> list[WalletListItem]:
        """List all wallets for the current tenant."""
        return await handler.list_wallets(tenant)

    @router.get("/{wallet_id}", response_model=WalletResponse)
    async def get_wallet(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Get a specific wallet by ID."""
        return await handler.get_wallet(wallet_id, tenant)

    @router.delete("/{wallet_id}")
    async def delete_wallet(
        wallet_id: UUID,
        force: bool = Query(
            default=False,
            description="If true, delete even when users have nonzero balance.",
        ),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a wallet (blocked if users have live balance, unless force=true)."""
        return await handler.delete_wallet(wallet_id, tenant, force=force)

    # --- Include category-specific sub-routers ---
    # These mount under /wallets/mpp/... and /wallets/gateway/...
    # The sub-routers define their own prefixes relative to /wallets
    router.include_router(build_mpp_wallet_routes(handler))
    router.include_router(build_gateway_wallet_routes(handler))

    return router
