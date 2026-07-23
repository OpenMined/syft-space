"""Credits API routes — space-facing (Bearer space credits token).

The 402 body is written at the TOP level, not inside FastAPI's usual
``{"detail": …}`` wrapper: space clients read ``response.json()["balance"]``
directly. See schemas.py for the compatibility rules.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse

from syft_station.components.credits.handlers import (
    AuthedSpace,
    CreditsHandler,
    InsufficientBalanceError,
)
from syft_station.components.credits.schemas import (
    BalanceResponse,
    DebitRequest,
    DebitResponse,
    RefundRequest,
    RefundResponse,
)


def build_credits_routes(handler: CreditsHandler) -> APIRouter:
    """Build the credits routes."""
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

    return router
