"""MPP per-request policy type for per-query payments via Machine Payments Protocol."""

from typing import Any, ClassVar

from loguru import logger
from mpp import Challenge

from syft_space.components.policy_types.interfaces import (
    Capabilities,
    PaymentRequiredError,
    PolicyContext,
    PolicyViolationError,
    ReasonCode,
    add_response_cost,
)
from syft_space.components.policy_types.mpp.mpp_payment_policy import (
    MppPaymentPolicy,
)
from syft_space.components.policy_types.mpp.policy_config import MppPerRequestConfig


class MppPerRequestPolicy(MppPaymentPolicy):
    """MPP-based payment policy using Tempo blockchain."""

    NAME: ClassVar[str] = "mpp_per_request"
    DESCRIPTION: ClassVar[str] = (
        "Charge per query using the Machine Payments Protocol (MPP) on Tempo blockchain"
    )
    CONFIG_CLS = MppPerRequestConfig

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(requires_wallet=True, required_wallet_type="mpp")

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Pre-hook: issue 402 challenge or verify payment credential.

        Flow:
        1. Match sender_email against pricing tiers to determine price
        2. If price is 0, allow through (free tier)
        3. Call MppCharger.charge() — it wraps the bound X-Payment credential
        4. If charge returns Challenge: raise PaymentRequiredError (→ HTTP 402)
        5. Otherwise stash credential/receipt for the post-hook
        """
        sender_email = context.sender_email

        price = self._find_matching_price(sender_email, configs)
        if price is None:
            if configs:
                raise PolicyViolationError(
                    message="No pricing tier matches your account",
                    policy_type=self.NAME,
                )
            return context

        # Free tier - skip payment
        if price == 0:
            return context

        charger = context.payment_chargers.mpp()
        result = await charger.charge(
            amount=price,
            description=f"Query endpoint: {context.endpoint_slug}",
        )

        if isinstance(result, Challenge):
            www_authenticate = result.to_www_authenticate(realm=context.endpoint_slug)
            description = f"Payment of ${price} required to query this endpoint"
            raise PaymentRequiredError(
                www_authenticate=www_authenticate,
                description=description,
                metadata_entry=self._rejected_entry(
                    context,
                    reason_code=ReasonCode.PAYMENT_REQUIRED,
                    reason=description,
                    amount=price,
                    currency="USD",
                ),
            )

        credential, receipt = result
        context.metadata["mpp_credential"] = {
            "source": credential.source,
        }
        context.metadata["mpp_receipt"] = {
            "reference": receipt.reference,
            "status": receipt.status,
            "external_id": receipt.external_id,
        }

        logger.info(
            f"MPP payment verified: ${price} from {credential.source} "
            f"for endpoint {context.endpoint_slug}"
        )

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook: add this policy's charge to the response total and
        emit its policy-metadata entry.

        The price from the matched tier is always added (including 0 for
        free tiers) so the response always reflects what *this policy*
        contributed. If pre_hook raised, post_hook doesn't run — so
        reaching here means the user matched a tier.
        """
        if context.response is None:
            return context

        price = self._find_matching_price(context.sender_email, configs)
        if price is None:
            return context

        add_response_cost(context.response, price, "USD")

        if price == 0:
            context.add_policy_metadata(self._free_entry(context))
            return context

        receipt_info = context.metadata.get("mpp_receipt") or {}
        context.add_policy_metadata(
            self._charged_entry(
                context,
                amount=price,
                reference=receipt_info.get("reference"),
                external_id=receipt_info.get("external_id"),
            )
        )

        return context
