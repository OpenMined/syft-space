"""Stripe-specific webhook route.

Unlike Xendit's single ``/xendit/webhooks`` endpoint, Stripe webhooks are
wallet-scoped via the URL path: ``/stripe/webhooks/{wallet_id}``. Stripe
signs the request body with the wallet's ``whsec_…``, so we must know
which wallet's secret to use BEFORE we can trust the body — the body
itself can't tell us. Stamping the wallet id in the URL solves this
without trusting an unverified field.

The wallet_id is not a secret. Brute-force enumeration is intractable
(UUIDv4 → 122 bits) and a wrong id receives a generic 403, so this is
not a side-channel for wallet existence.
"""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import UUID4

from syft_space.components.auth.public import public_route
from syft_space.components.payments.gateway.dependencies import (
    get_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler
from syft_space.components.payments.gateway.interfaces import WebhookEnvelope


def build_stripe_routes(
    handler: PaymentHandler,
    get_verified_sender_email: get_verified_sender_email_dependency,
) -> APIRouter:
    """Build the Stripe-specific webhook routes under /stripe."""
    router = APIRouter(prefix="/stripe", tags=["payments", "stripe"])

    @public_route
    @router.post("/webhooks/{wallet_id}")
    async def stripe_webhook(wallet_id: UUID4, request: Request) -> dict:
        """Stripe checkout webhook (PUBLIC, HMAC-verified).

        The wallet_id scopes the signing-secret lookup. Signature
        verification happens before any further body parsing.
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
        return await handler.handle_webhook_for_wallet("stripe", wallet_id, envelope)

    return router
