"""Generic per-document prepaid-balance policy.

Charges price per retrieved document, settled in post_hook once the
search has returned. A cheap pre_hook floor check refuses the request
when the user's balance can't cover even a single document.

Concrete provider subclasses inherit unchanged behavior and only declare
identity fields.
"""

from typing import Any

from syft_space.components.policy_types.interfaces import (
    BalanceShortfallError,
    Capabilities,
    PolicyContext,
    PolicyViolationError,
    add_response_cost,
)
from syft_space.components.policy_types.prepaid.payment_policy import (
    PrepaidBalancePaymentPolicyBase,
)


class PrepaidBalancePerDocumentPolicy(PrepaidBalancePaymentPolicyBase):
    """Prepaid-balance per-document pricing policy.

    Pre-hook: cheap floor check (balance >= price) so a user with zero
    balance can't keep triggering search compute.

    Post-hook: count documents in the response, settle for
    ``count * price`` via the same BalanceService.reserve path used by
    per-request. On insufficient balance the response is dropped.
    """

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(
            requires_wallet=True,
            required_wallet_type=cls.PROVIDER_NAME,
            requires_endpoint_dataset=True,
        )

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Floor check: balance must cover at least one document."""
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
        balance = await charger.get_balance(user_email)
        if balance < price:
            message = "Insufficient balance. Please purchase more credits."
            raise PolicyViolationError(
                message=message,
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "balance": balance,
                    "price": price,
                    "currency": charger.currency,
                },
                outcome="policy_violation",
                metadata_entry=self._rejected_entry(
                    context,
                    reason_code="INSUFFICIENT_BALANCE",
                    reason=message,
                    amount=price,
                    currency=charger.currency,
                    details={"balance": balance, "price": price},
                ),
            )

        context.metadata["prepaid_per_doc_price"] = price

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Settle for actual document count.

        Reserve happens here (not pre_hook) because we don't know the
        document count until the search returns. On insufficient balance
        we raise; an empty response means no documents were charged.
        """
        if not configs:
            return context

        price = context.metadata.get("prepaid_per_doc_price")
        if price is None:
            return context

        response = context.response or {}
        references = response.get("references") or {}
        documents = references.get("documents") or []
        count = len(documents)
        charger = context.payment_chargers.prepaid()

        # No documents → no charge. Record zero so the response indicates
        # this policy applied with no net cost.
        if count == 0:
            add_response_cost(response, 0, charger.currency)
            context.add_policy_metadata(
                self._free_entry(
                    context,
                    currency=charger.currency,
                    details={"documents": count},
                )
            )
            return context

        total = count * price
        user_email = str(context.sender_email)

        try:
            transaction_id = await charger.reserve(
                user_email=user_email,
                amount=total,
                charge_unit="document",
                charge_quantity=count,
            )
        except BalanceShortfallError as exc:
            message = "Insufficient balance for the documents retrieved."
            raise PolicyViolationError(
                message=message,
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "documents": count,
                    "price": price,
                    "total": total,
                    "currency": exc.currency,
                },
                outcome="policy_violation",
                metadata_entry=self._rejected_entry(
                    context,
                    reason_code="INSUFFICIENT_BALANCE",
                    reason=message,
                    amount=total,
                    currency=exc.currency,
                    details={"documents": count, "price": price},
                ),
            ) from exc

        add_response_cost(response, total, charger.currency)
        context.add_policy_metadata(
            self._charged_entry(
                context,
                amount=total,
                currency=charger.currency,
                wallet_type=charger.wallet_type,
                transaction_id=transaction_id,
                details={"documents": count},
            )
        )

        return context
