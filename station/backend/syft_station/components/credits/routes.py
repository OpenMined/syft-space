"""Credits API routes — space-facing (Bearer space credits token).

The 402 body is written at the TOP level, not inside FastAPI's usual
``{"detail": …}`` wrapper: space clients read ``response.json()["balance"]``
directly. See schemas.py for the compatibility rules.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from syft_station.components.auth.session import (
    SessionUser,
    get_current_user,
    require_admin,
)
from syft_station.components.credits.gateway.interfaces import WebhookEnvelope
from syft_station.components.credits.handlers import (
    AuthedSpace,
    CheckoutHandler,
    CreditsHandler,
    InsufficientBalanceError,
    WalletAdminHandler,
    WebhookHandler,
)
from syft_station.components.credits.schemas import (
    BalanceResponse,
    CheckoutRequest,
    CheckoutResponse,
    DebitRequest,
    DebitResponse,
    RefundRequest,
    RefundResponse,
    WalletSetupRequest,
    WalletSetupResponse,
    WalletStatusResponse,
)


def build_credits_routes(
    handler: CreditsHandler,
    admin_handler: WalletAdminHandler,
    checkout_handler: CheckoutHandler,
    webhook_handler: WebhookHandler,
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

    # ── Buyer (any signed-in session) ───────────────────────────────────────

    @router.get("/wallet", response_model=WalletStatusResponse)
    async def wallet_info(
        user: SessionUser = Depends(get_current_user),
    ) -> WalletStatusResponse:
        """Whether credits can be bought, and the bundle catalog."""
        return await checkout_handler.wallet_info()

    @router.post("/checkout", response_model=CheckoutResponse)
    async def create_checkout(
        body: CheckoutRequest,
        user: SessionUser = Depends(get_current_user),
    ) -> CheckoutResponse:
        """Start a hosted checkout for a bundle; redirect to checkout_url."""
        return await checkout_handler.create_checkout(user.email, body.bundle_name)

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
        return await admin_handler.setup(body)

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
