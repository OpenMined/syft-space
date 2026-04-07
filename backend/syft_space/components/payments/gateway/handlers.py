"""Payment handler — single use case class for all providers.

Shared business logic lives here. Provider-specific API calls and
webhook parsing are delegated to PaymentGateway implementations.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from loguru import logger

from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.payments.gateway.bundle_usage_repository import (
    BundleUsageRepository,
)
from syft_space.components.payments.gateway.entities import Invoice, InvoiceStatus
from syft_space.components.payments.gateway.interfaces import PaymentGateway
from syft_space.components.payments.gateway.invoice_repository import InvoiceRepository
from syft_space.components.payments.gateway.schemas import (
    BundleUsageResponse,
    CreateInvoiceRequest,
    InvoiceResponse,
)
from syft_space.components.policies.repository import PolicyRepository
from syft_space.components.shared.utils import matches_any_pattern
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.repository import WalletRepository


class PaymentHandler:
    """Single handler for all payment operations.

    Provider-specific logic is delegated to PaymentGateway implementations.
    Shared business logic (validate endpoint, find tier, store invoice,
    credit bundles) lives here and is never duplicated.
    """

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        bundle_usage_repository: BundleUsageRepository,
        wallet_repository: WalletRepository,
        endpoint_repository: EndpointRepository,
        policy_repository: PolicyRepository,
        gateways: dict[str, PaymentGateway],
    ):
        self.invoice_repo = invoice_repository
        self.bundle_usage_repo = bundle_usage_repository
        self.wallet_repo = wallet_repository
        self.endpoint_repo = endpoint_repository
        self.policy_repo = policy_repository
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
        request: CreateInvoiceRequest,
        tenant: Tenant,
        user_email: str,
    ) -> InvoiceResponse:
        """Create an invoice for a bundle purchase.

        Shared flow: validate endpoint → find policy → find tier →
        check applied_to → get wallet → gateway.create_payment() → store Invoice.
        """
        gateway = self._get_gateway(provider)

        # 1. Resolve endpoint
        endpoint = await self.endpoint_repo.get_by_slug(
            request.endpoint_slug, tenant.id
        )
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail=f"Endpoint '{request.endpoint_slug}' not found",
            )
        if not endpoint.published:
            raise HTTPException(status_code=400, detail="Endpoint is not published")
        if endpoint.archived:
            raise HTTPException(
                status_code=400,
                detail="Endpoint is archived — no new purchases allowed",
            )

        # 2. Find payment policy matching this provider
        policies = await self.policy_repo.get_by_endpoint_id(endpoint.id, tenant.id)
        payment_policy = next(
            (p for p in policies if p.policy_type == gateway.POLICY_TYPE), None
        )
        if not payment_policy:
            raise HTTPException(
                status_code=400,
                detail=f"Endpoint does not have a '{gateway.POLICY_TYPE}' payment policy",
            )
        config = payment_policy.configuration

        # 3. Find the requested tier
        tiers = config.get("bundle_tiers", [])
        tier = next((t for t in tiers if t["name"] == request.tier_name), None)
        if not tier:
            available = [t["name"] for t in tiers]
            raise HTTPException(
                status_code=400,
                detail=f"Tier '{request.tier_name}' not found. Available: {available}",
            )

        # 4. Check applied_to
        applied_to = config.get("applied_to", ["*"])
        if not matches_any_pattern(user_email, applied_to):
            raise HTTPException(
                status_code=403,
                detail="User is not eligible for this endpoint's payment policy",
            )

        # 5. Get wallet
        wallet = await self.wallet_repo.get_by_type(gateway.PROVIDER_NAME, tenant.id)
        if not wallet or not wallet.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"{gateway.PROVIDER_NAME} wallet not configured or inactive",
            )

        # 6. Call provider API via gateway
        currency = config.get("currency", "USD")
        unit_type = tier.get("unit_type", "requests")
        tier_units = tier["units"]
        amount = tier["price"]
        reference_id = f"syft-{endpoint.slug}-{user_email}-{datetime.now(timezone.utc).timestamp()}"

        result = await gateway.create_payment(
            reference_id=reference_id,
            amount=amount,
            currency=currency,
            payer_email=user_email,
            description=f"Bundle: {tier['name']} ({tier_units} {unit_type}) for {endpoint.slug}",
            wallet=wallet,
            policy_config=config,
            metadata={
                "endpoint_slug": endpoint.slug,
                "tenant_id": str(tenant.id),
                "tier_name": tier["name"],
                "tier_units": str(tier_units),
                "unit_type": unit_type,
            },
        )

        # 7. Store invoice
        invoice = Invoice(
            tenant_id=tenant.id,
            endpoint_id=endpoint.id,
            user_email=user_email,
            provider=gateway.PROVIDER_NAME,
            external_id=result.external_id,
            checkout_url=result.checkout_url,
            tier_name=tier["name"],
            tier_units=tier_units,
            unit_type=unit_type,
            amount=amount,
            currency=currency,
            status=InvoiceStatus.PENDING.value,
        )
        created = await self.invoice_repo.create(invoice)
        return InvoiceResponse.model_validate(created)

    # ── Provider-scoped: webhook handling ──────────────────────────

    async def handle_webhook(
        self, provider: str, raw_payload: dict, callback_token: str
    ) -> dict:
        """Handle a provider webhook callback.

        Shared flow: normalize payload → find invoice → verify auth →
        update status → credit bundle (if paid).

        Idempotent: only processes invoices in PENDING status.
        """
        gateway = self._get_gateway(provider)

        # 1. Normalize webhook payload via gateway
        webhook_result = gateway.normalize_webhook(raw_payload)

        # 2. Find invoice by external_id
        invoice = await self.invoice_repo.get_by_external_id(webhook_result.external_id)
        if not invoice:
            logger.warning(
                f"Webhook: invoice not found for external_id={webhook_result.external_id}"
            )
            return {"status": "ignored", "reason": "invoice not found"}

        # 3. Verify webhook authenticity
        wallet = await self.wallet_repo.get_by_type(
            gateway.PROVIDER_NAME, invoice.tenant_id
        )
        if not wallet:
            logger.error(f"Webhook: wallet not found for tenant_id={invoice.tenant_id}")
            raise HTTPException(status_code=500, detail="Wallet not found")
        gateway.verify_webhook(callback_token, wallet)

        # 4. Update invoice status (idempotent — only transitions from PENDING)
        updated = await self.invoice_repo.update_status(
            invoice.id,
            webhook_result.status,
            paid_at=webhook_result.paid_at,
            webhook_payload=webhook_result.raw_payload,
        )

        if not updated:
            logger.info(f"Webhook: invoice {invoice.id} already processed (idempotent)")
            return {"status": "already_processed"}

        # 5. Credit bundle if paid
        if webhook_result.status == InvoiceStatus.PAID:
            await self.bundle_usage_repo.upsert_add_units(
                tenant_id=invoice.tenant_id,
                endpoint_id=invoice.endpoint_id,
                user_email=invoice.user_email,
                unit_type=invoice.unit_type,
                add_units=invoice.tier_units,
            )
            logger.info(
                f"Webhook: credited {invoice.tier_units} {invoice.unit_type} "
                f"to {invoice.user_email} for {invoice.endpoint_id}"
            )
            return {"status": "paid", "units_credited": invoice.tier_units}

        return {"status": webhook_result.status.value}

    # ── Generic: reads ─────────────────────────────────────────────

    async def get_invoices_by_endpoint(
        self, endpoint_slug: str, tenant: Tenant
    ) -> list[InvoiceResponse]:
        """Get all invoices for an endpoint."""
        endpoint = await self.endpoint_repo.get_by_slug(endpoint_slug, tenant.id)
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail=f"Endpoint '{endpoint_slug}' not found",
            )
        invoices = await self.invoice_repo.get_by_endpoint_id(endpoint.id, tenant.id)
        return [InvoiceResponse.model_validate(inv) for inv in invoices]

    async def get_invoice(self, invoice_id: UUID, tenant: Tenant) -> InvoiceResponse:
        """Get an invoice by ID within a tenant."""
        invoice = await self.invoice_repo.get_by_id(invoice_id, tenant.id)
        if not invoice:
            raise HTTPException(
                status_code=404, detail=f"Invoice '{invoice_id}' not found"
            )
        return InvoiceResponse.model_validate(invoice)

    async def get_bundle_usage(
        self,
        endpoint_slug: str,
        user_email: str,
        tenant: Tenant,
        unit_type: str = "requests",
    ) -> BundleUsageResponse:
        """Get bundle balance for a user on an endpoint."""
        endpoint = await self.endpoint_repo.get_by_slug(endpoint_slug, tenant.id)
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail=f"Endpoint '{endpoint_slug}' not found",
            )

        usage = await self.bundle_usage_repo.get_by_user_endpoint(
            user_email, endpoint.id, tenant.id, unit_type
        )

        return BundleUsageResponse(
            endpoint_slug=endpoint_slug,
            user_email=user_email,
            unit_type=unit_type,
            remaining_units=usage.remaining_units if usage else 0,
            total_purchased=usage.total_purchased if usage else 0,
        )

    async def get_all_bundle_usages(
        self, endpoint_slug: str, tenant: Tenant
    ) -> list[BundleUsageResponse]:
        """Get all bundle usages for an endpoint (admin view)."""
        endpoint = await self.endpoint_repo.get_by_slug(endpoint_slug, tenant.id)
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail=f"Endpoint '{endpoint_slug}' not found",
            )
        usages = await self.bundle_usage_repo.get_by_endpoint_id(endpoint.id, tenant.id)
        return [
            BundleUsageResponse(
                endpoint_slug=endpoint_slug,
                user_email=u.user_email,
                unit_type=u.unit_type,
                remaining_units=u.remaining_units,
                total_purchased=u.total_purchased,
            )
            for u in usages
        ]
