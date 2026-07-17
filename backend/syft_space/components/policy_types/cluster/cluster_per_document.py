"""Cluster credits per-document payment policy.

All behavior is inherited from PrepaidBalancePerDocumentPolicy.
"""

from typing import ClassVar

from syft_space.components.policy_types.prepaid.per_document import (
    PrepaidBalancePerDocumentPolicy,
)
from syft_space.components.policy_types.prepaid.policy_config import (
    PrepaidPerDocumentConfig,
)


class ClusterPerDocumentPolicy(PrepaidBalancePerDocumentPolicy):
    PROVIDER_NAME: ClassVar[str] = "cluster"
    NAME: ClassVar[str] = "cluster_per_document"
    DESCRIPTION: ClassVar[str] = (
        "Pay-per-document billed against the space's managed credits wallet"
    )
    CONFIG_CLS = PrepaidPerDocumentConfig
