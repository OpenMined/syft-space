"""Cluster wallet provider.

Exists for display/config plumbing only — cluster wallets are seeded
from env at startup (see ``wallets/seed.py``), never created through
the wallet API.
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
        the wallet); the space only ever debits against it. Bundles come
        from the currency-keyed catalog — the same across every space on
        this wallet, so a marketplace renders one consistent set.
        """
        config = ClusterWalletConfig(**configuration)
        bundles = prepaid_bundles_for(config.currency)
        if not app_settings.cluster.public_url:
            return PaymentInfo(bundles, None, None, None, managed=True)
        base = str(app_settings.cluster.public_url).rstrip("/")
        prefix = f"{base}/api/v1/credits"
        return PaymentInfo(
            bundles=bundles,
            payment_url=f"{prefix}/checkout",
            invoices_url=f"{prefix}/me",
            credits_url=f"{prefix}/me",
            managed=True,
            station_url=base,
        )
