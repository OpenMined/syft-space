"""Stripe per-document payment policy.

All behavior is inherited from PrepaidBalancePerDocumentPolicy.
"""

from typing import ClassVar

from syft_space.components.policy_types.prepaid.per_document import (
    PrepaidBalancePerDocumentPolicy,
)
from syft_space.components.policy_types.prepaid.policy_config import (
    PrepaidPerDocumentConfig,
)


class StripePerDocumentPolicy(PrepaidBalancePerDocumentPolicy):
    PROVIDER_NAME: ClassVar[str] = "stripe"
    NAME: ClassVar[str] = "stripe_per_document"
    DESCRIPTION: ClassVar[str] = (
        "Pay-per-document billed against a Stripe wallet's prepaid balance"
    )
    CONFIG_CLS = PrepaidPerDocumentConfig
