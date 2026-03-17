"""Webhook routes for payment providers (public, no admin auth)."""

from fastapi import APIRouter, Header, Request

from syft_space.components.auth.public import public_route
from syft_space.components.payments.handlers import PaymentHandler


def build_webhook_routes(handler: PaymentHandler) -> APIRouter:
    """Build webhook routes for all payment providers.

    Each provider gets its own endpoint because auth headers differ
    (Xendit uses x-callback-token, Stripe uses Stripe-Signature, etc.).
    """
    router = APIRouter(prefix="/webhooks", tags=["webhooks"])

    def get_handler() -> PaymentHandler:
        return handler

    @public_route
    @router.post("/xendit")
    async def xendit_webhook(
        request: Request,
        x_callback_token: str = Header(..., alias="x-callback-token"),
    ) -> dict:
        """Xendit payment webhook (PUBLIC, no admin auth).

        Xendit sends payment status updates to this endpoint.
        Verified via x-callback-token header.
        """
        body = await request.json()
        return await handler.handle_webhook("xendit", body, x_callback_token)

    return router
