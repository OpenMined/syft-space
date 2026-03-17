"""Wallet handlers for business logic."""

import secrets
from uuid import UUID

from fastapi import HTTPException, Request

from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.entities import Wallet
from syft_space.components.wallets.repository import WalletRepository
from syft_space.components.wallets.schemas import (
    CreateWalletRequest,
    WalletCreateResponse,
    WalletListItem,
    WalletResponse,
)

# Supported wallet types
SUPPORTED_WALLET_TYPES = {"xendit"}


class WalletHandler:
    """Handler for wallet business logic."""

    def __init__(self, repository: WalletRepository):
        self.repository = repository

    def _build_webhook_url(self, request: Request, wallet_type: str) -> str:
        """Build the webhook URL for a wallet type.

        Uses the current request's base URL so it works behind proxies.
        """
        base_url = str(request.base_url).rstrip("/")
        return f"{base_url}/api/v1/webhooks/{wallet_type}"

    async def create_wallet(
        self,
        request_data: CreateWalletRequest,
        tenant: Tenant,
        request: Request,
    ) -> WalletCreateResponse:
        """Create a new wallet.

        Auto-generates a callback token for webhook verification.
        Returns the webhook URL and callback token (shown once).
        """
        if request_data.wallet_type not in SUPPORTED_WALLET_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported wallet type '{request_data.wallet_type}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_WALLET_TYPES))}",
            )

        # Check if wallet already exists for this type
        existing = await self.repository.get_by_type(
            request_data.wallet_type, tenant.id
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A '{request_data.wallet_type}' wallet already exists. "
                "Delete the existing wallet first or update its credentials.",
            )

        webhook_url = self._build_webhook_url(request, request_data.wallet_type)
        callback_token = secrets.token_urlsafe(32)

        wallet = Wallet(
            tenant_id=tenant.id,
            wallet_type=request_data.wallet_type,
            credentials={
                "api_key": request_data.api_key,
                "callback_token": callback_token,
            },
            is_active=True,
            webhook_url=webhook_url,
        )

        created = await self.repository.create(wallet)

        return WalletCreateResponse(
            id=created.id,
            wallet_type=created.wallet_type,
            is_active=created.is_active,
            webhook_url=created.webhook_url,
            callback_token=callback_token,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

    async def list_wallets(self, tenant: Tenant) -> list[WalletListItem]:
        """List all wallets for a tenant."""
        wallets = await self.repository.get_all(tenant.id)
        return [WalletListItem.model_validate(w) for w in wallets]

    async def get_wallet(self, wallet_id: UUID, tenant: Tenant) -> WalletResponse:
        """Get a specific wallet by ID."""
        wallet = await self.repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(
                status_code=404, detail=f"Wallet '{wallet_id}' not found"
            )
        return WalletResponse.model_validate(wallet)

    async def delete_wallet(self, wallet_id: UUID, tenant: Tenant) -> dict:
        """Delete a wallet."""
        wallet = await self.repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(
                status_code=404, detail=f"Wallet '{wallet_id}' not found"
            )

        deleted = await self.repository.delete(wallet_id, tenant.id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Wallet '{wallet_id}' not found"
            )

        return {"message": f"Successfully deleted '{wallet.wallet_type}' wallet"}
