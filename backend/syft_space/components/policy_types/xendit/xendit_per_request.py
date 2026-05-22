"""Xendit per-request payment policy.

All behavior is inherited from PrepaidBalancePerRequestPolicy.
"""

from typing import ClassVar

from syft_space.components.policy_types.prepaid.per_request import (
    PrepaidBalancePerRequestPolicy,
)
from syft_space.components.policy_types.prepaid.policy_config import (
    PrepaidPerRequestConfig,
)


class XenditPerRequestPolicy(PrepaidBalancePerRequestPolicy):
    PROVIDER_NAME: ClassVar[str] = "xendit"
    NAME: ClassVar[str] = "xendit_per_request"
    DESCRIPTION: ClassVar[str] = (
        "Pay-per-request billed against a Xendit wallet's prepaid balance"
    )
    CONFIG_CLS = PrepaidPerRequestConfig
