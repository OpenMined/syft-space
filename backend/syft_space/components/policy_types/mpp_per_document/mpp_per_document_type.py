"""MPP per-document policy type.

Charges price_per_document per retrieved document via the Machine Payments
Protocol, settled in post_hook once the search has returned. MPP has no
server-side balance, so pre_hook can only verify a credential is present
(issuing a 402 challenge if missing) — the real charge happens post-search.
"""

from typing import Any, ClassVar

from loguru import logger
from mpp import Challenge
from mpp.methods.tempo import PATH_USD, TESTNET_CHAIN_ID, ChargeIntent, tempo
from mpp.server import Mpp
from pydantic import BaseModel, Field

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    Capabilities,
    PaymentRequiredError,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.shared.utils import matches_any_pattern
from syft_space.config import app_settings


class MppPerDocumentConfig(BaseModel):
    """Configuration for MPP per-document policy."""

    price_per_document: float = Field(
        ge=0, description="Price per retrieved document in USD"
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user email patterns. Use '*' for all users.",
    )


class MppPerDocumentPolicy(BasePolicyType):
    """MPP-based per-document payment policy using Tempo blockchain.

    Pre-hook: if no X-Payment credential is presented, issue a 402 challenge
    sized for a single document so the client knows what to pay. No charge
    happens here; we just gate on credential presence.

    Post-hook: count documents, call ``mpp.charge`` for
    ``count * price_per_document``. If the credential can't cover the actual
    total, MPP returns a Challenge → PaymentRequiredError; the route layer
    surfaces it as 402 and the response body is never returned.
    """

    NAME: ClassVar[str] = "mpp_per_document"
    _mpp_instances: ClassVar[dict[str, Mpp]] = {}

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(
            requires_wallet=True,
            required_wallet_type="mpp",
            requires_endpoint_dataset=True,
        )

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return (
            "Charge per retrieved document using the Machine Payments "
            "Protocol (MPP) on Tempo blockchain"
        )

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return MppPerDocumentConfig.model_json_schema()

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        validated = MppPerDocumentConfig(**config)
        return validated.model_dump()

    def __init__(self) -> None:
        pass

    def _find_matching_price(
        self, sender_email: str, configs: list[dict[str, Any]]
    ) -> float | None:
        """Find the most specific matching price for a user.

        Mirrors MppPerRequestPolicy's tier-matching: more specific patterns
        (longer, non-wildcard) win.
        """
        best_price: float | None = None
        best_specificity = -1

        for config in configs:
            validated = MppPerDocumentConfig(**config)
            for pattern in validated.applied_to:
                if not matches_any_pattern(sender_email, [pattern]):
                    continue
                specificity = 0 if pattern == "*" else len(pattern.replace("*", ""))
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_price = validated.price_per_document

        return best_price

    async def _get_mpp_instance(
        self, wallet_address: str, realm: str, secret_key: str
    ) -> Mpp:
        """Get or create a cached Mpp server instance.

        Cached per (wallet_address, realm) so HMAC challenge verification
        stays consistent across the 402 → pay → verify flow.
        """
        cache_key = f"{wallet_address}:{realm}"
        if cache_key not in MppPerDocumentPolicy._mpp_instances:
            chain_id = TESTNET_CHAIN_ID if app_settings.tempo_testnet else None
            method = tempo(
                currency=PATH_USD,
                recipient=wallet_address,
                chain_id=chain_id,
                intents={"charge": ChargeIntent(chain_id=chain_id)},
            )
            MppPerDocumentPolicy._mpp_instances[cache_key] = Mpp.create(
                method=method,
                secret_key=secret_key,
                realm=realm,
            )
        return MppPerDocumentPolicy._mpp_instances[cache_key]

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Gate on credential presence; defer real charging to post_hook."""
        sender_email = context.sender_email
        price_per_document = self._find_matching_price(sender_email, configs)
        if price_per_document is None:
            if configs:
                raise PolicyViolationError(
                    message="No pricing tier matches your account",
                    policy_type=self.NAME,
                )
            return context

        if price_per_document == 0:
            context.metadata["mpp_per_doc_price"] = 0.0
            return context

        wallet_config = context.metadata.get("wallets", {}).get("mpp", {})
        wallet_address = wallet_config.get("wallet_address")
        if not wallet_address:
            raise PolicyViolationError(
                message=(
                    "Payment is required but the endpoint owner has not "
                    "configured a wallet address"
                ),
                policy_type=self.NAME,
            )

        x_payment = context.metadata.get("x_payment")
        if not x_payment:
            secret_key = wallet_config.get("mpp_secret_key", "")
            mpp = await self._get_mpp_instance(
                wallet_address,
                realm=context.endpoint_slug,
                secret_key=secret_key,
            )
            # No credential → MPP returns a Challenge for the requested
            # amount. Sizing for one document is a hint; the real total is
            # computed post-search and re-charged via the supplied credential.
            result = await mpp.charge(
                authorization=None,
                amount=str(price_per_document),
                description=(f"Query endpoint: {context.endpoint_slug} (per-document)"),
            )
            if isinstance(result, Challenge):
                www_authenticate = result.to_www_authenticate(
                    realm=context.endpoint_slug
                )
                raise PaymentRequiredError(
                    www_authenticate=www_authenticate,
                    description=(
                        f"Payment of at least ${price_per_document} per "
                        "document required to query this endpoint"
                    ),
                )

        context.metadata["mpp_per_doc_price"] = price_per_document
        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Charge count * price_per_document; 402 on credential shortfall.

        Cost is only written when a charge actually happened. Free-tier and
        zero-document requests leave cost/currency as None — absence is
        meaningful for downstream consumers.
        """
        price_per_document = context.metadata.get("mpp_per_doc_price")
        if price_per_document is None or price_per_document == 0:
            return context

        response = context.response or {}
        references = response.get("references") or {}
        documents = references.get("documents") or []
        count = len(documents)
        if count == 0:
            return context

        total = count * price_per_document
        wallet_config = context.metadata.get("wallets", {}).get("mpp", {})
        wallet_address = wallet_config.get("wallet_address")
        secret_key = wallet_config.get("mpp_secret_key", "")
        x_payment = context.metadata.get("x_payment")

        mpp = await self._get_mpp_instance(
            wallet_address, realm=context.endpoint_slug, secret_key=secret_key
        )
        result = await mpp.charge(
            authorization=x_payment,
            amount=str(total),
            description=(
                f"Query endpoint: {context.endpoint_slug} ({count} documents)"
            ),
        )

        if isinstance(result, Challenge):
            www_authenticate = result.to_www_authenticate(realm=context.endpoint_slug)
            raise PaymentRequiredError(
                www_authenticate=www_authenticate,
                description=(f"Payment of ${total} required for {count} documents"),
            )

        credential, receipt = result
        context.metadata["mpp_credential"] = {"source": credential.source}
        context.metadata["mpp_receipt"] = {
            "reference": receipt.reference,
            "status": receipt.status,
            "external_id": receipt.external_id,
        }
        context.metadata["payment_receipt_header"] = receipt.reference

        if context.response.get("references"):
            context.response["references"]["cost"] = total
            context.response["references"]["currency"] = "USD"

        logger.info(
            f"MPP per-document payment verified: ${total} from "
            f"{credential.source} for endpoint {context.endpoint_slug} "
            f"({count} documents)"
        )
        return context
