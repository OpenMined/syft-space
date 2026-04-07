"""Wallet handlers for business logic.

Use case interactor following Clean Architecture. Depends on
WalletProvider Protocol — never imports external libs directly.
"""

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from loguru import logger

from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.interfaces import WalletProvider
from syft_space.components.wallets.mpp.config import MppWalletConfig
from syft_space.components.wallets.repository import WalletRepository
from syft_space.components.wallets.schemas import WalletListItem, WalletResponse
from syft_space.components.wallets.wallet_configs import WalletType


class WalletHandler:
    """Handler for wallet business logic.

    Orchestrates wallet CRUD via the WalletProvider Protocol.
    Provider dispatch: wallet_type → provider instance (injected by main.py).
    """

    def __init__(
        self,
        repository: WalletRepository,
        providers: dict[str, WalletProvider],
    ) -> None:
        self.repository = repository
        self.providers = providers

    def _get_provider(self, wallet_type: str) -> WalletProvider:
        """Get provider for a wallet type."""
        if wallet_type not in self.providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown wallet type: {wallet_type}. "
                f"Supported: {list(self.providers.keys())}",
            )
        return self.providers[wallet_type]

    # --- Generic operations (all wallet types) ---

    async def list_wallets(self, tenant: Tenant) -> list[WalletListItem]:
        """List all wallets for a tenant."""
        wallets = await self.repository.get_all(tenant.id)
        items = []
        for w in wallets:
            display = self._extract_display(w.wallet_type, w.configuration)
            items.append(
                WalletListItem(
                    id=w.id,
                    wallet_type=w.wallet_type,
                    name=w.name,
                    is_active=w.is_active,
                    display=display,
                    created_at=w.created_at,
                )
            )
        return items

    async def get_wallet(self, wallet_id: UUID, tenant: Tenant) -> WalletResponse:
        """Get a wallet by ID."""
        wallet = await self.repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        display = self._extract_display(wallet.wallet_type, wallet.configuration)
        return WalletResponse(
            id=wallet.id,
            wallet_type=wallet.wallet_type,
            name=wallet.name,
            is_active=wallet.is_active,
            display=display,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
        )

    async def delete_wallet(self, wallet_id: UUID, tenant: Tenant) -> dict[str, str]:
        """Delete a wallet."""
        deleted = await self.repository.delete_wallet(wallet_id, tenant.id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return {"message": "Wallet deleted"}

    # --- Wallet creation (delegates to provider) ---

    async def create_wallet(
        self,
        wallet_type: str,
        raw_credentials: dict[str, Any],
        tenant: Tenant,
        name: str | None = None,
    ) -> WalletResponse:
        """Create a wallet using the appropriate provider.

        The provider handles type-specific logic (keypair generation for MPP,
        credential validation for Xendit). The handler validates the result
        via the config class and persists it.
        """
        provider = self._get_provider(wallet_type)

        # Delegate to provider
        try:
            result = await provider.setup_wallet(raw_credentials)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        # Validate credentials via config class
        config_cls = provider.config_class
        try:
            validated = config_cls(**result.credentials)
        except Exception as e:
            logger.error(f"Provider returned invalid credentials: {e}")
            raise HTTPException(
                status_code=500, detail="Wallet creation failed: invalid credentials"
            ) from None

        # Persist
        wallet = await self.repository.create_wallet(
            tenant_id=tenant.id,
            wallet_type=wallet_type,
            name=name or f"{wallet_type.upper()} Wallet",
            configuration=validated.model_dump(),
        )

        display = result.display
        return WalletResponse(
            id=wallet.id,
            wallet_type=wallet.wallet_type,
            name=wallet.name,
            is_active=wallet.is_active,
            display=display,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
        )

    # --- MPP-specific: address update ---

    async def update_mpp_wallet_address(
        self, wallet_id: UUID, wallet_address: str, tenant: Tenant
    ) -> WalletResponse:
        """Update the wallet address for an MPP wallet (without changing private key)."""
        wallet = await self.repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        if wallet.wallet_type != WalletType.MPP:
            raise HTTPException(
                status_code=400,
                detail="Address update is only supported for MPP wallets",
            )

        config = MppWalletConfig(**wallet.configuration)
        updated_config = config.model_copy(update={"wallet_address": wallet_address})
        wallet = await self.repository.update_configuration(
            wallet_id, tenant.id, updated_config.model_dump()
        )
        return WalletResponse(
            id=wallet.id,
            wallet_type=wallet.wallet_type,
            name=wallet.name,
            is_active=wallet.is_active,
            display={"wallet_address": wallet_address},
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
        )

    # --- Helpers ---

    @staticmethod
    def _extract_display(wallet_type: str, configuration: dict) -> dict[str, Any]:
        """Extract safe display info from wallet configuration.

        Never exposes private keys or secrets.
        """
        if wallet_type == WalletType.MPP:
            return {"wallet_address": configuration.get("wallet_address", "")}
        return {}
