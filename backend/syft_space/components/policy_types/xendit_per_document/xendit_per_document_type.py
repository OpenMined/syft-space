"""Xendit per-document policy type.

Charges price_per_document per retrieved document, settled in post_hook
once the search has returned. A cheap pre_hook floor check refuses the
request when the user's balance can't cover even a single document.
"""

from typing import Any

from pydantic import BaseModel, Field

from syft_space.components.payments.gateway.balance_service import (
    InsufficientBalanceError,
)
from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    Capabilities,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.shared.utils import (
    ConfigSchemaGenerator,
    matches_any_pattern,
)


class XenditPerDocumentConfig(BaseModel):
    """Configuration schema for xendit per-document pricing policy."""

    price_per_document: float = Field(
        ..., gt=0, description="Cost per retrieved document in the wallet's currency"
    )
    applied_to: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of user emails or glob patterns. Use '*' for all users.",
    )

    def applies_to_user(self, user_email: str) -> bool:
        """Check if this policy applies to the given user email."""
        return matches_any_pattern(user_email, self.applied_to)


class XenditPerDocumentPolicy(BasePolicyType):
    """Xendit per-document pricing policy.

    Pre-hook: cheap floor check (balance >= price_per_document) so a user
    with zero balance can't keep triggering search compute.

    Post-hook: count the documents in the response, settle for
    count * price_per_document via the same BalanceService.reserve path
    used by per-request. On insufficient balance the response is dropped
    (we don't ship documents we can't charge for).
    """

    NAME = "xendit_per_document"

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(
            requires_wallet=True,
            required_wallet_type="xendit",
            requires_endpoint_dataset=True,
        )

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Pay-per-document billed against a Xendit wallet's prepaid balance"

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return XenditPerDocumentConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = XenditPerDocumentConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid xendit_per_document config: {e}") from e

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Floor check: balance must cover at least one document."""
        if not configs:
            return context

        user_email = str(context.sender_email)
        validated = [XenditPerDocumentConfig(**c) for c in configs]

        balance_service = context.metadata.get("balance_service")
        wallet_id = context.metadata.get("xendit_wallet_id")
        currency = context.metadata.get("xendit_wallet_currency")
        endpoint_id = context.metadata.get("endpoint_id")
        tenant_id = context.metadata.get("tenant_id")
        if (
            not balance_service
            or not wallet_id
            or not currency
            or not endpoint_id
            or not tenant_id
        ):
            raise PolicyViolationError(
                message="Missing wallet/endpoint context for per-document policy",
                policy_type=self.NAME,
                details={"user": user_email},
            )

        for config in validated:
            if not config.applies_to_user(user_email):
                continue

            balance = await balance_service.get_balance(
                wallet_id=wallet_id, tenant_id=tenant_id, user_email=user_email
            )
            if balance < config.price_per_document:
                raise PolicyViolationError(
                    message="Insufficient balance to cover even one document.",
                    policy_type=self.NAME,
                    details={
                        "user": user_email,
                        "balance": balance,
                        "price_per_document": config.price_per_document,
                        "currency": currency,
                    },
                )

            # Stash for post-hook settlement.
            context.metadata["xendit_per_doc_price"] = config.price_per_document
            context.metadata["xendit_per_doc_wallet_id"] = wallet_id
            context.metadata["xendit_per_doc_tenant_id"] = tenant_id
            context.metadata["xendit_per_doc_endpoint_id"] = endpoint_id
            context.metadata["xendit_per_doc_currency"] = currency
            # First matching config wins.
            break

        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Settle for actual document count; drop response on shortfall."""
        price_per_document = context.metadata.get("xendit_per_doc_price")
        if price_per_document is None:
            return context

        response = context.response or {}
        references = response.get("references") or {}
        documents = references.get("documents") or []
        count = len(documents)
        if count == 0:
            return context

        balance_service = context.metadata.get("balance_service")
        if not balance_service:
            return context

        total = count * price_per_document
        user_email = str(context.sender_email)
        wallet_id = context.metadata["xendit_per_doc_wallet_id"]
        tenant_id = context.metadata["xendit_per_doc_tenant_id"]
        endpoint_id = context.metadata["xendit_per_doc_endpoint_id"]
        currency = context.metadata["xendit_per_doc_currency"]

        try:
            await balance_service.reserve(
                wallet_id=wallet_id,
                tenant_id=tenant_id,
                user_email=user_email,
                endpoint_id=endpoint_id,
                amount=total,
                currency=currency,
                charge_unit="document",
                charge_quantity=count,
            )
        except InsufficientBalanceError as exc:
            raise PolicyViolationError(
                message="Insufficient balance for the documents retrieved.",
                policy_type=self.NAME,
                details={
                    "user": user_email,
                    "documents": count,
                    "price_per_document": price_per_document,
                    "total": total,
                    "currency": currency,
                },
            ) from exc

        if response.get("references"):
            response["references"]["cost"] = total
        return context
