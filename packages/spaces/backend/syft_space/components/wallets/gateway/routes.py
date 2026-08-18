"""Gateway wallet routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.gateway.schemas import (
    CreateStripeWalletRequest,
    CreateXenditWalletRequest,
    UpdateStripeWalletRequest,
    UpdateXenditWalletRequest,
)
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
                "currency": request.currency.value,
                "country": request.country.value,
            },
            tenant=tenant,
            name=request.name,
        )

    @router.put("/xendit/{wallet_id}", response_model=WalletResponse)
    async def update_xendit_wallet(
        wallet_id: UUID,
        request: UpdateXenditWalletRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Update Xendit wallet credentials (API key and/or callback token)."""
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        return await handler.update_wallet_credentials(wallet_id, updates, tenant)

    @router.post("/stripe", response_model=WalletResponse, status_code=201)
    async def create_stripe_wallet(
        request: CreateStripeWalletRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Create a Stripe payment gateway wallet."""
        return await handler.create_wallet(
            wallet_type="stripe",
            raw_credentials={
                "secret_key": request.secret_key,
                "webhook_secret": request.webhook_secret,
                "currency": request.currency.value,
            },
            tenant=tenant,
            name=request.name,
        )

    @router.put("/stripe/{wallet_id}", response_model=WalletResponse)
    async def update_stripe_wallet(
        wallet_id: UUID,
        request: UpdateStripeWalletRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: WalletHandler = Depends(get_handler),
    ) -> WalletResponse:
        """Update Stripe wallet credentials (secret key and/or webhook secret)."""
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        return await handler.update_wallet_credentials(wallet_id, updates, tenant)

    return router
