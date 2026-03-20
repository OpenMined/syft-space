"""Payment gateway protocol and domain types.

Defines the adapter boundary between the PaymentHandler (use case layer)
and provider-specific implementations (adapter layer).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from syft_space.components.payments.entities import InvoiceStatus
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


class PaymentGateway(Protocol):
    """Adapter interface for payment providers.

    Each provider implements this protocol to translate between
    our domain model and the provider's API/webhook format.

    The handler calls these methods after completing shared business logic
    (validate endpoint, find tier, check applied_to, get wallet).
    """

    PROVIDER_NAME: str  # "xendit", "stripe" — matches Wallet.wallet_type
    POLICY_TYPE: str  # "xendit", "stripe" — matches Policy.policy_type

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
        """Call provider API to create a payment session/invoice.

        Args:
            reference_id: Our unique reference (idempotency + webhook join)
            amount: Payment amount
            currency: Currency code from policy config
            payer_email: Buyer's email
            description: Human-readable description
            wallet: Wallet entity with provider credentials
            policy_config: Raw policy configuration dict
                           (provider extracts what it needs, e.g. country)
            metadata: Key-value pairs passed to the provider for tracking
        """
        ...

    def verify_webhook(
        self,
        callback_token: str,
        wallet: Wallet,
    ) -> None:
        """Verify webhook authenticity. Raises HTTPException on failure.

        Each provider has its own verification mechanism:
        - Xendit: compare x-callback-token against wallet.credentials["callback_token"]
        - Stripe: verify Stripe-Signature against webhook secret
        """
        ...

    def normalize_webhook(
        self,
        raw_payload: dict,
    ) -> WebhookResult:
        """Parse provider-specific webhook payload into domain types.

        Maps provider statuses to InvoiceStatus:
        - Xendit: SUCCEEDED → PAID, FAILED → FAILED, EXPIRED/CANCELED → EXPIRED
        - Stripe: payment_intent.succeeded → PAID, etc.
        """
        ...
