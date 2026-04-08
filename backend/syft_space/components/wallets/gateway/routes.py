"""Gateway wallet routes (Xendit, Stripe, Razorpay)."""

from fastapi import APIRouter, Depends

from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.gateway.schemas import CreateXenditWalletRequest
from syft_space.components.wallets.handlers import WalletHandler
from syft_space.components.wallets.schemas import WalletResponse


def build_gateway_wallet_routes(handler: WalletHandler) -> APIRouter:
    """Build gateway-specific wallet routes."""
    router = APIRouter(prefix="/gateway", tags=["wallets", "gateway"])

    def get_handler() -> WalletHandler:
        return handler

    @router.post("/xendit", response_model=WalletResponse, status_code=201)
    async def create_xendit_wallet(
        request: CreateXenditWalletRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Create a Xendit payment gateway wallet."""
        return await handler.create_wallet(
            wallet_type="xendit",
            raw_credentials={
                "api_key": request.api_key,
                "callback_token": request.callback_token,
            },
            tenant=tenant,
            name=request.name,
        )

    return router
