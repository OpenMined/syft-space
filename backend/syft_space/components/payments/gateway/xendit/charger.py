"""Xendit charging adapter — concrete impl of policy_types.XenditCharger.

The implementation is provider-agnostic — Stripe uses the identical shape —
so the class lives in ``balance_charger.WalletBalanceCharger`` and is
re-exported here as an alias to keep existing import paths stable.
"""

from syft_space.components.payments.gateway.balance_charger import (
    WalletBalanceCharger,
)

XenditChargingAdapter = WalletBalanceCharger

__all__ = ["XenditChargingAdapter"]
