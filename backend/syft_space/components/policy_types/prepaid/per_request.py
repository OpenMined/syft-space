"""Generic per-request prepaid-balance policy.

Wallet-scoped money-balance model. The policy carries only price and
applied_to. Currency and bundles live on the Wallet (linked via
Policy.wallet_id), so the same balance is fungible across all endpoints
that reference the same wallet.

Reserves price in pre_hook; cancels the reservation in post_hook if the
response is empty (no summary, no documents). Concrete provider
subclasses inherit unchanged behavior and only declare identity fields.
"""

from typing import Any

from syft_space.components.policy_types.interfaces import (
    BalanceShortfallError,
    PolicyContext,
    PolicyViolationError,
    add_response_cost,
)
from syft_space.components.policy_types.prepaid.payment_policy import (
    PrepaidBalancePaymentPolicyBase,
)


class PrepaidBalancePerRequestPolicy(PrepaidBalancePaymentPolicyBase):
    """Prepaid-balance per-request pricing policy."""

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Reserve price from the user's wallet balance."""
        if not configs:
            return context

        user_email = str(context.sender_email)
        price = self._find_matching_price(user_email, configs)

        if price is None:
            message = "No pricing tier matches your account"
            raise PolicyViolationError(
                message=message,
                policy_type=self.NAME,
                outcome="policy_violation",
                metadata_entry=self._rejected_entry(
                    context,
                    reason_code="NO_PRICING_TIER",
                    reason=message,
                ),
            )

        charger = context.payment_chargers.prepaid()
        try:
            transaction_id = await charger.reserve(
                user_email=user_email,
                amount=price,
                charge_unit="request",
                charge_quantity=1,
            )
        except BalanceShortfallError as exc:
            message = "Insufficient balance. Please purchase more credits."
            raise PolicyViolationError(
                message=message,
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "price": price,
                    "currency": exc.currency,
                },
                outcome="policy_violation",
                metadata_entry=self._rejected_entry(
                    context,
                    reason_code="INSUFFICIENT_BALANCE",
                    reason=message,
                    amount=price,
                    currency=exc.currency,
                ),
            ) from exc

        # Generic key — metadata is scoped to this policy invocation.
        context.metadata["prepaid_transaction_id"] = transaction_id
        context.metadata["prepaid_price"] = price

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Cancel the reservation if the response is empty (no useful content)."""
        if not configs:
            return context

        transaction_id = context.metadata.get("prepaid_transaction_id")
        price = context.metadata.get("prepaid_price")

        if not transaction_id:
            return context

        charger = context.payment_chargers.prepaid()
        response = context.response or {}

        has_summary = bool(
            response.get("summary") and response["summary"].get("message")
        )
        has_documents = bool(
            response.get("references") and response["references"].get("documents")
        )

        if has_summary or has_documents:
            add_response_cost(response, price, charger.currency)
            context.add_policy_metadata(
                self._charged_entry(
                    context,
                    amount=price,
                    currency=charger.currency,
                    wallet_type=charger.wallet_type,
                    transaction_id=transaction_id,
                )
            )
            return context

        # Cancel the reservation since the response is empty. Record zero
        # so consumers see this policy applied with no net charge.
        await charger.cancel(transaction_id)
        add_response_cost(response, 0, charger.currency)
        context.add_policy_metadata(
            self._refunded_entry(
                context,
                currency=charger.currency,
                wallet_type=charger.wallet_type,
                transaction_id=transaction_id,
            )
        )

        return context
