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
class ResolvedBundle:
    """Result of resolving a bundle from policy config.

    Returned by gateway.resolve_purchase() — the gateway parses its
    own policy config schema and validates bundle + user eligibility.
    """

    name: str
    amount: float  # money amount in policy currency
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
        wallet: Wallet,
        bundle_name: str,
    ) -> ResolvedBundle:
        """Validate bundle exists on the wallet's catalog.

        Wallet-scoped: bundles and currency live on the wallet, not the policy.
        Raises HTTPException if bundle not found.
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
    ) -> WebhookResult | None:
        """Parse provider-specific webhook payload into domain types.

        Returns None when the payload is well-authenticated but uninteresting
        (unknown event type, missing fields). Caller should log + 200-ack so
        the provider does not retry.
        """
        ...
