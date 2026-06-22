"""MPP per-document policy type.

Charges price per retrieved document via the Machine Payments Protocol,
settled in post_hook once the search has returned. MPP has no server-side
balance, so pre_hook can only verify a credential is present (issuing a
402 challenge if missing) — the real charge happens post-search.
"""

from typing import Any, ClassVar

from loguru import logger
from mpp import Challenge

from syft_space.components.policy_types.interfaces import (
    Capabilities,
    PaymentRequiredError,
    PolicyContext,
    PolicyViolationError,
    add_response_cost,
)
from syft_space.components.policy_types.mpp.mpp_payment_policy import (
    MppPaymentPolicy,
)
from syft_space.components.policy_types.mpp.policy_config import MppPerDocumentConfig


class MppPerDocumentPolicy(MppPaymentPolicy):
    """MPP-based per-document payment policy using Tempo blockchain.

    Pre-hook: if no X-Payment credential is presented, issue a 402 challenge
    sized for a single document so the client knows what to pay. No charge
    happens here; we just gate on credential presence.

    Post-hook: count documents, call ``mpp.charge`` for ``count * price``.
    If the credential can't cover the actual total, MPP returns a Challenge
    → PaymentRequiredError; the route layer surfaces it as 402 and the
    response body is never returned.
    """

    NAME: ClassVar[str] = "mpp_per_document"
    DESCRIPTION: ClassVar[str] = (
        "Charge per retrieved document using the Machine Payments "
        "Protocol (MPP) on Tempo blockchain"
    )
    CONFIG_CLS = MppPerDocumentConfig

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(
            requires_wallet=True,
            required_wallet_type="mpp",
            requires_endpoint_dataset=True,
        )

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Resolve the per-document price for this user and stash it.

        Real charging happens in post_hook once the document count is known.
        If the request lacks a valid X-Payment credential, post_hook's
        charge call returns a Challenge → PaymentRequiredError → HTTP 402.
        (We could 402 eagerly here, but search compute is cheap enough that
        the savings don't justify exposing credential presence on the
        charger Protocol. Revisit if search costs grow.)
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

        context.metadata["mpp_per_doc_price"] = price
        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Charge count * price; 402 on credential shortfall.

        Cost is only written when a charge actually happened. Free-tier and
        zero-document requests leave cost/currency as None — absence is
        meaningful for downstream consumers.
        """
        price = context.metadata.get("mpp_per_doc_price")
        if price is None or context.response is None:
            return context

        response = context.response
        references = response.get("references") or {}
        documents = references.get("documents") or []
        count = len(documents)

        # Free tier (price=0) or empty result (count=0): record zero so the
        # response reflects "this policy applied with no cost", then exit
        # before doing the (no-op) charge.
        if price == 0 or count == 0:
            add_response_cost(response, 0, "USD")
            context.add_policy_metadata(
                self._free_entry(context, details={"documents": count})
            )
            return context

        total = count * price
        charger = context.payment_chargers.mpp()
        result = await charger.charge(
            amount=total,
            description=f"Query endpoint: {context.endpoint_slug} ({count} documents)",
        )

        if isinstance(result, Challenge):
            www_authenticate = result.to_www_authenticate(realm=context.endpoint_slug)
            description = f"Payment of ${total} required for {count} documents"
            raise PaymentRequiredError(
                www_authenticate=www_authenticate,
                description=description,
                metadata_entry=self._rejected_entry(
                    context,
                    reason_code="PAYMENT_REQUIRED",
                    reason=description,
                    amount=total,
                    currency="USD",
                    details={"documents": count},
                ),
            )

        credential, receipt = result
        context.metadata["mpp_credential"] = {"source": credential.source}
        context.metadata["mpp_receipt"] = {
            "reference": receipt.reference,
            "status": receipt.status,
            "external_id": receipt.external_id,
        }

        add_response_cost(context.response, total, "USD")

        context.add_policy_metadata(
            self._charged_entry(
                context,
                amount=total,
                reference=receipt.reference,
                external_id=receipt.external_id,
                details={"documents": count},
            )
        )

        logger.info(
            f"MPP per-document payment verified: ${total} from "
            f"{credential.source} for endpoint {context.endpoint_slug} "
            f"({count} documents)"
        )
        return context
