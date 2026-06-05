"""Xendit per-document payment policy.

All behavior is inherited from PrepaidBalancePerDocumentPolicy.
"""

from typing import ClassVar

from syft_space.components.policy_types.prepaid.per_document import (
    PrepaidBalancePerDocumentPolicy,
)
from syft_space.components.policy_types.prepaid.policy_config import (
    PrepaidPerDocumentConfig,
)


class XenditPerDocumentPolicy(PrepaidBalancePerDocumentPolicy):
    PROVIDER_NAME: ClassVar[str] = "xendit"
    NAME: ClassVar[str] = "xendit_per_document"
    DESCRIPTION: ClassVar[str] = (
        "Pay-per-document billed against a Xendit wallet's prepaid balance"
    )
    CONFIG_CLS = PrepaidPerDocumentConfig
