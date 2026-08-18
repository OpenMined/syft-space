"""Cluster credits per-request payment policy.

All behavior is inherited from PrepaidBalancePerRequestPolicy.
"""

from typing import ClassVar

from syft_space.components.policy_types.prepaid.per_request import (
    PrepaidBalancePerRequestPolicy,
)
from syft_space.components.policy_types.prepaid.policy_config import (
    PrepaidPerRequestConfig,
)


class ClusterPerRequestPolicy(PrepaidBalancePerRequestPolicy):
    PROVIDER_NAME: ClassVar[str] = "cluster"
    NAME: ClassVar[str] = "cluster_per_request"
    DESCRIPTION: ClassVar[str] = (
        "Pay-per-request billed against the space's managed credits wallet"
    )
    CONFIG_CLS = PrepaidPerRequestConfig
