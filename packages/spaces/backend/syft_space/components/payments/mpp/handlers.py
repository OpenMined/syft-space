"""MPP payment handlers — balance and transaction queries."""

from uuid import UUID

from fastapi import HTTPException

from syft_space.components.payments.mpp.schemas import (
    MppBalanceResponse,
    TransactionResponse,
)
from syft_space.components.payments.mpp.tempo_utils import (
    get_wallet_balance,
    get_wallet_transactions,
)
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.mpp.config import MppWalletConfig
from syft_space.components.wallets.repository import WalletRepository
from syft_space.components.wallets.wallet_configs import WalletType

# Soft offset (in pathUSD) subtracted from the displayed wallet balance.
# The Tempo faucet drops 1M pathUSD on every new wallet; we hide all but ~$20
# of it so users see a realistic-looking starting balance.
FAUCET_DISPLAY_OFFSET = 999_980


class MppPaymentHandler:
    """Handler for MPP financial data (balance + transactions).

    Queries the Tempo blockchain for wallet balance and transfer events.
    """

    def __init__(self, wallet_repository: WalletRepository) -> None:
        self.wallet_repository = wallet_repository

    async def _get_mpp_wallet_config(
        self, wallet_id: UUID, tenant: Tenant
    ) -> MppWalletConfig:
        """Load and validate an MPP wallet by ID."""
        wallet = await self.wallet_repository.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        if wallet.wallet_type != WalletType.MPP:
            raise HTTPException(
                status_code=400,
                detail="This endpoint only supports MPP wallets",
            )
        return MppWalletConfig(**wallet.configuration)

    async def get_balance(self, wallet_id: UUID, tenant: Tenant) -> MppBalanceResponse:
        """Get MPP wallet balance from Tempo blockchain."""
        config = await self._get_mpp_wallet_config(wallet_id, tenant)
        balance = await get_wallet_balance(config.wallet_address)
        recent_txs = await get_wallet_transactions(config.wallet_address)
        return MppBalanceResponse(
            balance=max(0.0, balance - FAUCET_DISPLAY_OFFSET),
            currency="USD",
            recent_transactions=[TransactionResponse(**tx) for tx in recent_txs[:10]],
            wallet_configured=True,
        )

    async def get_transactions(
        self, wallet_id: UUID, tenant: Tenant
    ) -> list[TransactionResponse]:
        """Get MPP wallet transactions from Tempo blockchain."""
        config = await self._get_mpp_wallet_config(wallet_id, tenant)
        txs = await get_wallet_transactions(config.wallet_address)
        return [TransactionResponse(**tx) for tx in txs]
