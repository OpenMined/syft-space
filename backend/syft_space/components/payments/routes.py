"""Payments routes — single entry point that composes all sub-routers.

Produces:
    # MPP
    /payments/mpp/{wallet_id}/balance
    /payments/mpp/{wallet_id}/transactions

    # Gateway (wallet-scoped invoices + balance + ledger)
    POST   /payments/gateway/wallets/{wallet_id}/invoices         (public)
    GET    /payments/gateway/wallets/{wallet_id}/balance          (public)
    GET    /payments/gateway/wallets/{wallet_id}/transactions/me  (public)
    GET    /payments/gateway/wallets/{wallet_id}/invoices         (admin)
    GET    /payments/gateway/wallets/{wallet_id}/transactions     (admin)
    GET    /payments/gateway/invoices/{invoice_id}                (admin)

    # Xendit-specific (webhook receiver only)
    POST   /payments/gateway/xendit/webhooks
"""

from fastapi import APIRouter

from syft_space.components.payments.gateway.dependencies import (
    get_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler
from syft_space.components.payments.gateway.routes import build_gateway_routes
from syft_space.components.payments.mpp.handlers import MppPaymentHandler
from syft_space.components.payments.mpp.routes import build_mpp_payment_routes


def build_payment_routes(
    *,
    mpp_handler: MppPaymentHandler,
    gateway_handler: PaymentHandler | None = None,
    get_verified_sender_email: get_verified_sender_email_dependency | None = None,
) -> APIRouter:
    """Build all payment routes under /payments."""
    router = APIRouter(prefix="/payments", tags=["payments"])

    # MPP financial routes
    router.include_router(build_mpp_payment_routes(mpp_handler))

    # Gateway routes (invoice/bundle reads + provider-specific)
    if gateway_handler and get_verified_sender_email:
        router.include_router(
            build_gateway_routes(gateway_handler, get_verified_sender_email)
        )

    return router
