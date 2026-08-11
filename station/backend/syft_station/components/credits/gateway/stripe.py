"""Stripe payment gateway — Checkout Sessions API.

Checkout is Stripe-hosted: the station creates a Checkout Session and
redirects the buyer to its ``url``. No success/cancel URLs are set —
Stripe then shows its own confirmation screen, the same hosted-end-screen
model as Xendit; settlement is webhook-authoritative either way.

Webhook signature scheme (different from Xendit's static token):
``Stripe-Signature: t=<ts>,v1=<hex>,…`` where v1 = HMAC-SHA256 over
``f"{ts}.{raw_body}"`` keyed by the endpoint's signing secret (whsec_…).
The timestamp is inside the signed payload, so the 5-minute staleness
window doubles as replay protection. Only ``v1`` is accepted — ``v0``
exists for test events and ignoring it defends against downgrades.

State machine (see entities.InvoiceStatus for why PROCESSING exists):
- ``checkout.session.completed`` + ``payment_status=paid``   → PAID
- ``checkout.session.completed`` + ``payment_status=unpaid`` → PROCESSING
  (delayed method, e.g. SEPA/ACH — settlement still in flight)
- ``checkout.session.async_payment_succeeded``               → PAID
- ``checkout.session.async_payment_failed``                  → CANCELLED
- ``checkout.session.expired``                               → EXPIRED
"""

import hashlib
import hmac
import time
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException, status
from loguru import logger
from pydantic import BaseModel, ConfigDict

from syft_station.components.credits.bundles import PREPAID_BUNDLES
from syft_station.components.credits.entities import InvoiceStatus
from syft_station.components.credits.gateway.interfaces import (
    CreatePaymentResult,
    WebhookEnvelope,
    WebhookResult,
)

# Stripe's own default webhook tolerance; the timestamp is signed, so an
# attacker can't move it without breaking the HMAC.
_WEBHOOK_TOLERANCE_SECONDS = 300

# Currencies Stripe charges in whole units (no cents). A currency missing
# from this list gets multiplied by 100 at the API boundary — adding a
# zero-decimal currency to the catalog WITHOUT listing it here would
# charge 100× the intended amount. Reference:
# https://docs.stripe.com/currencies#zero-decimal
_STRIPE_ZERO_DECIMAL = frozenset({"JPY"})


def to_stripe_minor_units(amount: float, currency: str) -> int:
    """Convert a major-unit float to Stripe's integer minor-unit format.

    The catalog stores major units (dollars); Stripe wants minor units
    (cents), except for zero-decimal currencies. Strictly one-way: webhook
    accounting uses our own invoice amount via client_reference lookup, so
    nothing ever converts back.
    """
    if currency.upper() in _STRIPE_ZERO_DECIMAL:
        return int(round(amount))
    return int(round(amount * 100))


class StripeError(Exception):
    """Stripe API call failed."""

    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class StripeCheckoutSession(BaseModel):
    """The fields of a Checkout Session response the station uses."""

    id: str  # cs_…
    url: str | None = None  # hosted checkout URL (None in custom-UI modes)
    client_reference_id: str | None = None

    model_config = ConfigDict(extra="allow")


class StripeClient:
    """Async client for the Stripe Checkout Sessions API.

    Basic auth: secret_key as username, empty password. Request bodies are
    form-encoded (Stripe takes no JSON). Instantiated per call from the
    wallet's stored credentials.
    """

    def __init__(self, secret_key: str, base_url: str):
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")

    def _build_http_client(self) -> httpx.AsyncClient:
        """Seam for tests to swap in a MockTransport."""
        return httpx.AsyncClient(
            base_url=self.base_url, auth=(self.secret_key, ""), timeout=30.0
        )

    async def create_checkout_session(
        self,
        *,
        reference_id: str,
        amount_minor: int,
        currency: str,
        payer_email: str,
        description: str,
    ) -> StripeCheckoutSession:
        """Create a hosted Checkout Session; returns its checkout link.

        ``reference_id`` rides as ``client_reference_id`` (round-tripped on
        every webhook event) and doubles as the Idempotency-Key — a retried
        create returns the original session instead of a second charge.
        """
        payload = {
            "mode": "payment",
            "client_reference_id": reference_id,
            "customer_email": payer_email,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": str(amount_minor),
            "line_items[0][price_data][product_data][name]": description,
        }
        async with self._build_http_client() as client:
            try:
                response = await client.post(
                    "/v1/checkout/sessions",
                    data=payload,
                    headers={"Idempotency-Key": reference_id},
                )
            except httpx.HTTPError as e:
                raise StripeError(f"Stripe unreachable: {e}") from e

        if response.status_code not in (200, 201):
            try:
                message = response.json().get("error", {}).get("message", response.text)
            except Exception:
                message = response.text
            raise StripeError(
                f"Stripe rejected the session ({response.status_code}): {message}",
                status_code=502,
            )
        return StripeCheckoutSession(**response.json())


class StripeGateway:
    """PaymentGateway implementation for Stripe."""

    PROVIDER_NAME = "stripe"

    def __init__(self, api_url: str = "https://api.stripe.com"):
        self.api_url = api_url

    def validate_credentials(self, credentials: dict, currency: str) -> dict:
        # Supported currencies ARE the catalog keys — a wallet currency
        # without a bundle catalog would have nothing to sell.
        supported = PREPAID_BUNDLES[self.PROVIDER_NAME]
        if currency not in supported:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Stripe support here does not include currency "
                f"'{currency}'. Supported: {sorted(supported)}",
            )
        secret_key = (credentials.get("secret_key") or "").strip()
        webhook_secret = (credentials.get("webhook_secret") or "").strip()
        if not secret_key or not webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Stripe needs both secret_key and webhook_secret",
            )
        return {"secret_key": secret_key, "webhook_secret": webhook_secret}

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
        client = self._build_client(credentials["secret_key"])
        try:
            session = await client.create_checkout_session(
                reference_id=reference_id,
                amount_minor=to_stripe_minor_units(amount, currency),
                currency=currency,
                payer_email=payer_email,
                description=description,
            )
        except StripeError as e:
            logger.error(f"Stripe session creation failed: {e.message}")
            raise HTTPException(status_code=e.status_code, detail=e.message) from e
        if not session.url:
            # Stripe omits url only in custom-UI modes; we always request
            # hosted checkout, so a missing url means something is wrong.
            logger.error(f"Stripe returned session {session.id} with no checkout URL")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe did not return a checkout URL",
            )
        return CreatePaymentResult(
            checkout_url=session.url,
            provider_session_id=session.id,
        )

    def _build_client(self, secret_key: str) -> StripeClient:
        """Seam for tests to swap in a stubbed client."""
        return StripeClient(secret_key, self.api_url)

    def verify_webhook(self, envelope: WebhookEnvelope, credentials: dict) -> None:
        """HMAC-verify the Stripe-Signature header against the raw body."""
        sig_header = envelope.headers.get("stripe-signature")
        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing Stripe-Signature header",
            )

        parts: dict[str, str] = {}
        for piece in sig_header.split(","):
            if "=" in piece:
                key, value = piece.split("=", 1)
                parts[key.strip()] = value.strip()
        timestamp, v1 = parts.get("t"), parts.get("v1")
        if not timestamp or not v1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Malformed Stripe-Signature header",
            )
        try:
            ts = int(timestamp)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bad Stripe-Signature timestamp",
            ) from e
        if abs(int(time.time()) - ts) > _WEBHOOK_TOLERANCE_SECONDS:
            logger.warning("Stripe webhook stale timestamp; possible replay")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Stale Stripe webhook timestamp",
            )

        signed = f"{ts}.{envelope.raw_body.decode('utf-8')}".encode()
        expected = hmac.new(
            credentials.get("webhook_secret", "").encode(), signed, hashlib.sha256
        ).hexdigest()
        # Constant-time comparison — no timing oracle on the signature.
        if not hmac.compare_digest(expected, v1):
            logger.warning("Stripe webhook signature mismatch")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Stripe webhook signature",
            )

    def normalize_webhook(self, envelope: WebhookEnvelope) -> WebhookResult | None:
        """Map ``{type, data: {object: {…}}}`` to the invoice domain."""
        payload = envelope.parsed
        event = payload.get("type", "")
        data_object = (payload.get("data") or {}).get("object") or {}

        client_ref = data_object.get("client_reference_id")
        if not client_ref:
            logger.info(
                f"Stripe webhook missing client_reference_id; ignoring: {event}"
            )
            return None

        if event == "checkout.session.completed":
            if data_object.get("payment_status") == "paid":
                invoice_status = InvoiceStatus.PAID
            else:
                # Delayed method: the buyer finished checkout but the bank
                # settlement is in flight — hold the credit until
                # async_payment_succeeded fires.
                invoice_status = InvoiceStatus.PROCESSING
        elif event == "checkout.session.async_payment_succeeded":
            invoice_status = InvoiceStatus.PAID
        elif event == "checkout.session.async_payment_failed":
            # Financial outcome matches a cancellation: no credit.
            invoice_status = InvoiceStatus.CANCELLED
        elif event == "checkout.session.expired":
            invoice_status = InvoiceStatus.EXPIRED
        else:
            logger.info(f"Stripe webhook event '{event}' not handled; ignoring")
            return None

        paid_at = None
        if invoice_status == InvoiceStatus.PAID:
            paid_at = self._extract_event_time(data_object, payload, client_ref)

        return WebhookResult(
            client_reference=client_ref,
            status=invoice_status.value,
            paid_at=paid_at,
            raw_payload=payload,
        )

    @staticmethod
    def _extract_event_time(
        data_object: dict, event: dict, client_ref: str
    ) -> datetime:
        """A PAID timestamp: the session's ``created``, else the event's,
        else now(). Unix epoch seconds; the wall-clock fallback is logged so
        a silently-wrong audit timestamp stays observable."""
        for source in (data_object, event):
            ts = source.get("created")
            if isinstance(ts, int):
                return datetime.fromtimestamp(ts, tz=UTC)
        logger.warning(
            f"Stripe PAID webhook without a 'created' timestamp; "
            f"using now() for {client_ref}"
        )
        return datetime.now(UTC)
