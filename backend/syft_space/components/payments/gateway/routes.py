"""Gateway payment routes — wallet-scoped invoice/balance/transaction APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from syft_space.components.payments.gateway.dependencies import (
    get_verified_sender_email_dependency,
)
from syft_space.components.payments.gateway.handlers import PaymentHandler
from syft_space.components.payments.gateway.schemas import (
    CreateInvoiceRequest,
    InvoiceResponse,
    LedgerEntryPage,
    UserBalanceResponse,
)
from syft_space.components.payments.gateway.xendit.routes import build_xendit_routes
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_gateway_routes(
    handler: PaymentHandler,
    get_verified_sender_email: get_verified_sender_email_dependency,
) -> APIRouter:
    """Build gateway payment routes under /gateway.

    Wallet-scoped paths:
      POST   /gateway/wallets/{wallet_id}/invoices            (PUBLIC, satellite token)
      GET    /gateway/wallets/{wallet_id}/balance             (PUBLIC, satellite token)
      GET    /gateway/wallets/{wallet_id}/transactions/me     (PUBLIC, satellite token)
      GET    /gateway/wallets/{wallet_id}/transactions        (admin, tenant)
      GET    /gateway/wallets/{wallet_id}/invoices            (admin, tenant)
      GET    /gateway/invoices/{invoice_id}                   (admin, tenant)
    """
    router = APIRouter(prefix="/gateway", tags=["payments", "gateway"])

    def get_handler() -> PaymentHandler:
        return handler

    # ── Admin routes (tenant-authenticated) ────────────────────────

    @router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
    async def get_invoice(
        invoice_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Get invoice details by ID."""
        return await handler.get_invoice(invoice_id, tenant)

    @router.get("/wallets/{wallet_id}/invoices", response_model=list[InvoiceResponse])
    async def list_wallet_invoices(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> list[InvoiceResponse]:
        """All invoices for a wallet (admin view)."""
        return await handler.get_invoices_by_wallet(wallet_id, tenant)

    @router.get("/wallets/{wallet_id}/transactions", response_model=LedgerEntryPage)
    async def list_wallet_transactions(
        wallet_id: UUID,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: PaymentHandler = Depends(get_handler),
    ) -> LedgerEntryPage:
        """Cursor-paginated transaction ledger across all users for this wallet (admin)."""
        return await handler.list_wallet_transactions(
            wallet_id, tenant, cursor=cursor, limit=limit
        )

    # ── Public routes (satellite-token authenticated) ──────────────

    @router.post(
        "/wallets/{wallet_id}/invoices",
        response_model=InvoiceResponse,
        status_code=201,
    )
    async def create_invoice(
        wallet_id: UUID,
        request: CreateInvoiceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        user_email: str = Depends(get_verified_sender_email),
        handler: PaymentHandler = Depends(get_handler),
    ) -> InvoiceResponse:
        """Create an invoice against a wallet (PUBLIC, satellite token)."""
        # Provider is derived from the wallet at the handler — we just dispatch
        # to the matching gateway. Hardcoded to xendit while it's the only
        # prepaid provider; generalize when a second one lands.
        return await handler.create_invoice(
            "xendit", wallet_id, request, tenant, user_email
        )

    @router.get("/wallets/{wallet_id}/balance", response_model=UserBalanceResponse)
    async def get_balance(
        wallet_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        user_email: str = Depends(get_verified_sender_email),
        handler: PaymentHandler = Depends(get_handler),
    ) -> UserBalanceResponse:
        """Read the caller's wallet balance (PUBLIC, satellite token)."""
        return await handler.get_user_balance(wallet_id, user_email, tenant)

    @router.get(
        "/wallets/{wallet_id}/transactions/me",
        response_model=LedgerEntryPage,
    )
    async def list_my_transactions(
        wallet_id: UUID,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        tenant: Tenant = Depends(get_tenant_dependency),
        user_email: str = Depends(get_verified_sender_email),
        handler: PaymentHandler = Depends(get_handler),
    ) -> LedgerEntryPage:
        """Caller's own transaction history for this wallet (PUBLIC, satellite token)."""
        return await handler.list_user_transactions(
            wallet_id, user_email, tenant, cursor=cursor, limit=limit
        )

    # Provider-specific sub-router (currently just the webhook)
    router.include_router(build_xendit_routes(handler, get_verified_sender_email))

    return router
