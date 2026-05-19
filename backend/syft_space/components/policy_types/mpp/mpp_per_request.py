"""MPP per-request policy type for per-query payments via Machine Payments Protocol."""

from typing import Any, ClassVar

from loguru import logger
from mpp import Challenge

from syft_space.components.policy_types.interfaces import (
    Capabilities,
    PaymentRequiredError,
    PolicyContext,
    PolicyViolationError,
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
            raise PaymentRequiredError(
                www_authenticate=www_authenticate,
                description=f"Payment of ${price} required to query this endpoint",
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
        """Post-hook: surface cost+currency on the response and the receipt
        reference for the Payment-Receipt header.

        Cost is only written when a charge actually happened (receipt
        present). Free-tier requests leave cost/currency as None — absence
        is meaningful for downstream consumers.
        """
        receipt_info = context.metadata.get("mpp_receipt")

        if receipt_info and context.response:
            price = self._find_matching_price(context.sender_email, configs)
            if price is not None and price > 0:
                if context.response.get("summary"):
                    context.response["summary"]["cost"] = price
                    context.response["summary"]["currency"] = "USD"
                if context.response.get("references"):
                    context.response["references"]["cost"] = price
                    context.response["references"]["currency"] = "USD"

        if receipt_info:
            context.metadata["payment_receipt_header"] = receipt_info.get("reference")

        return context
