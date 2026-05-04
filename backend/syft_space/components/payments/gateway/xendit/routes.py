"""Xendit-specific webhook route.

Invoice creation is wallet-scoped and lives on the gateway router; only the
provider-specific webhook stays here.
"""

from fastapi import APIRouter, Header, Request

from syft_space.components.payments.gateway.dependencies import (
    get_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler


def build_xendit_routes(
    handler: PaymentHandler,
    get_verified_sender_email: get_verified_sender_email_dependency,
) -> APIRouter:
    """Build the Xendit-specific webhook route under /xendit."""
    router = APIRouter(prefix="/xendit", tags=["payments", "xendit"])

    @router.post("/webhooks")
    async def xendit_webhook(
        request: Request,
        x_callback_token: str = Header(..., alias="x-callback-token"),
    ) -> dict:
        """Xendit payment webhook (PUBLIC, no admin auth).

        Verified via x-callback-token header. The handler looks up the
        invoice's wallet to resolve the expected token.
        """
        body = await request.json()
        return await handler.handle_webhook("xendit", body, x_callback_token)

    return router
