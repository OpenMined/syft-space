"""Stripe per-request policy type implementation.

Wallet-scoped money-balance model. The policy carries only price and
applied_to. Currency and bundles live on the Wallet (linked via
Policy.wallet_id), so the same balance is fungible across all endpoints
that reference the same wallet.

Behaviorally identical to ``XenditPerRequestPolicy`` — both providers
deduct from the same ``UserBalance`` rows via ``BalanceService`` — only
the top-up rail differs.
"""

from typing import Any, ClassVar

from syft_space.components.policy_types.interfaces import (
    BalanceShortfallError,
    PolicyContext,
    PolicyViolationError,
    add_response_cost,
)
from syft_space.components.policy_types.stripe.policy_config import (
    StripePerRequestConfig,
)
from syft_space.components.policy_types.stripe.stripe_payment_policy import (
    StripePaymentPolicy,
)


class StripePerRequestPolicy(StripePaymentPolicy):
    """Stripe per-request pricing policy.

    Admin sets price. End users buy money bundles via the linked wallet,
    and balance is deducted by price on each query. Balance is fungible
    across all endpoints sharing the wallet.
    """

    NAME: ClassVar[str] = "stripe_per_request"
    DESCRIPTION: ClassVar[str] = (
        "Pay-per-request billed against a Stripe wallet's prepaid balance"
    )
    CONFIG_CLS = StripePerRequestConfig

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Reserve price from the user's wallet balance."""
        if not configs:
            return context

        user_email = str(context.sender_email)
        price = self._find_matching_price(user_email, configs)

        if price is None:
            raise PolicyViolationError(
                message="No pricing tier matches your account",
                policy_type=self.NAME,
            )

        charger = context.payment_chargers.stripe()
        try:
            transaction_id = await charger.reserve(
                user_email=user_email,
                amount=price,
                charge_unit="request",
                charge_quantity=1,
            )
        except BalanceShortfallError as exc:
            raise PolicyViolationError(
                message="Insufficient balance. Please purchase more credits.",
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "price": price,
                    "currency": exc.currency,
                },
            ) from exc

        context.metadata["stripe_transaction_id"] = transaction_id
        context.metadata["stripe_price"] = price

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Cancel the reservation if the response is empty (no useful content)."""
        if not configs:
            return context

        transaction_id = context.metadata.get("stripe_transaction_id")
        price = context.metadata.get("stripe_price")

        if not transaction_id:
            return context

        charger = context.payment_chargers.stripe()
        response = context.response or {}

        has_summary = bool(
            response.get("summary") and response["summary"].get("message")
        )
        has_documents = bool(
            response.get("references") and response["references"].get("documents")
        )

        if has_summary or has_documents:
            add_response_cost(response, price, charger.currency)
            return context

        # Cancel the reservation since the response is empty (no useful
        # content). Record zero on the response so consumers see this
        # policy applied with no net charge.
        await charger.cancel(transaction_id)
        add_response_cost(response, 0, charger.currency)

        return context
