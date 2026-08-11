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
    cluster = app_settings.cluster
    if not (cluster.credits_url and cluster.credits_token):
        return

    config = ClusterWalletConfig(
        credits_url=str(cluster.credits_url),
        service_token=cluster.credits_token,
        currency=cluster.credits_currency,
    )

    # The station passes its own wallet id so every space it provisions adopts
    # the same one — a marketplace then groups them as a single balance.
    wallet_id = cluster.credits_wallet_id

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
            wallet_id=wallet_id,
        )
        logger.info(f"Seeded cluster wallet {wallet.id} ({config.credits_url})")
        return

    if wallet_id is not None and existing.id != wallet_id:
        # A cluster wallet seeded before this id was injected. Its id can't be
        # rewritten safely (payment policies reference it), so the space must
        # be re-provisioned to pick up the shared id.
        logger.warning(
            f"Cluster wallet {existing.id} predates the station wallet id "
            f"{wallet_id}; re-provision this space so its endpoints publish "
            "the shared id."
        )
    if existing.configuration != config.model_dump():
        await repository.update_configuration(
            existing.id, tenant_id, config.model_dump()
        )
        logger.info(f"Updated cluster wallet {existing.id} config from env")
