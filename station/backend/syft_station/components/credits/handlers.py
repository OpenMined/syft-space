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
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.exc import IntegrityError

from syft_station.components.credits.entities import (
    EntryType,
    Invoice,
    InvoiceStatus,
    LedgerEntry,
    Payout,
    Wallet,
)
from syft_station.components.credits.gateway.interfaces import (
    PaymentGateway,
    WebhookEnvelope,
)
from syft_station.components.credits.interfaces import SpaceDirectory
from syft_station.components.credits.provisioning import WalletRollout
from syft_station.components.credits.repository import (
    CreditsLedger,
    PayoutRepository,
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.schemas import (
    BalanceResponse,
    CheckoutResponse,
    DailyEarnings,
    DebitRequest,
    DebitResponse,
    EarningsResponse,
    EarningsTotals,
    EndpointEarnings,
    MemberEarningsResponse,
    MemberSpaceEarnings,
    MyCreditsResponse,
    OutstandingBalance,
    OutstandingBalancesResponse,
    PayoutInfo,
    PayoutRequest,
    PayoutResponse,
    RefundResponse,
    ReversalResponse,
    SpaceEarnings,
    SpendEntry,
    TopUpInfo,
    WalletSetupRequest,
    WalletSetupResponse,
    WalletStatusResponse,
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


def _wallet_status(wallet: Wallet | None) -> WalletStatusResponse:
    """Wallet state without secrets — shared by the admin and buyer views."""
    if wallet is None:
        return WalletStatusResponse(configured=False)
    return WalletStatusResponse(
        configured=True,
        provider=wallet.provider,
        currency=wallet.currency,
    )


class WalletAdminHandler:
    """Station wallet setup — create/replace plus the rollout to spaces."""

    def __init__(
        self,
        wallets: WalletRepository,
        gateways: dict[str, PaymentGateway],
        rollout: WalletRollout,
    ):
        self.wallets = wallets
        self.gateways = gateways
        self.rollout = rollout

    async def get(self) -> WalletStatusResponse:
        return _wallet_status(await self.wallets.get_active())

    async def setup(self, body: WalletSetupRequest) -> WalletSetupResponse:
        """Create the wallet, or replace its provider/credentials in place.

        Replacement keeps the wallet id, so existing space tokens stay
        bound. The currency is immutable — every user balance is
        denominated in it.
        """
        gateway = self.gateways.get(body.provider)
        if gateway is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported provider '{body.provider}'. "
                f"Available: {sorted(self.gateways)}",
            )
        credentials = gateway.validate_credentials(body.credentials, body.currency)

        wallet = await self.wallets.get_active()
        if wallet is None:
            wallet = await self.wallets.create(
                Wallet(
                    provider=body.provider,
                    currency=body.currency,
                    credentials=credentials,
                )
            )
        else:
            if wallet.currency != body.currency:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"The wallet currency is fixed at {wallet.currency} — "
                    "user balances are denominated in it",
                )
            wallet.provider = body.provider
            wallet.credentials = credentials
            wallet.updated_at = datetime.now(UTC)
            wallet = await self.wallets.update(wallet)

        # Spaces approved before the wallet existed (and not opted out) get
        # attached now; their Secrets apply on restart.
        attached, failed = await self.rollout.attach_unbound_spaces(wallet.id)

        response = _wallet_status(wallet)
        return WalletSetupResponse(
            **response.model_dump(), spaces_attached=attached, spaces_failed=failed
        )


class CheckoutHandler:
    """Buyer-facing: view the wallet's bundles, start a hosted checkout."""

    def __init__(
        self,
        db: AsyncDatabase,
        wallets: WalletRepository,
        gateways: dict[str, PaymentGateway],
    ):
        self.db = db
        self.wallets = wallets
        self.gateways = gateways

    async def wallet_info(self) -> WalletStatusResponse:
        return _wallet_status(await self.wallets.get_active())

    async def my_credits(self, user_email: str) -> MyCreditsResponse:
        """The signed-in user's balance, purchases, and spend history."""
        wallet = await self.wallets.get_active()
        async with CreditsLedger(self.db) as ledger:
            row = await ledger.balances.get(user_email)
            invoices = await ledger.invoices.list_for_user(user_email)
            entries = await ledger.entries.list_for_user(user_email)
            return MyCreditsResponse(
                balance=row.balance if row else 0.0,
                currency=wallet.currency if wallet else "",
                top_ups=[
                    TopUpInfo(
                        invoice_id=i.id,
                        user_email=i.user_email,
                        bundle_name=i.bundle_name,
                        amount=i.amount,
                        currency=i.currency,
                        status=i.status,
                        created_at=i.created_at,
                        paid_at=i.paid_at,
                    )
                    for i in invoices
                ],
                spend=[
                    SpendEntry(
                        transaction_id=e.transaction_id,
                        type=e.type,
                        space_id=e.space_id,
                        endpoint=e.endpoint,
                        amount=e.amount,
                        created_at=e.created_at,
                    )
                    for e in entries
                ],
            )

    async def create_checkout(
        self, user_email: str, amount: float, label: str | None = None
    ) -> CheckoutResponse:
        """Create a PENDING invoice, then the provider session for it.

        The amount is charged as-is — credits are 1:1 with the wallet
        currency, so there's nothing to validate against a catalog (the
        spaces own the purchasable bundles). ``label`` is display-only.

        Order matters: the invoice exists before the provider call, so a
        provider session can never outlive the local row. If the provider
        call fails, the invoice stays PENDING — harmless, and a webhook can
        still settle it if the session actually went through.
        """
        wallet = await self.wallets.get_active()
        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The station has no payment wallet configured",
            )
        gateway = self.gateways.get(wallet.provider)
        if gateway is None:
            raise HTTPException(
                status_code=500, detail=f"No gateway for provider '{wallet.provider}'"
            )
        display = label or "Credits top-up"

        invoice_id = uuid4()
        invoice = Invoice(
            id=invoice_id,
            user_email=user_email,
            provider=wallet.provider,
            client_reference=f"syft-{invoice_id}",
            bundle_name=display,
            amount=amount,
            currency=wallet.currency,
        )
        async with CreditsLedger(self.db) as ledger:
            ledger.invoices.insert(invoice)
            await ledger.commit()

        payment = await gateway.create_payment(
            reference_id=f"syft-{invoice_id}",
            amount=amount,
            currency=wallet.currency,
            payer_email=user_email,
            description=f"Syft Station credits — {display}",
            credentials=wallet.credentials,
        )

        async with CreditsLedger(self.db) as ledger:
            await ledger.invoices.set_checkout_metadata(
                invoice_id, payment.checkout_url, payment.provider_session_id
            )
            await ledger.commit()

        return CheckoutResponse(
            invoice_id=invoice_id,
            checkout_url=payment.checkout_url,
            amount=amount,
            currency=wallet.currency,
        )


class WebhookHandler:
    """Provider webhooks: verify, normalize, settle, credit."""

    def __init__(
        self,
        db: AsyncDatabase,
        wallets: WalletRepository,
        gateways: dict[str, PaymentGateway],
    ):
        self.db = db
        self.wallets = wallets
        self.gateways = gateways

    async def handle(self, provider: str, envelope: WebhookEnvelope) -> dict[str, str]:
        """Process one webhook delivery, idempotently.

        Everything that should NOT be retried by the provider is answered
        200 with a status word ("ignored", "unknown_reference",
        "already_processed") — providers retry on any non-2xx, and only
        authentication failures deserve that.
        """
        wallet = await self.wallets.get_active()
        if wallet is None or wallet.provider != provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {provider} wallet is configured",
            )
        gateway = self.gateways[provider]
        gateway.verify_webhook(envelope, wallet.credentials)

        result = gateway.normalize_webhook(envelope)
        if result is None:
            return {"status": "ignored"}

        async with CreditsLedger(self.db) as ledger:
            invoice = await ledger.invoices.get_by_client_reference(
                result.client_reference
            )
            if invoice is None:
                # Not ours (e.g. another system on the same provider account).
                logger.info(f"Webhook for unknown reference {result.client_reference}")
                return {"status": "unknown_reference"}

            if result.status == InvoiceStatus.PAID.value:
                settled = await ledger.invoices.mark_paid(
                    invoice.id, result.raw_payload, paid_at=result.paid_at
                )
                if settled:
                    # Same transaction as mark_paid: the credit and the
                    # settlement land (or roll back) together.
                    await ledger.balances.upsert_credit(
                        invoice.user_email, invoice.amount
                    )
                await ledger.commit()
                return {"status": "ok" if settled else "already_processed"}

            moved = await ledger.invoices.update_status(invoice.id, result.status)
            await ledger.commit()
            return {"status": "ok" if moved else "already_processed"}


class EarningsHandler:
    """Admin money views + payout recording + debit reversal.

    Every figure is derived from the ledger (never stored), so the numbers
    always reconcile: earned = Σ(DEBIT) − Σ(CANCELLED) per space, payable =
    earned − Σ(payouts).
    """

    # Float-sum tolerance for "payout exceeds payable" checks.
    _EPSILON = 1e-9

    def __init__(
        self,
        db: AsyncDatabase,
        wallets: WalletRepository,
        payouts: PayoutRepository,
        spaces: SpaceDirectory,
    ):
        self.db = db
        self.wallets = wallets
        self.payouts = payouts
        self.spaces = spaces

    async def earnings(self) -> EarningsResponse:
        wallet = await self.wallets.get_active()
        paid_out_by_space = await self.payouts.totals_by_space()
        recent_payouts = await self.payouts.list_recent()

        async with CreditsLedger(self.db) as ledger:
            by_space = await ledger.entries.earnings_by_space()
            by_endpoint = await ledger.entries.earnings_by_endpoint()
            by_day = await ledger.entries.earnings_by_day()
            credits_sold = await ledger.invoices.total_paid()
            outstanding = await ledger.balances.total_outstanding()
            recent_top_ups = await ledger.invoices.list_recent_paid()

        spaces = [
            SpaceEarnings(
                space_id=row.space_id,
                earned=row.earned,
                query_count=row.query_count,
                paid_out=paid_out_by_space.get(row.space_id, 0.0),
                payable=row.earned - paid_out_by_space.get(row.space_id, 0.0),
            )
            for row in by_space
        ]
        return EarningsResponse(
            currency=wallet.currency if wallet else "",
            totals=EarningsTotals(
                credits_sold=credits_sold,
                earned=sum(s.earned for s in spaces),
                paid_out=sum(s.paid_out for s in spaces),
                outstanding_balance=outstanding,
            ),
            spaces=spaces,
            endpoints=[
                EndpointEarnings(
                    space_id=row.space_id,
                    endpoint=row.endpoint,
                    earned=row.earned,
                    query_count=row.query_count,
                )
                for row in by_endpoint
            ],
            daily=[
                DailyEarnings(
                    day=row.day,
                    space_id=row.space_id,
                    earned=row.earned,
                    query_count=row.query_count,
                )
                for row in by_day
            ],
            recent_top_ups=[
                TopUpInfo(
                    invoice_id=i.id,
                    user_email=i.user_email,
                    bundle_name=i.bundle_name,
                    amount=i.amount,
                    currency=i.currency,
                    status=i.status,
                    created_at=i.created_at,
                    paid_at=i.paid_at,
                )
                for i in recent_top_ups
            ],
            payouts=[
                PayoutInfo(
                    id=p.id,
                    space_id=p.space_id,
                    amount=p.amount,
                    note=p.note,
                    created_at=p.created_at,
                )
                for p in recent_payouts
            ],
        )

    async def earnings_mine(self, owner_email: str) -> MemberEarningsResponse:
        """Money view for a member's own spaces. The headline is payable —
        what the station admin still owes them (earned − paid out)."""
        wallet = await self.wallets.get_active()
        owned = await self.spaces.list_by_owner(owner_email)
        paid_out_by_space = await self.payouts.totals_by_space()

        async with CreditsLedger(self.db) as ledger:
            earned_rows = {
                row.space_id: row for row in await ledger.entries.earnings_by_space()
            }

        spaces = []
        for space in owned:
            row = earned_rows.get(space.id)
            if row is None:
                continue  # never earned — no money line for it
            paid_out = paid_out_by_space.get(space.id, 0.0)
            spaces.append(
                MemberSpaceEarnings(
                    space_id=space.id,
                    name=space.name,
                    subdomain=space.subdomain,
                    earned=row.earned,
                    query_count=row.query_count,
                    paid_out=paid_out,
                    payable=row.earned - paid_out,
                )
            )
        return MemberEarningsResponse(
            currency=wallet.currency if wallet else "",
            spaces=spaces,
            total_earned=sum(s.earned for s in spaces),
            total_paid_out=sum(s.paid_out for s in spaces),
            total_payable=sum(s.payable for s in spaces),
        )

    async def outstanding_balances(self) -> OutstandingBalancesResponse:
        async with CreditsLedger(self.db) as ledger:
            rows = await ledger.balances.list_nonzero()
            total = await ledger.balances.total_outstanding()
            topped_up = await ledger.invoices.paid_totals_by_user()
            spent = await ledger.entries.net_spend_by_user()
        return OutstandingBalancesResponse(
            total=total,
            balances=[
                OutstandingBalance(
                    user_email=r.user_email,
                    topped_up=topped_up.get(r.user_email, 0.0),
                    spent=spent.get(r.user_email, 0.0),
                    balance=r.balance,
                )
                for r in rows
            ],
        )

    async def record_payout(self, body: PayoutRequest) -> PayoutResponse:
        """Record money already moved out-of-band. Capped at the payable —
        overpaying a space is a bookkeeping error, not a feature."""
        async with CreditsLedger(self.db) as ledger:
            earned = await ledger.entries.earned_for_space(body.space_id)
        paid_out = await self.payouts.total_for_space(body.space_id)
        payable = earned - paid_out
        if body.amount > payable + self._EPSILON:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Payout {body.amount} exceeds the space's payable {payable}",
            )

        payout = await self.payouts.create(
            Payout(space_id=body.space_id, amount=body.amount, note=body.note)
        )
        return PayoutResponse(
            id=payout.id,
            space_id=payout.space_id,
            amount=payout.amount,
            note=payout.note,
            created_at=payout.created_at,
            payable_after=payable - body.amount,
        )

    async def reverse_debit(self, transaction_id: UUID) -> ReversalResponse:
        """Admin dispute path: undo a debit regardless of which space made
        it. Same CANCELLED mechanism as a space refund — the user gets the
        money back and the space's earned/payable drops. Idempotent."""
        async with CreditsLedger(self.db) as ledger:
            debit = await ledger.entries.get(transaction_id, EntryType.DEBIT.value)
            if debit is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Unknown transaction",
                )
            already = await ledger.entries.get(
                transaction_id, EntryType.CANCELLED.value
            )
            if already is not None:
                return ReversalResponse()

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
                # Raced a concurrent refund of the same debit — one of the
                # two restored; the other rolled back whole.
                await ledger.session.rollback()
            return ReversalResponse()
