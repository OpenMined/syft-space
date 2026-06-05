"""Stripe Checkout Sessions API client using httpx.

Mirrors XenditClient shape: async context manager, Basic auth with the
secret key as username and empty password, typed errors that convert to
HTTPException. Stripe's API takes form-encoded request bodies (not JSON),
so we pass dicts via httpx ``data=``.

Idempotency: every POST attaches an ``Idempotency-Key`` derived from our
reference_id (which is unique per invoice). A retried create returns the
original session if Stripe still has the key cached (≥24h retention).
"""

from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, ConfigDict


class StripeError(Exception):
    """Base exception for Stripe API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(status_code=self.status_code, detail=self.message)


class StripeAuthError(StripeError):
    """Invalid API key (401)."""


class StripeValidationError(StripeError):
    """Request validation failed (400/422)."""


class StripeCheckoutSession(BaseModel):
    """Stripe Checkout Session response model (relevant fields only)."""

    id: str  # cs_xxx
    url: str | None = None  # hosted checkout URL (None in custom UI modes)
    status: str  # open | complete | expired
    payment_status: str  # unpaid | paid | no_payment_required
    client_reference_id: str | None = None
    customer_email: str | None = None
    amount_total: int | None = None
    currency: str | None = None

    model_config = ConfigDict(extra="allow")


class StripeClient:
    """Async httpx client for Stripe Checkout Sessions.

    Uses Basic auth with secret_key as username, empty password — Stripe's
    standard server-side auth. NOT a singleton: instantiated per request
    from the wallet's stored credentials.

    Usage:
        async with StripeClient(secret_key, base_url) as client:
            session = await client.create_checkout_session(...)
    """

    def __init__(self, secret_key: str, base_url: str = "https://api.stripe.com"):
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "StripeClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.secret_key, ""),
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _handle_error(self, response: httpx.Response) -> None:
        """Raise typed error from a Stripe API error response."""
        try:
            body = response.json()
            err = body.get("error", {}) if isinstance(body, dict) else {}
            message = err.get("message") or response.text
            error_code = err.get("code")
        except Exception:
            message = response.text
            error_code = None

        if response.status_code == 401:
            raise StripeAuthError(
                message=f"Stripe authentication failed: {message}",
                status_code=401,
                error_code=error_code,
            )
        if response.status_code in (400, 422):
            raise StripeValidationError(
                message=f"Stripe validation error: {message}",
                status_code=response.status_code,
                error_code=error_code,
            )
        raise StripeError(
            message=f"Stripe API error ({response.status_code}): {message}",
            status_code=response.status_code,
            error_code=error_code,
        )

    async def create_checkout_session(
        self,
        *,
        reference_id: str,
        amount_minor: int,
        currency: str,
        payer_email: str,
        description: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str] | None = None,
    ) -> StripeCheckoutSession:
        """Create a one-shot Stripe Checkout Session.

        Args:
            reference_id: Our invoice's syft-{uuid}; surfaces in webhook
                as ``client_reference_id`` and also doubles as the
                Idempotency-Key for safe retries.
            amount_minor: Amount in Stripe's minor unit (cents / whole yen).
            currency: ISO 4217 code, lowercased in the request payload.
            payer_email: Pre-fills the Stripe checkout form.
            description: Shown on the line item as the product name.
            success_url / cancel_url: Where the customer lands after
                completing / abandoning the checkout. Settlement is
                authoritative via webhook; these are UX only.
            metadata: Additional key/value tags surfaced in the session +
                downstream PaymentIntent. Useful for tenant/wallet IDs.
        """
        assert self._client is not None, "Use 'async with StripeClient(...) as client:'"

        payload: dict[str, str] = {
            "mode": "payment",
            "client_reference_id": reference_id,
            "customer_email": payer_email,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": str(amount_minor),
            "line_items[0][price_data][product_data][name]": description,
        }
        for key, value in (metadata or {}).items():
            payload[f"metadata[{key}]"] = value

        headers = {"Idempotency-Key": reference_id}

        logger.debug(f"Creating Stripe checkout session: reference_id={reference_id}")
        response = await self._client.post(
            "/v1/checkout/sessions", data=payload, headers=headers
        )

        if response.status_code not in (200, 201):
            self._handle_error(response)

        return StripeCheckoutSession(**response.json())

    async def get_checkout_session(self, session_id: str) -> StripeCheckoutSession:
        """Retrieve a Checkout Session by id.

        Reserved for future stale-PENDING reconciliation — once a sweep
        worker is added, it'll GET the session to learn whether the user
        completed checkout while we missed the webhook.
        """
        assert self._client is not None, "Use 'async with StripeClient(...) as client:'"
        response = await self._client.get(f"/v1/checkout/sessions/{session_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return StripeCheckoutSession(**response.json())
