"""Xendit payment gateway — Payment Sessions API.

Checkout is Xendit-hosted: the station creates a payment session and
redirects the buyer to its ``payment_link_url``. Settlement arrives on the
webhook (``payment_session.completed``), authenticated by the static
``x-callback-token`` header configured in the Xendit dashboard.

Xendit has no cross-border support here: each currency is locked to its
home country (see CURRENCY_TO_COUNTRY) — a mismatched pairing leaves only
multi-country channels available and confuses payers.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException, status
from loguru import logger
from pydantic import BaseModel, ConfigDict

from syft_station.components.credits.entities import InvoiceStatus
from syft_station.components.credits.gateway.interfaces import (
    CreatePaymentResult,
    WebhookEnvelope,
    WebhookResult,
)

# Currency → home country. The single source of truth for what the wallet
# setup accepts.
CURRENCY_TO_COUNTRY: dict[str, str] = {
    "IDR": "ID",
    "PHP": "PH",
    "SGD": "SG",
    "MYR": "MY",
    "VND": "VN",
    "THB": "TH",
}


class XenditError(Exception):
    """Xendit API call failed."""

    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class XenditSessionResponse(BaseModel):
    """The fields of a Payment Session response the station uses."""

    payment_session_id: str
    reference_id: str
    payment_link_url: str

    model_config = ConfigDict(extra="allow")


class XenditClient:
    """Async client for the Xendit Payment Sessions API.

    Basic auth: api_key as username, empty password. Instantiated per call
    from the wallet's stored credentials.
    """

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _build_http_client(self) -> httpx.AsyncClient:
        """Seam for tests to swap in a MockTransport."""
        return httpx.AsyncClient(
            base_url=self.base_url, auth=(self.api_key, ""), timeout=30.0
        )

    async def create_session(
        self,
        *,
        reference_id: str,
        amount: float,
        currency: str,
        country: str,
        payer_email: str,
        description: str,
    ) -> XenditSessionResponse:
        """Create a hosted payment session; returns its checkout link."""
        payload: dict[str, Any] = {
            "reference_id": reference_id,
            "amount": amount,
            "currency": currency,
            "country": country,
            "session_type": "PAY",
            "mode": "PAYMENT_LINK",
            "capture_method": "AUTOMATIC",
            "description": description,
            "customer": {
                "reference_id": f"cust-{reference_id}",
                "type": "INDIVIDUAL",
                "email": payer_email,
                "individual_detail": {"given_names": payer_email.split("@")[0]},
            },
        }
        async with self._build_http_client() as client:
            try:
                response = await client.post("/sessions", json=payload)
            except httpx.HTTPError as e:
                raise XenditError(f"Xendit unreachable: {e}") from e

        if response.status_code not in (200, 201):
            try:
                message = response.json().get("message", response.text)
            except Exception:
                message = response.text
            raise XenditError(
                f"Xendit rejected the session ({response.status_code}): {message}",
                status_code=502,
            )
        return XenditSessionResponse(**response.json())


class XenditGateway:
    """PaymentGateway implementation for Xendit."""

    PROVIDER_NAME = "xendit"

    # Xendit event type → invoice status. Anything else is ack-and-ignore.
    _EVENT_STATUS_MAP = {
        "payment_session.completed": InvoiceStatus.PAID,
        "payment_session.expired": InvoiceStatus.EXPIRED,
        "payment_session.canceled": InvoiceStatus.CANCELLED,
    }

    def __init__(self, api_url: str = "https://api.xendit.co"):
        self.api_url = api_url

    def validate_credentials(self, credentials: dict, currency: str) -> dict:
        if currency not in CURRENCY_TO_COUNTRY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Xendit does not support currency '{currency}'. "
                f"Supported: {sorted(CURRENCY_TO_COUNTRY)}",
            )
        api_key = (credentials.get("api_key") or "").strip()
        callback_token = (credentials.get("callback_token") or "").strip()
        if not api_key or not callback_token:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Xendit needs both api_key and callback_token",
            )
        return {"api_key": api_key, "callback_token": callback_token}

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
        client = self._build_client(credentials["api_key"])
        try:
            session = await client.create_session(
                reference_id=reference_id,
                amount=amount,
                currency=currency,
                country=CURRENCY_TO_COUNTRY[currency],
                payer_email=payer_email,
                description=description,
            )
        except XenditError as e:
            logger.error(f"Xendit session creation failed: {e.message}")
            raise HTTPException(status_code=e.status_code, detail=e.message) from e
        return CreatePaymentResult(
            checkout_url=session.payment_link_url,
            provider_session_id=session.payment_session_id,
        )

    def _build_client(self, api_key: str) -> XenditClient:
        """Seam for tests to swap in a stubbed client."""
        return XenditClient(api_key, self.api_url)

    def verify_webhook(self, envelope: WebhookEnvelope, credentials: dict) -> None:
        """Compare the static x-callback-token header against the wallet's."""
        token = envelope.headers.get("x-callback-token")
        if not token or token != credentials.get("callback_token"):
            logger.warning("Xendit webhook: invalid callback token")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid callback token",
            )

    def normalize_webhook(self, envelope: WebhookEnvelope) -> WebhookResult | None:
        """Map ``{event, data: {reference_id, …}}`` to the invoice domain."""
        payload = envelope.parsed
        event = payload.get("event", "")
        data = payload.get("data", {})

        reference_id = data.get("reference_id", "")
        if not reference_id:
            logger.info(f"Xendit webhook missing data.reference_id; ignoring: {event}")
            return None

        invoice_status = self._EVENT_STATUS_MAP.get(event)
        if invoice_status is None:
            logger.info(f"Xendit webhook event '{event}' not handled; ignoring")
            return None

        # Timestamp for paid events; wall-clock fallback is logged so a
        # silently-wrong audit timestamp stays observable.
        paid_at = None
        if invoice_status == InvoiceStatus.PAID:
            timestamp = data.get("updated") or data.get("created")
            try:
                paid_at = datetime.fromisoformat(timestamp) if timestamp else None
            except ValueError:
                paid_at = None
            if paid_at is None:
                logger.warning(
                    f"Xendit PAID webhook without a parseable timestamp; "
                    f"using now() for {reference_id}"
                )
                paid_at = datetime.now(UTC)

        return WebhookResult(
            client_reference=reference_id,
            status=invoice_status.value,
            paid_at=paid_at,
            raw_payload=payload,
        )
