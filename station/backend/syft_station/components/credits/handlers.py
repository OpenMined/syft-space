"""Credits handlers, one class per caller: CreditsHandler (spaces),
CheckoutHandler (buyers via SyftHub), WalletAdminHandler + EarningsHandler
(station admin), WebhookHandler (payment providers).

Space auth model: every space call carries a space credits token (Bearer).
The token resolves to its SpaceCreditToken binding, which supplies both
authorization and attribution — earnings follow the calling space, refunds
are scoped to the caller's own debits.

Idempotency: the space generates transaction_id. A replayed debit or a
concurrent double-refund lands on UNIQUE(transaction_id, type) and is
answered with the original outcome, never a second movement.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.exc import IntegrityError

from syft_station.components.auth.syfthub import (
    SyftHubAuthError,
    SyftHubBuyerTokenError,
    SyftHubIdentityClient,
    SyftHubUnavailableError,
)
from syft_station.components.credits.bundles import bundle_amount
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
    BuyerBalanceResponse,
    BuyerInvoiceResponse,
    CreateInvoiceRequest,
    DailyEarnings,
    DebitRequest,
    DebitResponse,
    EarningsResponse,
    EarningsTotals,
    EndpointEarnings,
    MemberEarningsResponse,
    MemberSpaceEarnings,
    OutstandingBalance,
    OutstandingBalancesResponse,
    PayoutInfo,
    PayoutRequest,
    PayoutResponse,
    RefundResponse,
    ReversalResponse,
    SpaceEarnings,
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
        wallet_owner=wallet.hub_user_id,
    )


class WalletAdminHandler:
    """Station wallet setup — create/replace plus the rollout to spaces."""

    def __init__(
        self,
        wallets: WalletRepository,
        gateways: dict[str, PaymentGateway],
        rollout: WalletRollout,
        hub: SyftHubIdentityClient,
    ):
        self.wallets = wallets
        self.gateways = gateways
        self.rollout = rollout
        self.hub = hub

    async def get(self) -> WalletStatusResponse:
        return _wallet_status(await self.wallets.get_active())

    async def _mint_hub_identity(
        self, admin_email: str, password: str
    ) -> tuple[str, int]:
        """One-shot: mint the wallet's PAT and resolve its owner's user id.

        The password never outlives this call. A newly minted PAT replaces
        the stored one; the previous PAT stays valid hub-side until the
        admin revokes it from the hub's token list.
        """
        try:
            pat = await self.hub.mint_pat(admin_email, password)
            profile = await self.hub.whoami(pat)
        except SyftHubAuthError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except SyftHubUnavailableError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e
        return pat, profile.id

    async def setup(
        self, body: WalletSetupRequest, admin_email: str
    ) -> WalletSetupResponse:
        """Create the wallet, or replace its provider/credentials in place.

        Replacement keeps the wallet id, so existing space tokens stay
        bound. The currency is immutable — every user balance is
        denominated in it.

        The hub identity travels with the wallet: first setup must carry
        ``syfthub_password`` (buyer verification needs a PAT); a replace
        without it keeps the stored PAT, with it mints a fresh one.
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
        hub_pat = wallet.hub_pat if wallet else None
        hub_user_id = wallet.hub_user_id if wallet else None
        if body.syfthub_password:
            hub_pat, hub_user_id = await self._mint_hub_identity(
                admin_email, body.syfthub_password
            )
        elif hub_pat is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="syfthub_password is required — the wallet needs a hub "
                "identity to verify buyers' tokens",
            )

        if wallet is None:
            wallet = await self.wallets.create(
                Wallet(
                    provider=body.provider,
                    currency=body.currency,
                    credentials=credentials,
                    hub_user_id=hub_user_id,
                    hub_pat=hub_pat,
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
            wallet.hub_user_id = hub_user_id
            wallet.hub_pat = hub_pat
            wallet.updated_at = datetime.now(UTC)
            wallet = await self.wallets.update(wallet)

        # Spaces approved before the wallet existed (and not opted out) get
        # attached now; their Secrets apply on restart.
        attached, failed = await self.rollout.attach_unbound_spaces(wallet.id)

        response = _wallet_status(wallet)
        return WalletSetupResponse(
            **response.model_dump(), spaces_attached=attached, spaces_failed=failed
        )


_BUYER_CACHE_TTL_SECONDS = 60.0
_BUYER_CACHE_MAX_ENTRIES = 1024


def _buyer_invoice(invoice: Invoice, wallet_id: UUID) -> BuyerInvoiceResponse:
    """Shape one invoice the way the self-hosted gateway would."""
    return BuyerInvoiceResponse(
        id=invoice.id,
        wallet_id=wallet_id,
        user_email=invoice.user_email,
        provider=invoice.provider,
        client_reference=invoice.client_reference,
        checkout_url=invoice.checkout_url,
        provider_session_id=invoice.provider_session_id,
        bundle_name=invoice.bundle_name,
        amount=invoice.amount,
        currency=invoice.currency,
        status=invoice.status,
        paid_at=invoice.paid_at,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


class CheckoutHandler:
    """Buyer-facing, driven by SyftHub with satellite tokens.

    Speaks the same contract as syft-space's self-hosted gateway (buy a
    bundle by name, list own invoices, read balance) so the hub runs one
    buyer flow against managed and self-hosted spaces alike. Every call is
    authenticated by verifying the token against the hub with the wallet's
    PAT — the hub derives the authorized audience from the PAT's owner.
    """

    def __init__(
        self,
        db: AsyncDatabase,
        wallets: WalletRepository,
        gateways: dict[str, PaymentGateway],
        hub: SyftHubIdentityClient,
    ):
        self.db = db
        self.wallets = wallets
        self.gateways = gateways
        self.hub = hub
        # token-hash → (email, absolute expiry). /verify is a network call on
        # the buyer read hot-path; satellite tokens are short-lived, so cache
        # verdicts until the token's own exp (capped at a short TTL).
        self._buyer_cache: dict[str, tuple[str, float]] = {}

    async def wallet_info(self) -> WalletStatusResponse:
        return _wallet_status(await self.wallets.get_active())

    async def _resolve_wallet(self, wallet_id: UUID) -> Wallet:
        """The wallet a buyer URL names, or 404. Buyer routes are scoped by
        wallet id (published that way), so the balance/checkout they hit is
        explicit rather than 'whichever wallet is active'."""
        wallet = await self.wallets.get_by_id(wallet_id)
        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found"
            )
        return wallet

    async def _verify_buyer(self, wallet: Wallet, token: str) -> str:
        """Resolve a satellite token to the buyer's billing email.

        Raises 401 for a bad buyer token; 502 when the hub is unreachable
        or the wallet's own PAT is rejected — station-side problems the
        buyer can't fix.
        """
        if not wallet.hub_pat:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The station wallet has no SyftHub identity — "
                "ask the admin to reconnect it",
            )
        key = sha256(token.encode()).hexdigest()
        now = time.time()
        cached = self._buyer_cache.get(key)
        if cached and cached[1] > now:
            return cached[0]

        try:
            buyer = await self.hub.verify_buyer_token(wallet.hub_pat, token)
        except SyftHubBuyerTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
            ) from e
        except SyftHubAuthError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SyftHub rejected the station's API token — "
                "reconnect the wallet",
            ) from e
        except SyftHubUnavailableError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e

        expires = now + _BUYER_CACHE_TTL_SECONDS
        if buyer.exp is not None:
            expires = min(expires, float(buyer.exp))
        if len(self._buyer_cache) >= _BUYER_CACHE_MAX_ENTRIES:
            self._buyer_cache = {
                k: v for k, v in self._buyer_cache.items() if v[1] > now
            }
        self._buyer_cache[key] = (buyer.email, expires)
        return buyer.email

    async def create_invoice(
        self, wallet_id: UUID, token: str, body: CreateInvoiceRequest
    ) -> BuyerInvoiceResponse:
        """Buy a bundle: create a PENDING invoice, then the provider session.

        The bundle name is priced from the station's catalog (the same table
        the spaces publish), so the hub can only buy what was advertised.

        Order matters: the invoice exists before the provider call, so a
        provider session can never outlive the local row. If the provider
        call fails, the invoice stays PENDING — harmless, and a webhook can
        still settle it if the session actually went through.
        """
        wallet = await self._resolve_wallet(wallet_id)
        user_email = await self._verify_buyer(wallet, token)
        amount = bundle_amount(wallet.currency, body.bundle_name)
        if amount is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown bundle '{body.bundle_name}' "
                f"for currency {wallet.currency}",
            )
        gateway = self.gateways.get(wallet.provider)
        if gateway is None:
            raise HTTPException(
                status_code=500, detail=f"No gateway for provider '{wallet.provider}'"
            )

        invoice_id = uuid4()
        invoice = Invoice(
            id=invoice_id,
            user_email=user_email,
            provider=wallet.provider,
            client_reference=f"syft-{invoice_id}",
            bundle_name=body.bundle_name,
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
            description=f"Syft Station credits — {body.bundle_name}",
            credentials=wallet.credentials,
        )

        async with CreditsLedger(self.db) as ledger:
            await ledger.invoices.set_checkout_metadata(
                invoice_id, payment.checkout_url, payment.provider_session_id
            )
            await ledger.commit()
            final = await ledger.invoices.get(invoice_id)

        assert final is not None  # inserted above
        return _buyer_invoice(final, wallet.id)

    async def my_invoices(
        self, wallet_id: UUID, token: str, status_filter: str | None = None
    ) -> list[BuyerInvoiceResponse]:
        """The buyer's own invoices, newest first — the hub's pending-dedup."""
        wallet = await self._resolve_wallet(wallet_id)
        user_email = await self._verify_buyer(wallet, token)
        async with CreditsLedger(self.db) as ledger:
            invoices = await ledger.invoices.list_for_user(
                user_email, status=status_filter
            )
        return [_buyer_invoice(i, wallet.id) for i in invoices]

    async def balance(self, wallet_id: UUID, token: str) -> BuyerBalanceResponse:
        """The buyer's spendable balance in the wallet currency."""
        wallet = await self._resolve_wallet(wallet_id)
        user_email = await self._verify_buyer(wallet, token)
        async with CreditsLedger(self.db) as ledger:
            row = await ledger.balances.get(user_email)
        return BuyerBalanceResponse(
            wallet_id=wallet.id,
            user_email=user_email,
            balance=row.balance if row else 0.0,
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
