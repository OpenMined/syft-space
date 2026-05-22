"""Stripe per-request payment policy.

All behavior is inherited from PrepaidBalancePerRequestPolicy — Stripe
and Xendit deduct from the same UserBalance rows via BalanceService;
only the top-up rail differs.
"""

from typing import ClassVar

from syft_space.components.policy_types.prepaid.per_request import (
    PrepaidBalancePerRequestPolicy,
)
from syft_space.components.policy_types.prepaid.policy_config import (
    PrepaidPerRequestConfig,
)


class StripePerRequestPolicy(PrepaidBalancePerRequestPolicy):
    PROVIDER_NAME: ClassVar[str] = "stripe"
    NAME: ClassVar[str] = "stripe_per_request"
    DESCRIPTION: ClassVar[str] = (
        "Pay-per-request billed against a Stripe wallet's prepaid balance"
    )
    CONFIG_CLS = PrepaidPerRequestConfig
