"""Cluster wallet configuration.

The managed credits wallet for spaces running inside a Syft Cluster.
Balance and top-ups live at the cluster's credits service; the space
holds only the connection details. Seeded from ``SYFT_CLUSTER_CREDITS_*``
env at startup — never created through the wallet API.
"""

from typing import Any

from pydantic import BaseModel, Field

# Prepaid top-up catalog for the managed wallet, keyed by currency — what a
# marketplace advertises on a managed endpoint. CONTRACT MIRROR: the managing
# station prices bundle purchases from its own copy of this table; if the two
# drift, buyers are offered bundles the station won't sell.
CLUSTER_PREPAID_BUNDLES: dict[str, list[dict[str, Any]]] = {
    "IDR": [
        {"name": "Starter", "amount": 10_000},
        {"name": "Basic", "amount": 50_000},
        {"name": "Pro", "amount": 100_000},
        {"name": "Enterprise", "amount": 500_000},
    ],
    "PHP": [
        {"name": "Starter", "amount": 100},
        {"name": "Basic", "amount": 500},
        {"name": "Pro", "amount": 1_000},
        {"name": "Enterprise", "amount": 5_000},
    ],
    "SGD": [
        {"name": "Starter", "amount": 1},
        {"name": "Basic", "amount": 5},
        {"name": "Pro", "amount": 10},
        {"name": "Enterprise", "amount": 50},
    ],
    "MYR": [
        {"name": "Starter", "amount": 5},
        {"name": "Basic", "amount": 20},
        {"name": "Pro", "amount": 50},
        {"name": "Enterprise", "amount": 200},
    ],
    "VND": [
        {"name": "Starter", "amount": 25_000},
        {"name": "Basic", "amount": 100_000},
        {"name": "Pro", "amount": 250_000},
        {"name": "Enterprise", "amount": 1_000_000},
    ],
    "THB": [
        {"name": "Starter", "amount": 35},
        {"name": "Basic", "amount": 150},
        {"name": "Pro", "amount": 350},
        {"name": "Enterprise", "amount": 1_500},
    ],
}


def prepaid_bundles_for(currency: str) -> list[dict[str, Any]]:
    """Return the purchasable bundles for a currency (empty if unsupported)."""
    return CLUSTER_PREPAID_BUNDLES.get(currency, [])


class ClusterWalletConfig(BaseModel):
    """Connection details for the cluster credits service."""

    credits_url: str = Field(..., description="Base URL of the cluster credits API")
    service_token: str = Field(
        ..., description="Per-space bearer token (minted at provisioning)"
    )
    currency: str = Field(default="USD", description="Credits currency code")
