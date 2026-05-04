"""Invoice repository for database operations.

Session-bound: every method runs against the session passed at construction
time. Repos do not commit; the owning PaymentLedger commits or rolls back.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from syft_space.components.payments.gateway.entities import Invoice, InvoiceStatus


class InvoiceRepository:
    """Repository for Invoice CRUD."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, invoice: Invoice) -> Invoice:
        """Stage a new invoice on the session. PaymentLedger commits."""
        self.session.add(invoice)
        return invoice

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Invoice | None:
        """Get an invoice by ID within a tenant."""
        statement = select(Invoice).where(
            Invoice.id == id, Invoice.tenant_id == tenant_id
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_external_id(self, external_id: str) -> Invoice | None:
        """Get an invoice by external provider ID.

        No tenant filter — webhooks don't know the tenant.
        """
        statement = select(Invoice).where(Invoice.external_id == external_id)
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_wallet_id(self, wallet_id: UUID, tenant_id: UUID) -> list[Invoice]:
        """Get all invoices for a wallet."""
        statement = (
            select(Invoice)
            .where(
                Invoice.wallet_id == wallet_id,
                Invoice.tenant_id == tenant_id,
            )
            .order_by(Invoice.created_at.desc())
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def list_for_tenant(
        self, tenant_id: UUID, status: str | None = None
    ) -> list[Invoice]:
        """Admin view: all invoices for a tenant, newest first.

        Optional status filter (pending|paid|expired|failed). No pagination —
        invoice volume is low (a few per user per month).
        """
        statement = select(Invoice).where(Invoice.tenant_id == tenant_id)
        if status:
            statement = statement.where(Invoice.status == status)
        statement = statement.order_by(Invoice.created_at.desc())
        result = await self.session.exec(statement)
        return list(result.all())

    async def list_for_user_in_wallet(
        self,
        wallet_id: UUID,
        tenant_id: UUID,
        user_email: str,
        status: str | None = None,
    ) -> list[Invoice]:
        """Caller's own invoices for a wallet, newest first.

        Used by the satellite-token /invoices/me endpoint so callers can check
        whether a pending invoice already exists before creating a new one.
        Optional status filter (pending|paid|expired|failed).
        """
        statement = select(Invoice).where(
            Invoice.wallet_id == wallet_id,
            Invoice.tenant_id == tenant_id,
            Invoice.user_email == user_email,
        )
        if status:
            statement = statement.where(Invoice.status == status)
        statement = statement.order_by(Invoice.created_at.desc())
        result = await self.session.exec(statement)
        return list(result.all())

    async def has_pending_by_wallet_id(self, wallet_id: UUID, tenant_id: UUID) -> bool:
        """Check if any pending invoices exist for a wallet."""
        statement = select(Invoice).where(
            Invoice.wallet_id == wallet_id,
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.PENDING.value,
        )
        result = await self.session.exec(statement)
        return result.first() is not None

    async def set_checkout_url(self, id: UUID, checkout_url: str) -> bool:
        """Set checkout_url on a still-pending invoice.

        Used to patch the URL in after the provider returns it, when the
        invoice was inserted PENDING with an empty placeholder. Guarded by
        WHERE status='pending' so a concurrent webhook can't be clobbered.
        Returns False if no row was updated (already terminal).
        """
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == id,
                Invoice.status == InvoiceStatus.PENDING.value,
            )
            .values(
                checkout_url=checkout_url,
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0

    async def mark_paid(
        self,
        id: UUID,
        paid_at: datetime,
        webhook_payload: dict,
    ) -> bool:
        """Atomically transition PENDING → PAID. No-op (returns False) otherwise.

        Idempotent via the WHERE status='pending' guard: replayed webhooks
        find the invoice already paid and the row count is 0.
        """
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == id,
                Invoice.status == InvoiceStatus.PENDING.value,
            )
            .values(
                status=InvoiceStatus.PAID.value,
                paid_at=paid_at,
                webhook_payload=webhook_payload,
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0

    async def update_status(
        self,
        id: UUID,
        status: InvoiceStatus,
        paid_at: datetime | None = None,
        webhook_payload: dict | None = None,
    ) -> bool:
        """Transition PENDING → terminal status (EXPIRED/FAILED).

        For PAID, prefer mark_paid() — it carries the paid_at + payload contract
        explicitly. This method handles non-PAID terminal states.
        """
        statement = select(Invoice).where(
            Invoice.id == id,
            Invoice.status == InvoiceStatus.PENDING.value,
        )
        result = await self.session.exec(statement)
        invoice = result.first()
        if not invoice:
            return False

        invoice.status = status.value
        invoice.updated_at = datetime.now(timezone.utc)
        if paid_at:
            invoice.paid_at = paid_at
        if webhook_payload:
            invoice.webhook_payload = webhook_payload

        self.session.add(invoice)
        return True
