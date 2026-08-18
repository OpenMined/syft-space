"""Xendit-specific webhook route.

Invoice creation is wallet-scoped and lives on the gateway router; only the
provider-specific webhook stays here.
"""

import json

from fastapi import APIRouter, HTTPException, Request

from syft_space.components.auth.public import public_route
from syft_space.components.payments.gateway.dependencies import (
    get_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler
from syft_space.components.payments.gateway.interfaces import WebhookEnvelope


def build_xendit_routes(
    handler: PaymentHandler,
    get_verified_sender_email: get_verified_sender_email_dependency,
) -> APIRouter:
    """Build the Xendit-specific webhook route under /xendit."""
    router = APIRouter(prefix="/xendit", tags=["payments", "xendit"])

    @public_route
    @router.post("/webhooks")
    async def xendit_webhook(request: Request) -> dict:
        """Xendit payment webhook (PUBLIC, no admin auth).

        Verified via x-callback-token header. The handler looks up the
        invoice's wallet to resolve the expected token.

        The route builds a WebhookEnvelope for the gateway to read whatever
        it needs (header for Xendit; raw body for signature-based providers).
        """
        raw = await request.body()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from e
        envelope = WebhookEnvelope(
            raw_body=raw,
            parsed=parsed,
            headers={k.lower(): v for k, v in request.headers.items()},
        )
        return await handler.handle_webhook("xendit", envelope)

    return router
