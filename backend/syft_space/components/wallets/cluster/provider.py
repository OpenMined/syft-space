"""Cluster wallet provider.

Exists for display/config plumbing only — cluster wallets are seeded
from env at startup (see ``wallets/seed.py``), never created through
the wallet API.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from syft_space.components.wallets.cluster.config import ClusterWalletConfig
from syft_space.components.wallets.interfaces import SetupResult


class ClusterWalletProvider:
    """WalletProvider impl for the managed cluster wallet."""

    @property
    def config_class(self) -> type[BaseModel]:
        return ClusterWalletConfig

    async def setup_wallet(self, raw_credentials: dict[str, Any]) -> SetupResult:
        raise ValueError(
            "Cluster wallets are managed by the cluster and cannot be "
            "created through the API"
        )

    def extract_display(
        self, configuration: dict[str, Any], wallet_id: UUID
    ) -> dict[str, Any]:
        """Safe display info — never the service token."""
        return {"managed_by": "Your cluster"}
