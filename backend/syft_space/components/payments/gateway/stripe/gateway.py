"""Stripe payment gateway implementation.

Translates between our domain model and Stripe's Checkout + webhook
formats. Implements ``PaymentGateway`` Protocol.

Webhook signature scheme (different from Xendit):
- Header: ``Stripe-Signature: t=<ts>,v1=<hex>,v0=…``
- Body is signed: HMAC-SHA256 over ``f"{ts}.{raw_body_utf8}"`` keyed by
  the wallet's ``webhook_secret`` (``whsec_…``).
- Replay protection: 5-minute timestamp tolerance (the timestamp is part
  of the signed payload, so an attacker can't move it without breaking
  the HMAC).
- We deliberately accept only ``v1``; ``v0`` exists for test events and
  ignoring it defends against downgrade attacks.

State machine:
- ``checkout.session.completed`` + ``payment_status=paid`` → ``PAID``
- ``checkout.session.completed`` + ``payment_status=unpaid`` → ``PROCESSING``
    (delayed payment method initiated; settlement pending)
- ``checkout.session.async_payment_succeeded`` → ``PAID``
- ``checkout.session.async_payment_failed`` → ``CANCELLED``
- ``checkout.session.expired`` → ``EXPIRED``
"""

import hashlib
import hmac
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from loguru import logger

from syft_space.components.payments.gateway.entities import InvoiceStatus
from syft_space.components.payments.gateway.interfaces import (
    CreatePaymentResult,
    ResolvedBundle,
    WebhookEnvelope,
    WebhookResult,
)
from syft_space.components.payments.gateway.stripe.amounts import to_stripe_minor_units
from syft_space.components.payments.gateway.stripe.client import (
    StripeClient,
    StripeError,
)
from syft_space.components.wallets.entities import Wallet
from syft_space.components.wallets.gateway.stripe.config import StripeWalletConfig
from syft_space.config import app_settings

# Stripe's default webhook timestamp tolerance is 5 minutes; the timestamp
# is part of the signed payload so we can rely on it for replay protection.
_WEBHOOK_TOLERANCE_SECONDS = 300


class StripeGateway:
    """Stripe Checkout Sessions gateway."""

    PROVIDER_NAME = "stripe"
    POLICY_TYPE = "stripe_per_request"

    def resolve_purchase(
        self,
        wallet: Wallet,
        bundle_name: str,
    ) -> ResolvedBundle:
        """Validate the bundle exists in the currency's catalog."""
        wallet_config = StripeWalletConfig(**wallet.configuration)
        bundle = wallet_config.get_bundle(bundle_name)
        if not bundle:
            available = [b.name for b in wallet_config.prepaid_balance_bundles]
            raise HTTPException(
                status_code=400,
                detail=f"Bundle '{bundle_name}' not found. Available: {available}",
            )
        return ResolvedBundle(
            name=bundle.name,
            amount=bundle.amount,
            currency=wallet_config.currency,
        )

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
        """Create a Stripe Checkout Session."""
        secret_key = wallet.configuration.get("secret_key")
        if not secret_key:
            raise HTTPException(
                status_code=500, detail="Stripe wallet missing secret key"
            )

        amount_minor = to_stripe_minor_units(amount, currency)

        base = str(app_settings.public_url).rstrip("/")
        success_url = f"{base}/syft-space-server/payment/success?ref={reference_id}"
        cancel_url = f"{base}/syft-space-server/payment/cancel?ref={reference_id}"

        try:
            stripe_base_url = str(app_settings.stripe_api_url)
            async with StripeClient(secret_key, stripe_base_url) as client:
                session = await client.create_checkout_session(
                    reference_id=reference_id,
                    amount_minor=amount_minor,
                    currency=currency,
                    payer_email=payer_email,
                    description=description,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata=metadata or {},
                )
        except StripeError as e:
            logger.error(f"Stripe session creation failed: {e.message}")
            raise e.to_http_exception() from e

        if not session.url:
            # Stripe omits url in custom-UI modes; we always request hosted
            # checkout, so missing url means something is wrong.
            logger.error(f"Stripe returned session {session.id} with no checkout URL")
            raise HTTPException(
                status_code=502, detail="Stripe did not return a checkout URL"
            )

        return CreatePaymentResult(
            external_id=reference_id,
            checkout_url=session.url,
            provider_session_id=session.id,
        )

    def verify_webhook(
        self,
        envelope: WebhookEnvelope,
        wallet: Wallet,
    ) -> None:
        """Verify Stripe webhook via HMAC-SHA256 of timestamp + raw body.

        Rejects:
        - Missing or malformed Stripe-Signature header.
        - Wallet missing webhook_secret (server misconfiguration).
        - Stale timestamp (>5min from now in either direction) — replay
          protection. The timestamp is signed, so it cannot be tampered.
        - HMAC mismatch — wrong secret or modified body.

        Constant-time comparison via ``hmac.compare_digest`` to avoid
        timing oracles on the signature byte-by-byte.
        """
        sig_header = envelope.headers.get("stripe-signature")
        if not sig_header:
            raise HTTPException(
                status_code=403, detail="Missing Stripe-Signature header"
            )

        webhook_secret = wallet.configuration.get("webhook_secret")
        if not webhook_secret:
            logger.error(f"Stripe wallet {wallet.id} missing webhook_secret")
            raise HTTPException(status_code=500, detail="Stripe wallet misconfigured")

        parts: dict[str, str] = {}
        for piece in sig_header.split(","):
            if "=" not in piece:
                continue
            k, v = piece.split("=", 1)
            parts[k.strip()] = v.strip()

        timestamp = parts.get("t")
        v1 = parts.get("v1")
        if not timestamp or not v1:
            raise HTTPException(
                status_code=403, detail="Malformed Stripe-Signature header"
            )

        try:
            ts = int(timestamp)
        except ValueError as e:
            raise HTTPException(
                status_code=403, detail="Bad Stripe-Signature timestamp"
            ) from e

        if abs(int(time.time()) - ts) > _WEBHOOK_TOLERANCE_SECONDS:
            logger.warning("Stripe webhook stale timestamp; possible replay")
            raise HTTPException(
                status_code=403, detail="Stale Stripe webhook timestamp"
            )

        signed = f"{ts}.{envelope.raw_body.decode('utf-8')}".encode()
        expected = hmac.new(
            webhook_secret.encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, v1):
            logger.warning("Stripe webhook signature mismatch")
            raise HTTPException(
                status_code=403, detail="Invalid Stripe webhook signature"
            )

    def normalize_webhook(
        self,
        envelope: WebhookEnvelope,
    ) -> WebhookResult | None:
        """Parse a Stripe webhook into a domain WebhookResult.

        Returns None for events we don't act on so the route 200-acks and
        Stripe stops retrying. We rely on ``client_reference_id`` (= our
        ``syft-{uuid}`` reference) for invoice lookup, set on session
        creation — Stripe round-trips it on every related event.
        """
        payload = envelope.parsed
        event = payload.get("type", "")
        data_object = (payload.get("data") or {}).get("object") or {}
        client_ref = data_object.get("client_reference_id")

        if not client_ref:
            logger.info(
                f"Stripe webhook missing client_reference_id; ignoring event={event}"
            )
            return None

        # Map event type to domain status, with the payment_status branch
        # for the synchronous-vs-delayed case on session.completed.
        if event == "checkout.session.completed":
            payment_status = data_object.get("payment_status")
            if payment_status == "paid":
                return WebhookResult(
                    external_id=client_ref,
                    status=InvoiceStatus.PAID,
                    paid_at=self._extract_event_time(data_object, payload),
                    raw_payload=payload,
                )
            # Delayed payment method (e.g. SEPA, ACH): customer completed
            # the flow but the bank settlement is in flight. Hold balance
            # until async_payment_succeeded fires.
            return WebhookResult(
                external_id=client_ref,
                status=InvoiceStatus.PROCESSING,
                paid_at=None,
                raw_payload=payload,
            )
        if event == "checkout.session.async_payment_succeeded":
            return WebhookResult(
                external_id=client_ref,
                status=InvoiceStatus.PAID,
                paid_at=self._extract_event_time(data_object, payload),
                raw_payload=payload,
            )
        if event == "checkout.session.async_payment_failed":
            # Reuse CANCELLED — the financial outcome (no credit) matches.
            # Distinguish from genuine cancellations via webhook_payload.type
            # if analytics ever need to.
            return WebhookResult(
                external_id=client_ref,
                status=InvoiceStatus.CANCELLED,
                paid_at=None,
                raw_payload=payload,
            )
        if event == "checkout.session.expired":
            return WebhookResult(
                external_id=client_ref,
                status=InvoiceStatus.EXPIRED,
                paid_at=None,
                raw_payload=payload,
            )

        logger.info(
            f"Stripe webhook event '{event}' not handled; "
            f"ignoring client_ref={client_ref}"
        )
        return None

    def _extract_event_time(self, data_object: dict, event: dict) -> datetime:
        """Extract a PAID timestamp from a Stripe payload.

        Prefers the Checkout Session's ``created`` field; falls back to the
        event-level ``created``; finally to ``now()``. Always Unix epoch
        seconds. Falling back to wall-clock keeps PAID auditable even if
        Stripe ever omits both — logged so silent fallbacks are detectable.
        """
        for source, key in ((data_object, "created"), (event, "created")):
            ts = source.get(key)
            if isinstance(ts, int):
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        logger.warning(
            "Stripe PAID webhook missing 'created' timestamp; falling back to now()"
        )
        return datetime.now(timezone.utc)
