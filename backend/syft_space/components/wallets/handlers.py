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
from syft_space.components.wallets.repository import WalletRepository
from syft_space.components.wallets.schemas import WalletListItem, WalletResponse
from syft_space.components.wallets.wallet_configs import WalletType


class WalletHandler:
    """Handler for wallet business logic.

    Orchestrates wallet CRUD via the WalletProvider Protocol.
    Provider dispatch: wallet_type → provider instance (injected by main.py).

    Enforces (tenant, wallet_type, currency) uniqueness at the application
    layer (also DB-enforced via UniqueConstraint).
    """

    def __init__(
        self,
        repository: WalletRepository,
        providers: dict[str, WalletProvider],
        deletion_check=None,
    ) -> None:
        self.repository = repository
        self.providers = providers
        # Optional callback returning a string error if the wallet has live
        # balances (set by main.py via dependency inversion to avoid the
        # wallet component importing payments).
        self.deletion_check = deletion_check

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

    async def _has_managed_wallet(self, tenant_id) -> bool:
        """True when a cluster-managed wallet exists for this tenant."""
        wallets = await self.repository.get_all(tenant_id)
        return any(w.wallet_type == WalletType.CLUSTER.value for w in wallets)

    async def list_wallets(self, tenant: Tenant) -> list[WalletListItem]:
        """List all wallets for a tenant."""
        wallets = await self.repository.get_all(tenant.id)
        items = []
        for w in wallets:
            display = self._extract_display(w.wallet_type, w.configuration, w.id)
            items.append(
                WalletListItem(
                    id=w.id,
                    wallet_type=w.wallet_type,
                    name=w.name,
                    currency=w.currency,
                    country=w.country,
                    is_active=w.is_active,
                    display=display,
                    managed=w.wallet_type == WalletType.CLUSTER.value,
                    created_at=w.created_at,
                )
            )
        return items

    async def get_wallet(self, wallet_id: UUID, tenant: Tenant) -> WalletResponse:
        """Get a wallet by ID."""
        wallet = await self.repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        display = self._extract_display(
            wallet.wallet_type, wallet.configuration, wallet.id
        )
        return WalletResponse(
            id=wallet.id,
            wallet_type=wallet.wallet_type,
            name=wallet.name,
            currency=wallet.currency,
            country=wallet.country,
            is_active=wallet.is_active,
            display=display,
            managed=wallet.wallet_type == WalletType.CLUSTER.value,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
        )

    async def delete_wallet(
        self, wallet_id: UUID, tenant: Tenant, force: bool = False
    ) -> dict[str, str]:
        """Delete a wallet.

        Blocked if any user has a nonzero balance for this wallet, unless
        force=True. The deletion_check callback (set by main.py) provides
        the UserBalance lookup without creating a wallet→payments import.
        """
        wallet = await self.repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        if wallet.wallet_type == WalletType.CLUSTER.value:
            raise HTTPException(
                status_code=403,
                detail="This wallet is managed by the cluster and cannot be deleted",
            )

        if not force and self.deletion_check is not None:
            error = await self.deletion_check(wallet_id, tenant.id)
            if error:
                raise HTTPException(status_code=409, detail=error)

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

        The provider validates and enriches credentials, returning currency
        and (optionally) country alongside the configuration. The handler
        enforces (tenant, wallet_type, currency) uniqueness.

        Blocked entirely while a cluster-managed wallet exists — members
        of a Syft Cluster can only use the managed credits wallet.
        """
        if wallet_type == WalletType.CLUSTER.value:
            raise HTTPException(
                status_code=403,
                detail="Cluster wallets are seeded by the cluster, not created here",
            )
        if await self._has_managed_wallet(tenant.id):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Wallet creation is disabled — this space uses a "
                    "managed credits wallet"
                ),
            )
        provider = self._get_provider(wallet_type)

        try:
            result = await provider.setup_wallet(raw_credentials)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        existing = await self.repository.get_by_type_and_currency(
            wallet_type, result.currency, tenant.id
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A {wallet_type} wallet for {result.currency} already exists. "
                    "Update the existing wallet instead."
                ),
            )

        config_cls = provider.config_class
        try:
            validated = config_cls(**result.credentials)
        except Exception as e:
            logger.error(f"Provider returned invalid credentials: {e}")
            raise HTTPException(
                status_code=500, detail="Wallet creation failed: invalid credentials"
            ) from None

        wallet = await self.repository.create_wallet(
            tenant_id=tenant.id,
            wallet_type=wallet_type,
            name=name or f"{wallet_type.upper()} Wallet",
            currency=result.currency,
            country=result.country,
            configuration=validated.model_dump(),
        )

        # SetupResult.display may be wallet-id-independent (Xendit, MPP) or
        # empty for providers that need the wallet id to compute the URL
        # (Stripe). Recompute via extract_display so the response is correct
        # for all providers, falling back to the setup-time display.
        display = provider.extract_display(wallet.configuration, wallet.id)
        if not display:
            display = result.display

        return WalletResponse(
            id=wallet.id,
            wallet_type=wallet.wallet_type,
            name=wallet.name,
            currency=wallet.currency,
            country=wallet.country,
            is_active=wallet.is_active,
            display=display,
            managed=wallet.wallet_type == WalletType.CLUSTER.value,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
        )

    # --- Credential updates (delegates to provider) ---

    async def update_wallet_credentials(
        self,
        wallet_id: UUID,
        updates: dict[str, Any],
        tenant: Tenant,
    ) -> WalletResponse:
        """Partially update wallet credentials via the provider.

        Currency edits are blocked downstream by the partial-update path;
        if a provider's update_credentials silently allows it, the entity
        column will diverge from configuration JSON. Currency lock is
        enforced at the provider layer (allowed update fields are listed
        explicitly).
        """
        wallet = await self.repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        if wallet.wallet_type == WalletType.CLUSTER.value:
            raise HTTPException(
                status_code=403,
                detail=(
                    "This wallet is managed by the cluster — its config "
                    "comes from the environment"
                ),
            )

        provider = self._get_provider(wallet.wallet_type)
        try:
            updated_config = provider.update_credentials(wallet.configuration, updates)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        wallet = await self.repository.update_configuration(
            wallet_id, tenant.id, updated_config
        )
        display = provider.extract_display(updated_config, wallet.id)
        return WalletResponse(
            id=wallet.id,
            wallet_type=wallet.wallet_type,
            name=wallet.name,
            currency=wallet.currency,
            country=wallet.country,
            is_active=wallet.is_active,
            display=display,
            managed=wallet.wallet_type == WalletType.CLUSTER.value,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at,
        )

    # --- Helpers ---

    def _extract_display(
        self, wallet_type: str, configuration: dict, wallet_id: UUID
    ) -> dict[str, Any]:
        """Extract safe display info by delegating to the provider."""
        provider = self.providers.get(wallet_type)
        if provider:
            return provider.extract_display(configuration, wallet_id)
        return {}
