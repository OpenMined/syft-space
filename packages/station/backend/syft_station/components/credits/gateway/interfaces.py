"""Payment gateway seam — one protocol per payment provider.

A gateway owns everything provider-specific: credential validation,
hosted-checkout session creation, and webhook verification + normalization.
Handlers stay provider-agnostic and dispatch by the wallet's ``provider``
string; adding a provider means implementing this protocol and registering
it in main.py — no handler changes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class CreatePaymentResult:
    """Provider session for one invoice."""

    checkout_url: str
    provider_session_id: str | None = None


@dataclass(frozen=True)
class WebhookEnvelope:
    """A provider webhook request, unopinionated.

    Headers are lowercased for case-insensitive lookup. ``raw_body`` is kept
    for providers that sign the exact bytes (e.g. HMAC schemes).
    """

    raw_body: bytes
    parsed: dict
    headers: dict[str, str]


@dataclass(frozen=True)
class WebhookResult:
    """A provider event normalized to the invoice domain."""

    client_reference: str
    status: str  # an InvoiceStatus value
    paid_at: datetime | None = None
    raw_payload: dict = field(default_factory=dict)


class PaymentGateway(Protocol):
    """Provider-specific behavior behind a common seam."""

    PROVIDER_NAME: str

    def validate_credentials(self, credentials: dict, currency: str) -> dict:
        """Check credential shape + currency support; return the dict to
        store on the wallet. Raises HTTPException on invalid input."""
        ...

    async def create_payment(
        self,
        *,
        reference_id: str,
        amount: float,
        currency: str,
        payer_email: str,
        description: str,
        credentials: dict,
    ) -> CreatePaymentResult:
        """Create a hosted-checkout session for one invoice."""
        ...

    def verify_webhook(self, envelope: WebhookEnvelope, credentials: dict) -> None:
        """Authenticate a webhook request. Raises HTTPException if invalid."""
        ...

    def normalize_webhook(self, envelope: WebhookEnvelope) -> WebhookResult | None:
        """Map a provider event to the invoice domain.

        Returns None for events that should be acknowledged but ignored —
        providers retry on non-2xx, and unknown event types must not cause
        a retry storm.
        """
        ...
