"""Xendit payment gateway implementation."""

from datetime import datetime, timezone

from fastapi import HTTPException
from loguru import logger

from syft_space.components.payments.entities import InvoiceStatus
from syft_space.components.payments.gateway import (
    CreatePaymentResult,
    WebhookResult,
)
from syft_space.components.payments.xendit_client import XenditClient, XenditError
from syft_space.components.wallets.entities import Wallet
from syft_space.config import app_settings


class XenditGateway:
    """Xendit Payment Sessions gateway.

    Translates between our domain model and Xendit's API/webhook format.
    """

    PROVIDER_NAME = "xendit"
    POLICY_TYPE = "xendit"

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
    ) -> CreatePaymentResult:
        """Create a Xendit Payment Session."""
        api_key = wallet.credentials.get("api_key")
        if not api_key:
            raise HTTPException(status_code=500, detail="Xendit wallet missing API key")

        country = policy_config.get("country", "ID")

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
        expected_token = wallet.credentials.get("callback_token")
        if callback_token != expected_token:
            logger.warning("Webhook: invalid callback token")
            raise HTTPException(status_code=403, detail="Invalid callback token")

    def normalize_webhook(
        self,
        raw_payload: dict,
    ) -> WebhookResult:
        """Map Xendit payment status to our domain model.

        Xendit Payment Sessions webhook statuses:
        - SUCCEEDED → InvoiceStatus.PAID
        - FAILED → InvoiceStatus.FAILED
        - EXPIRED, CANCELED → InvoiceStatus.EXPIRED
        """
        xendit_status = raw_payload.get("status", "").upper()
        reference_id = raw_payload.get("reference_id", "")

        # Map status
        status_map = {
            "SUCCEEDED": InvoiceStatus.PAID,
            "FAILED": InvoiceStatus.FAILED,
            "EXPIRED": InvoiceStatus.EXPIRED,
            "CANCELED": InvoiceStatus.EXPIRED,
        }
        status = status_map.get(xendit_status)
        if not status:
            raise HTTPException(
                status_code=400,
                detail=f"Unhandled Xendit status: {xendit_status}",
            )

        # Extract timestamp
        paid_at = None
        if status == InvoiceStatus.PAID:
            created = raw_payload.get("created")
            if created:
                try:
                    paid_at = datetime.fromisoformat(created)
                except ValueError:
                    paid_at = datetime.now(timezone.utc)
            else:
                paid_at = datetime.now(timezone.utc)

        return WebhookResult(
            external_id=reference_id,
            status=status,
            paid_at=paid_at,
            raw_payload=raw_payload,
        )
