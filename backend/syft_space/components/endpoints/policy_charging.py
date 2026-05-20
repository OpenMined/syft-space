"""Per-request payment-charger factory used by the query handler.

An endpoint is constrained to a single wallet (enforced at policy-attach
time by CapabilityChecker, which rejects sibling policies pointing at a
different wallet), so this builds at most one charger per request. The
query handler exposes the resulting bag on PolicyContext; policies
retrieve the charger they need by mechanism.

Adding a new payment mechanism (stripe, razorpay, ...) is two touches in
this file (a new field on PaymentChargers + a new branch in the builder)
plus a concrete adapter under payments/. No policy code changes.
"""

from uuid import UUID

from syft_space.components.payments.gateway.balance_service import BalanceService
from syft_space.components.payments.gateway.xendit.charger import (
    XenditChargingAdapter,
)
from syft_space.components.payments.mpp.charger import MppChargingAdapter
from syft_space.components.policy_types.interfaces import (
    MppCharger,
    PaymentChargers,
    XenditCharger,
)
from syft_space.components.wallets.entities import Wallet


def build_payment_chargers(
    *,
    wallet: Wallet | None,
    balance_service: BalanceService | None,
    tenant_id: UUID,
    endpoint_id: UUID,
    endpoint_slug: str,
    x_payment: str | None,
) -> PaymentChargers:
    """Construct a PaymentChargers bag for the current request.

    `wallet=None` means no payment policy is attached; both chargers stay
    absent and any downstream `.mpp()` / `.xendit()` call would (correctly)
    raise. The Xendit charger is also skipped if no BalanceService is
    wired — surfacing the missing dependency loudly.
    """
    mpp: MppCharger | None = None
    xendit: XenditCharger | None = None

    if wallet is not None:
        if wallet.wallet_type == "mpp":
            mpp = MppChargingAdapter(
                wallet_address=wallet.configuration.get("wallet_address", ""),
                secret_key=wallet.configuration.get("mpp_secret_key", ""),
                realm=endpoint_slug,
                x_payment=x_payment,
            )
        elif wallet.wallet_type == "xendit" and balance_service is not None:
            xendit = XenditChargingAdapter(
                balance_service=balance_service,
                wallet_id=wallet.id,
                currency=wallet.currency,
                tenant_id=tenant_id,
                endpoint_id=endpoint_id,
            )

    return PaymentChargers(mpp=mpp, xendit=xendit)
