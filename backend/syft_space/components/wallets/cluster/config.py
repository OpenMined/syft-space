"""Cluster wallet configuration.

The managed credits wallet for spaces running inside a Syft Cluster.
Balance and top-ups live at the cluster's credits service; the space
holds only the connection details. Seeded from ``SYFT_CLUSTER_CREDITS_*``
env at startup — never created through the wallet API.
"""

from pydantic import BaseModel, Field


class ClusterWalletConfig(BaseModel):
    """Connection details for the cluster credits service."""

    credits_url: str = Field(..., description="Base URL of the cluster credits API")
    service_token: str = Field(
        ..., description="Per-space bearer token (minted at provisioning)"
    )
    currency: str = Field(default="USD", description="Credits currency code")
