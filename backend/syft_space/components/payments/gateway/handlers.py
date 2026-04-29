"""Payment handler — single use case class for all providers.

Shared business logic lives here. Provider-specific API calls and
webhook parsing are delegated to PaymentGateway implementations.
Wallet-scoped: invoices and balance hang off Wallet, not Endpoint.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from loguru import logger

from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.payments.gateway.balance_service import BalanceService
from syft_space.components.payments.gateway.entities import Invoice, InvoiceStatus
from syft_space.components.payments.gateway.interfaces import PaymentGateway
from syft_space.components.payments.gateway.payment_ledger import PaymentLedger
from syft_space.components.payments.gateway.schemas import (
    CreateInvoiceRequest,
    InvoiceResponse,
    LedgerEntryPage,
    LedgerEntryResponse,
    UserBalanceResponse,
)
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.repository import WalletRepository


class PaymentHandler:
    """Single handler for all payment operations.

    Wallet-scoped: a user buys credits against a Wallet (not an Endpoint).
    Balance is fungible across all endpoints whose policies reference the
    same wallet.

    Provider-specific logic is delegated to PaymentGateway implementations.
    """

    def __init__(
        self,
        balance_service: BalanceService,
        payment_ledger_factory: Callable[[], PaymentLedger],
        wallet_repository: WalletRepository,
        endpoint_repository: EndpointRepository,
        gateways: dict[str, PaymentGateway],
    ):
        self.balance_service = balance_service
        self._ledger = payment_ledger_factory
        self.wallet_repo = wallet_repository
        self.endpoint_repo = endpoint_repository
        self.gateways = gateways

    def _get_gateway(self, provider: str) -> PaymentGateway:
        """Get gateway by provider name. Raises 400 if unknown."""
        gateway = self.gateways.get(provider)
        if not gateway:
            available = list(self.gateways.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown payment provider '{provider}'. Available: {available}",
            )
        return gateway

    # ── Provider-scoped: invoice creation ──────────────────────────

    async def create_invoice(
        self,
        provider: str,
        wallet_id: UUID,
        request: CreateInvoiceRequest,
        tenant: Tenant,
        user_email: str,
    ) -> InvoiceResponse:
        """Create an invoice for a bundle purchase against a specific wallet."""
        gateway = self._get_gateway(provider)

        # 1. Resolve and validate wallet
        wallet = await self.wallet_repo.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        if wallet.wallet_type != gateway.PROVIDER_NAME:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Wallet type '{wallet.wallet_type}' does not match "
                    f"provider '{gateway.PROVIDER_NAME}'"
                ),
            )
        if not wallet.is_active:
            raise HTTPException(status_code=400, detail="Wallet is not active")

        # 2. Resolve bundle from wallet's catalog
        bundle = gateway.resolve_purchase(wallet, request.bundle_name)

        # 3. Optional endpoint context (for analytics)
        endpoint_id: UUID | None = None
        if request.endpoint_slug:
            endpoint = await self.endpoint_repo.get_by_slug(
                request.endpoint_slug, tenant.id
            )
            if endpoint:
                endpoint_id = endpoint.id

        # 4. Call provider API via gateway
        reference_id = (
            f"syft-{wallet.id}-{user_email}-{datetime.now(timezone.utc).timestamp()}"
        )
        result = await gateway.create_payment(
            reference_id=reference_id,
            amount=bundle.amount,
            currency=bundle.currency,
            payer_email=user_email,
            description=f"Bundle: {bundle.name} ({bundle.amount} {bundle.currency})",
            wallet=wallet,
            metadata={
                "wallet_id": str(wallet.id),
                "tenant_id": str(tenant.id),
                "bundle_name": bundle.name,
            },
        )

        # 5. Store invoice
        invoice = Invoice(
            tenant_id=tenant.id,
            wallet_id=wallet.id,
            endpoint_id=endpoint_id,
            user_email=user_email,
            provider=gateway.PROVIDER_NAME,
            external_id=result.external_id,
            checkout_url=result.checkout_url,
            bundle_name=bundle.name,
            amount=bundle.amount,
            currency=bundle.currency,
            status=InvoiceStatus.PENDING.value,
        )
        async with self._ledger() as ledger:
            await ledger.invoices.create(invoice)
            await ledger.commit()
        return InvoiceResponse.model_validate(invoice)

    # ── Provider-scoped: webhook handling ──────────────────────────

    async def handle_webhook(
        self, provider: str, raw_payload: dict, callback_token: str
    ) -> dict:
        """Handle a provider webhook callback.

        Idempotent: invoice status only transitions from PENDING; PAID credits
        are de-duped via the same status guard inside BalanceService.credit_invoice.
        """
        gateway = self._get_gateway(provider)

        webhook_result = gateway.normalize_webhook(raw_payload)

        async with self._ledger() as ledger:
            invoice = await ledger.invoices.get_by_external_id(
                webhook_result.external_id
            )
        if not invoice:
            logger.warning(
                f"Webhook: invoice not found for external_id={webhook_result.external_id}"
            )
            return {"status": "ignored", "reason": "invoice not found"}

        # Verify webhook authenticity using the invoice's wallet
        if not invoice.wallet_id:
            logger.error(f"Webhook: invoice {invoice.id} has no wallet_id")
            raise HTTPException(status_code=500, detail="Invoice missing wallet")
        wallet = await self.wallet_repo.get_by_id(invoice.wallet_id, invoice.tenant_id)
        if not wallet:
            logger.error(
                f"Webhook: wallet {invoice.wallet_id} not found for invoice {invoice.id}"
            )
            raise HTTPException(status_code=500, detail="Wallet not found")
        gateway.verify_webhook(callback_token, wallet)

        # PAID is the only status that touches balance; status transition and
        # balance increment must be atomic. Other terminal statuses (EXPIRED,
        # FAILED) just flip status with no balance side-effect.
        if webhook_result.status == InvoiceStatus.PAID:
            applied = await self.balance_service.credit_invoice(
                invoice=invoice,
                paid_at=webhook_result.paid_at,
                webhook_payload=webhook_result.raw_payload,
            )
            if not applied:
                logger.info(
                    f"Webhook: invoice {invoice.id} already processed (idempotent)"
                )
                return {"status": "already_processed"}
            logger.info(
                f"Webhook: credited {invoice.amount} {invoice.currency} "
                f"to {invoice.user_email} on wallet {invoice.wallet_id}"
            )
            return {"status": "paid", "amount_credited": invoice.amount}

        async with self._ledger() as ledger:
            updated = await ledger.invoices.update_status(
                invoice.id,
                webhook_result.status,
                paid_at=webhook_result.paid_at,
                webhook_payload=webhook_result.raw_payload,
            )
            if updated:
                await ledger.commit()
        if not updated:
            logger.info(f"Webhook: invoice {invoice.id} already processed (idempotent)")
            return {"status": "already_processed"}
        return {"status": webhook_result.status.value}

    # ── Generic: reads ─────────────────────────────────────────────

    async def get_invoice(self, invoice_id: UUID, tenant: Tenant) -> InvoiceResponse:
        """Get an invoice by ID within a tenant."""
        async with self._ledger() as ledger:
            invoice = await ledger.invoices.get_by_id(invoice_id, tenant.id)
        if not invoice:
            raise HTTPException(
                status_code=404, detail=f"Invoice '{invoice_id}' not found"
            )
        return InvoiceResponse.model_validate(invoice)

    async def get_invoices_by_wallet(
        self, wallet_id: UUID, tenant: Tenant
    ) -> list[InvoiceResponse]:
        """Admin: all invoices for a wallet."""
        wallet = await self.wallet_repo.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        async with self._ledger() as ledger:
            invoices = await ledger.invoices.get_by_wallet_id(wallet.id, tenant.id)
        return [InvoiceResponse.model_validate(inv) for inv in invoices]

    async def get_user_balance(
        self,
        wallet_id: UUID,
        user_email: str,
        tenant: Tenant,
    ) -> UserBalanceResponse:
        """User-facing balance lookup for a wallet."""
        wallet = await self.wallet_repo.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        balance = await self.balance_service.get_balance(
            wallet_id=wallet.id, tenant_id=tenant.id, user_email=user_email
        )
        return UserBalanceResponse(
            wallet_id=wallet.id,
            user_email=user_email,
            balance=balance,
            currency=wallet.currency,
        )

    async def list_user_transactions(
        self,
        wallet_id: UUID,
        user_email: str,
        tenant: Tenant,
        cursor: str | None,
        limit: int,
    ) -> LedgerEntryPage:
        """User-facing transaction history (their own activity for this wallet)."""
        wallet = await self.wallet_repo.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        async with self._ledger() as ledger:
            rows, next_cursor = await ledger.entries.list_for_user(
                tenant_id=tenant.id,
                wallet_id=wallet.id,
                user_email=user_email,
                cursor=cursor,
                limit=limit,
            )
        return LedgerEntryPage(
            items=[LedgerEntryResponse.model_validate(r) for r in rows],
            next_cursor=next_cursor,
        )

    async def list_wallet_transactions(
        self,
        wallet_id: UUID,
        tenant: Tenant,
        cursor: str | None,
        limit: int,
    ) -> LedgerEntryPage:
        """Admin transaction history across all users for a wallet."""
        wallet = await self.wallet_repo.get_by_id(wallet_id, tenant.id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        async with self._ledger() as ledger:
            rows, next_cursor = await ledger.entries.list_for_wallet(
                tenant_id=tenant.id,
                wallet_id=wallet.id,
                cursor=cursor,
                limit=limit,
            )
        return LedgerEntryPage(
            items=[LedgerEntryResponse.model_validate(r) for r in rows],
            next_cursor=next_cursor,
        )
