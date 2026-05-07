"""Xendit payment gateway implementation."""

from datetime import datetime, timezone

from fastapi import HTTPException
from loguru import logger

from syft_space.components.payments.gateway.entities import InvoiceStatus
from syft_space.components.payments.gateway.interfaces import (
    CreatePaymentResult,
    ResolvedBundle,
    WebhookResult,
)
from syft_space.components.payments.gateway.xendit.client import (
    XenditClient,
    XenditError,
)
from syft_space.components.wallets.entities import Wallet
from syft_space.components.wallets.gateway.xendit.config import XenditWalletConfig
from syft_space.config import app_settings


class XenditGateway:
    """Xendit Payment Sessions gateway.

    Translates between our domain model and Xendit's API/webhook format.

    Xendit webhook payload structure:
    {
        "event": "payment_session.completed",
        "business_id": "...",
        "created": "...",
        "data": {
            "id": "ps-...",
            "reference_id": "our-reference",
            "status": "COMPLETED",
            "amount": 100000,
            "created": "...",
            "updated": "...",
            ...
        }
    }
    """

    PROVIDER_NAME = "xendit"
    POLICY_TYPE = "xendit"

    # Map Xendit event types to our domain status
    _EVENT_STATUS_MAP = {
        "payment_session.completed": InvoiceStatus.PAID,
        "payment_session.expired": InvoiceStatus.EXPIRED,
        "payment_session.canceled": InvoiceStatus.CANCELLED,
    }

    def resolve_purchase(
        self,
        wallet: Wallet,
        bundle_name: str,
    ) -> ResolvedBundle:
        """Validate bundle exists in the currency's catalog and resolve amount + currency.

        Wallet-scoped: currency lives on the wallet, not the policy; bundles
        are derived from the wallet's currency. Per-policy applies_to is
        checked separately at the route layer (it depends on which endpoint
        the user clicked through from).
        """
        wallet_config = XenditWalletConfig(**wallet.configuration)
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
        """Create a Xendit Payment Session."""
        api_key = wallet.configuration.get("api_key")
        if not api_key:
            raise HTTPException(status_code=500, detail="Xendit wallet missing API key")

        country = wallet.country or "ID"

        try:
            xendit_base_url = str(app_settings.xendit_api_url)
            async with XenditClient(api_key, xendit_base_url) as client:
                session = await client.create_session(
                    reference_id=reference_id,
                    amount=amount,
                    currency=currency,
                    country=country,
                    payer_email=payer_email,
                    description=description,
                    metadata=metadata or {},
                )
        except XenditError as e:
            logger.error(f"Xendit session creation failed: {e.message}")
            raise e.to_http_exception() from e

        return CreatePaymentResult(
            external_id=session.reference_id,
            checkout_url=session.payment_link_url,
        )

    def verify_webhook(
        self,
        callback_token: str,
        wallet: Wallet,
    ) -> None:
        """Verify Xendit webhook via x-callback-token header."""
        expected_token = wallet.configuration.get("callback_token")
        if callback_token != expected_token:
            logger.warning("Webhook: invalid callback token")
            raise HTTPException(status_code=403, detail="Invalid callback token")

    def normalize_webhook(
        self,
        raw_payload: dict,
    ) -> WebhookResult | None:
        """Parse Xendit webhook into domain types.

        Xendit sends a nested payload:
          { "event": "payment_session.completed", "data": { "reference_id": ..., "status": ..., ... } }

        We map the event type to our InvoiceStatus and extract fields from data.

        Returns None for unparseable / unhandled events so the caller can
        200-ack — Xendit retries on any non-2xx, and we don't want event types
        we don't care about (e.g. payment.capture) to drive a retry storm.
        """
        event = raw_payload.get("event", "")
        data = raw_payload.get("data", {})

        reference_id = data.get("reference_id", "")
        if not reference_id:
            logger.info(
                f"Xendit webhook missing data.reference_id; ignoring: {raw_payload}"
            )
            return None

        # Map event type to our domain status
        status = self._EVENT_STATUS_MAP.get(event)
        if not status:
            logger.info(
                f"Xendit webhook event '{event}' not handled; ignoring: {raw_payload}"
            )
            return None

        # Extract timestamp for paid events. Falling back to wall-clock time
        # is the safest default if Xendit ever changes its format, but we
        # want a log so the silent-wrong audit timestamp is observable.
        paid_at = None
        if status == InvoiceStatus.PAID:
            timestamp = data.get("updated") or data.get("created")
            if timestamp:
                try:
                    paid_at = datetime.fromisoformat(timestamp)
                except ValueError:
                    logger.warning(
                        f"Xendit paid_at parse failed (got {timestamp!r}); "
                        f"falling back to now() for reference_id={reference_id}"
                    )
                    paid_at = datetime.now(timezone.utc)
            else:
                logger.warning(
                    f"Xendit PAID webhook missing data.updated/created; "
                    f"falling back to now() for reference_id={reference_id}"
                )
                paid_at = datetime.now(timezone.utc)

        return WebhookResult(
            external_id=reference_id,
            status=status,
            paid_at=paid_at,
            raw_payload=raw_payload,
        )
