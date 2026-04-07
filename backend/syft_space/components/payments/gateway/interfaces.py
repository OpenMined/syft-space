"""Payment gateway protocol and domain types.

Defines the adapter boundary between the PaymentHandler (use case layer)
and provider-specific implementations (adapter layer).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from syft_space.components.payments.gateway.entities import InvoiceStatus
from syft_space.components.wallets.entities import Wallet


@dataclass
class CreatePaymentResult:
    """Normalized result from a provider's create-payment API."""

    external_id: str  # our reference echoed back (webhook join key)
    checkout_url: str  # hosted payment page URL


@dataclass
class WebhookResult:
    """Normalized result from parsing a provider's webhook payload."""

    external_id: str  # maps to Invoice.external_id for lookup
    status: InvoiceStatus  # provider status mapped to our domain enum
    paid_at: datetime | None
    raw_payload: dict  # original payload, stored for audit


@dataclass
class ResolvedTier:
    """Result of resolving a tier from policy config.

    Returned by gateway.resolve_purchase() — the gateway parses its
    own policy config schema and validates tier + user eligibility.
    """

    name: str
    units: int
    unit_type: str
    price: float
    currency: str


class PaymentGateway(Protocol):
    """Adapter interface for payment providers.

    Each provider implements this protocol to translate between
    our domain model and the provider's API/webhook format.
    """

    PROVIDER_NAME: str  # "xendit", "stripe" — matches Wallet.wallet_type
    POLICY_TYPE: str  # "xendit", "stripe" — matches Policy.policy_type

    def resolve_purchase(
        self,
        config: dict,
        tier_name: str,
        user_email: str,
    ) -> ResolvedTier:
        """Validate tier exists and user is eligible.

        The gateway owns the policy config schema interpretation.
        Raises HTTPException if tier not found or user not eligible.

        Args:
            config: Raw policy configuration dict
            tier_name: Requested tier name
            user_email: Buyer's email for applied_to check
        """
        ...

    async def create_payment(
        self,
        *,
        reference_id: str,
        amount: float,
        currency: str,
        payer_email: str,
        description: str,
        wallet: Wallet,
        policy_config: dict,
        metadata: dict[str, str] | None = None,
    ) -> CreatePaymentResult:
        """Call provider API to create a payment session/invoice."""
        ...

    def verify_webhook(
        self,
        callback_token: str,
        wallet: Wallet,
    ) -> None:
        """Verify webhook authenticity. Raises HTTPException on failure."""
        ...

    def normalize_webhook(
        self,
        raw_payload: dict,
    ) -> WebhookResult:
        """Parse provider-specific webhook payload into domain types."""
        ...
