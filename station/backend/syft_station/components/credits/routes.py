"""Credits API routes, grouped by caller:

- space-facing (Bearer ``sct_…`` space credits token): debit / refund / balance
- buyer (SyftHub satellite token): buy a bundle, own invoices, own balance
- admin + member views (station session cookie)
- provider webhooks (verified inside the gateway, no session)

The 402 body is written at the TOP level, not inside FastAPI's usual
``{"detail": …}`` wrapper: space clients read ``response.json()["balance"]``
directly. See schemas.py for the compatibility rules.
"""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from syft_station.components.auth.session import (
    SessionUser,
    get_current_user,
    require_admin,
)
from syft_station.components.credits.entities import InvoiceStatus
from syft_station.components.credits.gateway.interfaces import WebhookEnvelope
from syft_station.components.credits.handlers import (
    AuthedSpace,
    CheckoutHandler,
    CreditsHandler,
    EarningsHandler,
    InsufficientBalanceError,
    WalletAdminHandler,
    WebhookHandler,
)
from syft_station.components.credits.schemas import (
    BalanceResponse,
    BuyerBalanceResponse,
    BuyerInvoiceResponse,
    CreateInvoiceRequest,
    DebitRequest,
    DebitResponse,
    EarningsResponse,
    HubTokenMintRequest,
    HubTokenMintResponse,
    MemberEarningsResponse,
    OutstandingBalancesResponse,
    PayoutRequest,
    PayoutResponse,
    RefundRequest,
    RefundResponse,
    ReversalResponse,
    WalletSetupRequest,
    WalletSetupResponse,
    WalletStatusResponse,
)


def build_credits_routes(
    handler: CreditsHandler,
    admin_handler: WalletAdminHandler,
    checkout_handler: CheckoutHandler,
    webhook_handler: WebhookHandler,
    earnings_handler: EarningsHandler,
) -> APIRouter:
    """Build the credits routes: space-facing, buyer, admin, and webhooks."""
    router = APIRouter(prefix="/credits", tags=["credits"])

    async def get_caller(
        authorization: Annotated[str | None, Header()] = None,
    ) -> AuthedSpace:
        """Resolve the Bearer space credits token, or 401."""
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
            )
        return await handler.authenticate(token.strip())

    @router.post("/debit", response_model=DebitResponse)
    async def debit(
        request: DebitRequest,
        caller: AuthedSpace = Depends(get_caller),
    ):
        """Atomic check-and-debit, idempotent by transaction_id."""
        try:
            return await handler.debit(caller, request)
        except InsufficientBalanceError as e:
            return JSONResponse(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                content={
                    "error": "insufficient_balance",
                    "balance": e.balance,
                    "required": e.required,
                },
            )

    @router.post("/refund", response_model=RefundResponse)
    async def refund(
        request: RefundRequest,
        caller: AuthedSpace = Depends(get_caller),
    ) -> RefundResponse:
        """Reverse one of the caller's own debits (idempotent)."""
        return await handler.refund(caller, request.transaction_id)

    @router.get("/balance", response_model=BalanceResponse)
    async def balance(
        user_email: str,
        caller: AuthedSpace = Depends(get_caller),
    ) -> BalanceResponse:
        """A user's spendable balance in the station currency."""
        return await handler.balance(caller, user_email)

    # ── Buyer (SyftHub, satellite token) ────────────────────────────────────
    # Same paths and shapes as syft-space's self-hosted gateway
    # (/payments/gateway/wallets/{id}/…), so the hub drives both with one
    # client. Verification happens per-wallet in the handler — the wallet's
    # PAT is what authenticates the /verify call to the hub.

    async def get_buyer_token(
        authorization: Annotated[str | None, Header()] = None,
    ) -> str:
        """Extract the satellite bearer token; the handler verifies it."""
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
            )
        return token.strip()

    @router.get("/wallet", response_model=WalletStatusResponse)
    async def wallet_info(
        user: SessionUser = Depends(get_current_user),
    ) -> WalletStatusResponse:
        """Whether a wallet is configured — the station UI's own view."""
        return await checkout_handler.wallet_info()

    @router.post(
        "/{wallet_id}/invoices",
        response_model=BuyerInvoiceResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_invoice(
        wallet_id: UUID,
        body: CreateInvoiceRequest,
        token: str = Depends(get_buyer_token),
    ) -> BuyerInvoiceResponse:
        """Buy a bundle by name: PENDING invoice + hosted checkout session."""
        return await checkout_handler.create_invoice(wallet_id, token, body)

    @router.get("/{wallet_id}/invoices/me", response_model=list[BuyerInvoiceResponse])
    async def my_invoices(
        wallet_id: UUID,
        status_filter: Annotated[InvoiceStatus | None, Query(alias="status")] = None,
        token: str = Depends(get_buyer_token),
    ) -> list[BuyerInvoiceResponse]:
        """The buyer's own invoices, filterable by status (pending-dedup)."""
        return await checkout_handler.my_invoices(
            wallet_id, token, status_filter.value if status_filter else None
        )

    @router.get("/{wallet_id}/balance", response_model=BuyerBalanceResponse)
    async def buyer_balance(
        wallet_id: UUID,
        token: str = Depends(get_buyer_token),
    ) -> BuyerBalanceResponse:
        """The buyer's spendable balance in the wallet currency."""
        return await checkout_handler.balance(wallet_id, token)

    @router.get("/earnings/mine", response_model=MemberEarningsResponse)
    async def my_earnings(
        user: SessionUser = Depends(get_current_user),
    ) -> MemberEarningsResponse:
        """What the member's own spaces earned and are still owed."""
        return await earnings_handler.earnings_mine(user.email)

    # ── Admin (wallet setup) ────────────────────────────────────────────────

    @router.get("/admin/wallet", response_model=WalletStatusResponse)
    async def get_wallet(
        user: SessionUser = Depends(require_admin),
    ) -> WalletStatusResponse:
        """Wallet state, never credentials."""
        return await admin_handler.get()

    @router.put("/admin/wallet", response_model=WalletSetupResponse)
    async def setup_wallet(
        body: WalletSetupRequest,
        user: SessionUser = Depends(require_admin),
    ) -> WalletSetupResponse:
        """Create or replace the station wallet; attaches unbound spaces."""
        return await admin_handler.setup(body, user.email)

    @router.post("/admin/wallet/hub-token", response_model=HubTokenMintResponse)
    async def mint_hub_token(
        body: HubTokenMintRequest,
        user: SessionUser = Depends(require_admin),
    ) -> HubTokenMintResponse:
        """Mint a SyftHub API token for the wallet form (password used once)."""
        return await admin_handler.mint_hub_token(user.email, body.password)

    @router.get("/admin/earnings", response_model=EarningsResponse)
    async def earnings(
        user: SessionUser = Depends(require_admin),
    ) -> EarningsResponse:
        """Ledger-derived money dashboard: totals, per-space, per-endpoint, daily."""
        return await earnings_handler.earnings()

    @router.get("/admin/balances", response_model=OutstandingBalancesResponse)
    async def outstanding_balances(
        user: SessionUser = Depends(require_admin),
    ) -> OutstandingBalancesResponse:
        """Unspent user credit — the station's liability."""
        return await earnings_handler.outstanding_balances()

    @router.post("/admin/payouts", response_model=PayoutResponse)
    async def record_payout(
        body: PayoutRequest,
        user: SessionUser = Depends(require_admin),
    ) -> PayoutResponse:
        """Record a payout made out-of-band; capped at the space's payable."""
        return await earnings_handler.record_payout(body)

    @router.post(
        "/admin/debits/{transaction_id}/reverse", response_model=ReversalResponse
    )
    async def reverse_debit(
        transaction_id: UUID,
        user: SessionUser = Depends(require_admin),
    ) -> ReversalResponse:
        """Dispute path: refund a debit to the user (idempotent)."""
        return await earnings_handler.reverse_debit(transaction_id)

    # ── Provider webhooks (verified inside the gateway, no session) ─────────

    @router.post("/webhooks/xendit")
    async def xendit_webhook(request: Request) -> dict[str, str]:
        """Xendit event delivery — settles invoices, credits balances."""
        raw_body = await request.body()
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from e
        envelope = WebhookEnvelope(
            raw_body=raw_body,
            parsed=parsed,
            headers={k.lower(): v for k, v in request.headers.items()},
        )
        return await webhook_handler.handle("xendit", envelope)

    return router
