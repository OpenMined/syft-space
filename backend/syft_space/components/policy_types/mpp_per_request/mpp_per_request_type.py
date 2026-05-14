"""MPP per-request policy type for per-query payments via Machine Payments Protocol."""

from enum import StrEnum
from typing import Any, ClassVar

from loguru import logger
from mpp import Challenge
from mpp.methods.tempo import PATH_USD, TESTNET_CHAIN_ID, ChargeIntent, tempo
from mpp.server import Mpp
from pydantic import BaseModel, Field

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    PaymentRequiredError,
    PolicyContext,
    PolicyViolationError,
    WalletPolicy,
)
from syft_space.components.shared.utils import matches_any_pattern
from syft_space.config import app_settings


class UnitType(StrEnum):
    """Unit type for MPP accounting policy."""

    REQUESTS = "requests"


class MppPerRequestConfig(BaseModel):
    """Configuration for MPP accounting policy."""

    price: float = Field(ge=0, description="Price per query in USD")
    unit_type: UnitType = Field(
        default=UnitType.REQUESTS,
        description="Unit type for this policy",
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user email patterns. Use '*' for all users.",
    )


class MppPerRequestPolicy(BasePolicyType, WalletPolicy):
    """MPP-based payment policy using Tempo blockchain."""

    NAME: ClassVar[str] = "mpp_per_request"
    _mpp_instances: ClassVar[dict[str, Mpp]] = {}

    def required_wallet_type(self) -> str:
        return "mpp"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Charge per query using the Machine Payments Protocol (MPP) on Tempo blockchain"

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return MppPerRequestConfig.model_json_schema()

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize the configuration."""
        validated = MppPerRequestConfig(**config)
        return validated.model_dump()

    def __init__(self) -> None:
        pass

    def _find_matching_price(
        self, sender_email: str, configs: list[dict[str, Any]]
    ) -> float | None:
        """Find the most specific matching price for a user.

        More specific patterns (longer, non-wildcard) take priority.
        Returns None if no config matches.
        """
        best_price: float | None = None
        best_specificity = -1

        for config in configs:
            validated = MppPerRequestConfig(**config)
            for pattern in validated.applied_to:
                if not matches_any_pattern(sender_email, [pattern]):
                    continue
                specificity = 0 if pattern == "*" else len(pattern.replace("*", ""))
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_price = validated.price

        return best_price

    async def _get_mpp_instance(
        self, wallet_address: str, realm: str, secret_key: str
    ) -> Mpp:
        """Get or create a cached Mpp server instance for charging.

        Instances are cached per (wallet_address, realm) so the HMAC-based
        challenge verification uses a consistent realm across the
        402 challenge → pay → verify flow.
        """
        cache_key = f"{wallet_address}:{realm}"
        if cache_key not in MppPerRequestPolicy._mpp_instances:
            chain_id = TESTNET_CHAIN_ID if app_settings.tempo_testnet else None
            method = tempo(
                currency=PATH_USD,
                recipient=wallet_address,
                chain_id=chain_id,
                intents={"charge": ChargeIntent(chain_id=chain_id)},
            )
            MppPerRequestPolicy._mpp_instances[cache_key] = Mpp.create(
                method=method,
                secret_key=secret_key,
                realm=realm,
            )
        return MppPerRequestPolicy._mpp_instances[cache_key]

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Pre-hook: issue 402 challenge or verify payment credential.

        Flow:
        1. Match sender_email against pricing tiers to determine price
        2. If price is 0, allow through (free tier)
        3. Check for X-Payment credential in context.metadata
        4. If no credential: raise PaymentRequiredError with 402 challenge
        5. If credential present: verify payment via mpp.charge()
        6. Store receipt in context.metadata
        """
        sender_email = context.sender_email

        # Find matching price tier
        price = self._find_matching_price(sender_email, configs)
        if price is None:
            # No matching tier - if we have configs but none match, deny
            if configs:
                raise PolicyViolationError(
                    message="No pricing tier matches your account",
                    policy_type=self.NAME,
                )
            return context

        # Free tier - skip payment
        if price == 0:
            context.metadata["mpp_total_amount"] = 0.0
            return context

        # Get wallet configuration from context metadata
        wallet_config = context.metadata.get("wallets", {}).get("mpp", {})
        wallet_address = wallet_config.get("wallet_address")
        if not wallet_address:
            raise PolicyViolationError(
                message="Payment is required but the endpoint owner has not configured a wallet address",
                policy_type=self.NAME,
            )

        # Get X-Payment credential from metadata (injected by route handler)
        x_payment = context.metadata.get("x_payment")

        # Create MPP instance and attempt charge
        secret_key = wallet_config.get("mpp_secret_key", "")
        mpp = await self._get_mpp_instance(
            wallet_address, realm=context.endpoint_slug, secret_key=secret_key
        )

        result = await mpp.charge(
            authorization=x_payment,
            amount=str(price),
            description=f"Query endpoint: {context.endpoint_slug}",
        )

        if isinstance(result, Challenge):
            # Payment required - raise error for route handler to return 402
            www_authenticate = result.to_www_authenticate(realm=context.endpoint_slug)
            raise PaymentRequiredError(
                www_authenticate=www_authenticate,
                description=f"Payment of ${price} required to query this endpoint",
            )

        # Payment verified
        credential, receipt = result
        context.metadata["mpp_credential"] = {
            "source": credential.source,
        }
        context.metadata["mpp_receipt"] = {
            "reference": receipt.reference,
            "status": receipt.status,
            "external_id": receipt.external_id,
        }
        context.metadata["mpp_total_amount"] = price

        logger.info(
            f"MPP payment verified: ${price} from {credential.source} "
            f"for endpoint {context.endpoint_slug}"
        )

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Post-hook: add cost and receipt info to response metadata."""
        total_amount = context.metadata.get("mpp_total_amount", 0.0)
        receipt_info = context.metadata.get("mpp_receipt")

        if context.response:
            if context.response.get("summary"):
                context.response["summary"]["cost"] = total_amount
            if context.response.get("references"):
                context.response["references"]["cost"] = total_amount

        # Store receipt reference for Payment-Receipt header
        if receipt_info:
            context.metadata["payment_receipt_header"] = receipt_info.get("reference")

        return context
