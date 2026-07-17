"""Wallet configuration registry.

Imports config classes from each wallet type and builds the registries.
Each type owns its config definition — this module aggregates them.

Same pattern as policy_types/__init__.py registering policy types.
"""

from enum import Enum

from pydantic import BaseModel

from syft_space.components.wallets.cluster.config import ClusterWalletConfig
from syft_space.components.wallets.gateway.xendit.config import XenditWalletConfig
from syft_space.components.wallets.mpp.config import MppWalletConfig


class WalletCategory(str, Enum):
    """Wallet category — determines billing model and financial views."""

    MPP = "mpp"
    GATEWAY = "gateway"
    # Managed cluster credits: no local top-ups/invoices, balance lives at
    # the cluster's credits service, spend history is journaled locally.
    CLUSTER = "cluster"


class WalletType(str, Enum):
    """Specific wallet type — maps to a provider and config class."""

    MPP = "mpp"
    XENDIT = "xendit"
    CLUSTER = "cluster"

    @property
    def category(self) -> WalletCategory:
        return WALLET_TYPE_CATEGORIES[self]


# Maps each wallet type to its category
WALLET_TYPE_CATEGORIES: dict[WalletType, WalletCategory] = {
    WalletType.MPP: WalletCategory.MPP,
    WalletType.XENDIT: WalletCategory.GATEWAY,
    WalletType.CLUSTER: WalletCategory.CLUSTER,
}

# Maps each wallet type to its Pydantic config class
WALLET_CONFIG_REGISTRY: dict[WalletType, type[BaseModel]] = {
    WalletType.MPP: MppWalletConfig,
    WalletType.XENDIT: XenditWalletConfig,
    WalletType.CLUSTER: ClusterWalletConfig,
}

__all__ = [
    "ClusterWalletConfig",
    "MppWalletConfig",
    "XenditWalletConfig",
    "WalletCategory",
    "WalletType",
    "WALLET_CONFIG_REGISTRY",
    "WALLET_TYPE_CATEGORIES",
]
