"""Credits handlers — the space-facing debit / refund / balance operations.

Auth model: every call carries a space credits token (Bearer). The token
resolves to its SpaceCreditToken binding, which supplies both authorization
and attribution — earnings follow the calling space, refunds are scoped to
the caller's own debits.

Idempotency: the space generates transaction_id. A replayed debit or a
concurrent double-refund lands on UNIQUE(transaction_id, type) and is
answered with the original outcome, never a second movement.
"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from syft_station.components.credits.entities import EntryType, LedgerEntry
from syft_station.components.credits.repository import (
    CreditsLedger,
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.schemas import (
    BalanceResponse,
    DebitRequest,
    DebitResponse,
    RefundResponse,
)
from syft_station.components.credits.tokens import hash_credit_token
from syft_station.components.shared.database import AsyncDatabase


class InsufficientBalanceError(Exception):
    """Debit rejected — mapped to the contract's top-level 402 body."""

    def __init__(self, balance: float, required: float):
        super().__init__(f"balance {balance} below required {required}")
        self.balance = balance
        self.required = required


@dataclass(frozen=True)
class AuthedSpace:
    """A verified caller: the space and the wallet its token is bound to."""

    space_id: UUID
    wallet_id: UUID
    currency: str


class CreditsHandler:
    """Space-facing credits operations over the CreditsLedger."""

    def __init__(
        self,
        db: AsyncDatabase,
        wallets: WalletRepository,
        credit_tokens: SpaceCreditTokenRepository,
    ):
        self.db = db
        self.wallets = wallets
        self.credit_tokens = credit_tokens

    async def authenticate(self, bearer_token: str) -> AuthedSpace:
        """Resolve a presented space token, or 401.

        A token whose wallet no longer exists is treated as revoked — it
        cannot authorize movements in a currency the station no longer has.
        """
        binding = await self.credit_tokens.get_active_by_hash(
            hash_credit_token(bearer_token)
        )
        if binding is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown or revoked space token",
            )
        wallet = await self.wallets.get_by_id(binding.wallet_id)
        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Space token is bound to a wallet that no longer exists",
            )
        return AuthedSpace(
            space_id=binding.space_id,
            wallet_id=binding.wallet_id,
            currency=wallet.currency,
        )

    async def debit(self, caller: AuthedSpace, request: DebitRequest) -> DebitResponse:
        """Atomic check-and-debit; replay-safe by transaction_id.

        The replay guarantee is "never a second debit": a known
        transaction_id returns 200 with the *current* balance (the original
        movement happened exactly once; balance_after is informational).
        """
        async with CreditsLedger(self.db) as ledger:
            existing = await ledger.entries.get(
                request.transaction_id, EntryType.DEBIT.value
            )
            if existing is not None:
                self._require_own_transaction(caller, existing)
                return await self._debit_response(ledger, caller, request)

            ok = await ledger.balances.atomic_deduct(request.user_email, request.amount)
            if not ok:
                row = await ledger.balances.get(request.user_email)
                raise InsufficientBalanceError(
                    balance=row.balance if row else 0.0, required=request.amount
                )
            ledger.entries.insert(
                LedgerEntry(
                    user_email=request.user_email,
                    transaction_id=request.transaction_id,
                    type=EntryType.DEBIT.value,
                    space_id=caller.space_id,
                    endpoint=request.endpoint,
                    amount=request.amount,
                    currency=caller.currency,
                    charge_unit=request.charge_unit,
                    charge_quantity=request.charge_quantity,
                )
            )
            try:
                await ledger.commit()
            except IntegrityError:
                # Lost a race against an identical concurrent debit — the
                # whole transaction rolled back; answer as a replay.
                await ledger.session.rollback()
            return await self._debit_response(ledger, caller, request)

    async def refund(self, caller: AuthedSpace, transaction_id: UUID) -> RefundResponse:
        """Reverse a debit (idempotent). Scope: the caller's own debits."""
        async with CreditsLedger(self.db) as ledger:
            debit = await ledger.entries.get(transaction_id, EntryType.DEBIT.value)
            if debit is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Unknown transaction",
                )
            self._require_own_transaction(caller, debit)

            already = await ledger.entries.get(
                transaction_id, EntryType.CANCELLED.value
            )
            if already is not None:
                return RefundResponse()

            # Copy the debit's attribution so analytics stay join-free.
            ledger.entries.insert(
                LedgerEntry(
                    user_email=debit.user_email,
                    transaction_id=transaction_id,
                    type=EntryType.CANCELLED.value,
                    space_id=debit.space_id,
                    endpoint=debit.endpoint,
                    amount=debit.amount,
                    currency=debit.currency,
                    charge_unit=debit.charge_unit,
                    charge_quantity=debit.charge_quantity,
                )
            )
            await ledger.balances.atomic_restore(debit.user_email, debit.amount)
            try:
                await ledger.commit()
            except IntegrityError:
                # Concurrent double refund — the other call restored; ours
                # rolled back whole. Same outcome either way.
                await ledger.session.rollback()
            return RefundResponse()

    async def balance(self, caller: AuthedSpace, user_email: str) -> BalanceResponse:
        """A user's spendable balance (0 for users with no balance row)."""
        async with CreditsLedger(self.db) as ledger:
            row = await ledger.balances.get(user_email)
            return BalanceResponse(
                balance=row.balance if row else 0.0, currency=caller.currency
            )

    @staticmethod
    def _require_own_transaction(caller: AuthedSpace, entry: LedgerEntry) -> None:
        if entry.space_id != caller.space_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Transaction belongs to another space",
            )

    @staticmethod
    async def _debit_response(
        ledger: CreditsLedger, caller: AuthedSpace, request: DebitRequest
    ) -> DebitResponse:
        row = await ledger.balances.get(request.user_email)
        return DebitResponse(
            transaction_id=request.transaction_id,
            balance_after=row.balance if row else 0.0,
            currency=caller.currency,
        )
