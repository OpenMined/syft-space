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
    Wallet,
)
from syft_station.components.credits.gateway.interfaces import (
    PaymentGateway,
    WebhookEnvelope,
)
from syft_station.components.credits.provisioning import WalletRollout
from syft_station.components.credits.repository import (
    CreditsLedger,
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.schemas import (
    BalanceResponse,
    CheckoutResponse,
    DebitRequest,
    DebitResponse,
    RefundResponse,
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


def _wallet_status(
    wallet: Wallet | None, gateways: dict[str, PaymentGateway]
) -> WalletStatusResponse:
    """Wallet state without secrets — shared by the admin and buyer views."""
    if wallet is None:
        return WalletStatusResponse(configured=False)
    gateway = gateways.get(wallet.provider)
    bundles = gateway.bundles(wallet.currency) if gateway else []
    return WalletStatusResponse(
        configured=True,
        provider=wallet.provider,
        currency=wallet.currency,
        bundles=[{"name": b.name, "amount": b.amount} for b in bundles],
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
        return _wallet_status(await self.wallets.get_active(), self.gateways)

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

        response = _wallet_status(wallet, self.gateways)
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
        return _wallet_status(await self.wallets.get_active(), self.gateways)

    async def create_checkout(
        self, user_email: str, bundle_name: str
    ) -> CheckoutResponse:
        """Create a PENDING invoice, then the provider session for it.

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
        bundle = next(
            (b for b in gateway.bundles(wallet.currency) if b.name == bundle_name),
            None,
        )
        if bundle is None:
            available = [b.name for b in gateway.bundles(wallet.currency)]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bundle '{bundle_name}' not found. Available: {available}",
            )

        invoice_id = uuid4()
        invoice = Invoice(
            id=invoice_id,
            user_email=user_email,
            provider=wallet.provider,
            client_reference=f"syft-{invoice_id}",
            bundle_name=bundle.name,
            amount=bundle.amount,
            currency=wallet.currency,
        )
        async with CreditsLedger(self.db) as ledger:
            ledger.invoices.insert(invoice)
            await ledger.commit()

        payment = await gateway.create_payment(
            reference_id=f"syft-{invoice_id}",
            amount=bundle.amount,
            currency=wallet.currency,
            payer_email=user_email,
            description=f"Syft Station credits — {bundle.name}",
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
            amount=bundle.amount,
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
