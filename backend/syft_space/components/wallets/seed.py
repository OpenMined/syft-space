"""Seed the managed cluster wallet from env at startup.

Spaces provisioned into a cluster get ``SYFT_CLUSTER_CREDITS_URL``
and ``SYFT_CLUSTER_CREDITS_TOKEN`` in their Secret. This hook upserts the
matching wallet so billing works without any UI action: create it when
missing, refresh the stored config when the env changed (token rotation
= Secret update + restart). No env → no-op (standalone spaces).
"""

import logging
from uuid import UUID

from syft_space.components.wallets.cluster.config import ClusterWalletConfig
from syft_space.components.wallets.repository import WalletRepository
from syft_space.components.wallets.wallet_configs import WalletType
from syft_space.config import app_settings

logger = logging.getLogger(__name__)

CLUSTER_WALLET_NAME = "Managed Credits Wallet"


async def seed_cluster_wallet(repository: WalletRepository, tenant_id: UUID) -> None:
    """Ensure the cluster wallet mirrors the ``SYFT_CLUSTER_CREDITS_*`` env."""
    if not (app_settings.cluster_credits_url and app_settings.cluster_credits_token):
        return

    config = ClusterWalletConfig(
        credits_url=str(app_settings.cluster_credits_url),
        service_token=app_settings.cluster_credits_token,
        currency=app_settings.cluster_credits_currency,
    )

    existing = await repository.get_by_type_and_currency(
        WalletType.CLUSTER.value, config.currency, tenant_id
    )
    if existing is None:
        wallet = await repository.create_wallet(
            tenant_id=tenant_id,
            wallet_type=WalletType.CLUSTER.value,
            name=CLUSTER_WALLET_NAME,
            currency=config.currency,
            country=None,
            configuration=config.model_dump(),
        )
        logger.info(f"Seeded cluster wallet {wallet.id} ({config.credits_url})")
    elif existing.configuration != config.model_dump():
        await repository.update_configuration(
            existing.id, tenant_id, config.model_dump()
        )
        logger.info(f"Updated cluster wallet {existing.id} config from env")
