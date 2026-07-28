"""Cluster wallet provider.

Cluster wallets are seeded from env at startup (see ``wallets/seed.py``),
never created through the wallet API. This provider covers display/config
plumbing plus the payment surface published on paid endpoints — which for
a managed wallet points buyers at the station, not this space.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from syft_space.components.wallets.cluster.config import (
    ClusterWalletConfig,
    prepaid_bundles_for,
)
from syft_space.components.wallets.interfaces import PaymentInfo, SetupResult
from syft_space.config import app_settings


class ClusterWalletProvider:
    """WalletProvider impl for the managed cluster wallet."""

    @property
    def config_class(self) -> type[BaseModel]:
        return ClusterWalletConfig

    async def setup_wallet(self, raw_credentials: dict[str, Any]) -> SetupResult:
        raise ValueError(
            "This wallet is managed externally and cannot be created through the API"
        )

    def extract_display(
        self, configuration: dict[str, Any], wallet_id: UUID
    ) -> dict[str, Any]:
        """Safe display info — never the service token."""
        return {"managed_by": app_settings.cluster.managed_by}

    def payment_info(
        self, configuration: dict[str, Any], wallet_id: UUID
    ) -> PaymentInfo | None:
        """Point buyers at the managing station rather than this space.

        Balance, top-ups, and checkout all live on the station (which owns
        the wallet); the space only ever debits against it. Bundles prefer
        the station-injected catalog (``SYFT_CLUSTER_BUNDLES`` — the exact
        set the station will price); the static per-currency table is the
        fallback for spaces started before their station injected one.
        """
        config = ClusterWalletConfig(**configuration)
        cluster = app_settings.cluster
        bundles = cluster.bundles or prepaid_bundles_for(config.currency)
        owner = cluster.wallet_owner
        if not cluster.public_url:
            return PaymentInfo(bundles, None, None, None, owner=owner)
        base = str(cluster.public_url).rstrip("/")
        # Wallet-id-scoped, with the same suffixes as the self-hosted gateway
        # (/payments/gateway/wallets/{id}/…): a marketplace buys, dedups, and
        # reads balances through one client regardless of who hosts the wallet.
        prefix = f"{base}/api/v1/credits/{wallet_id}"
        return PaymentInfo(
            bundles=bundles,
            payment_url=f"{prefix}/invoices",
            invoices_url=f"{prefix}/invoices/me",
            credits_url=f"{prefix}/balance",
            owner=owner,
        )
