"""Payment gateway protocol and domain types.

Defines the adapter boundary between the PaymentHandler (use case layer)
and provider-specific implementations (adapter layer).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from syft_space.components.payments.gateway.entities import InvoiceStatus
from syft_space.components.wallets.entities import Wallet


@dataclass
class CreatePaymentResult:
    """Normalized result from a provider's create-payment API."""

    client_reference: str  # our token echoed back (webhook join key)
    checkout_url: str  # hosted payment page URL
    # Provider's native session id (e.g. Stripe cs_…). Persisted on the
    # invoice for stale-PENDING reconciliation — a future sweep job can
    # poll the provider when a webhook never arrives. Providers whose API
    # is addressable by client_reference (Xendit) leave this None.
    provider_session_id: str | None = None


@dataclass
class WebhookResult:
    """Normalized result from parsing a provider's webhook payload."""

    client_reference: str  # maps to Invoice.client_reference for lookup
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


@dataclass(frozen=True)
class WebhookEnvelope:
    """Everything a gateway might need to authenticate and parse a webhook.

    Carries the raw bytes (some providers — Stripe, GitHub, Slack — sign the
    body and any reformatting invalidates the signature), the already-decoded
    JSON for convenience, and a case-insensitive view of the request headers.

    Providers read whatever they need:
    - Xendit: headers["x-callback-token"] + parsed (static token, parsed body)
    - Stripe: headers["stripe-signature"] + raw_body (HMAC-SHA256 over t.body)
    """

    raw_body: bytes
    parsed: dict
    headers: Mapping[str, str]
    """Lower-cased keys. Route layer is responsible for normalizing."""


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
        envelope: WebhookEnvelope,
        wallet: Wallet,
    ) -> None:
        """Verify webhook authenticity. Raises HTTPException on failure.

        The envelope carries raw_body + headers, so providers that sign the
        body (Stripe HMAC) can re-hash and compare, while providers that use
        a static header token (Xendit) can read it directly.
        """
        ...

    def normalize_webhook(
        self,
        envelope: WebhookEnvelope,
    ) -> WebhookResult | None:
        """Parse provider-specific webhook payload into domain types.

        Returns None when the payload is well-authenticated but uninteresting
        (unknown event type, missing fields). Caller should log + 200-ack so
        the provider does not retry.
        """
        ...
