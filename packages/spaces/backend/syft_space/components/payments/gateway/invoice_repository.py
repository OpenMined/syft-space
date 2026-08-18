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
from syft_space.components.shared.database import AsyncBaseRepository


class InvoiceRepository(AsyncBaseRepository[Invoice]):
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

    async def get_by_client_reference(self, client_reference: str) -> Invoice | None:
        """Look up an invoice by the ``syft-{uuid}`` reference we sent to
        the provider (and which they echo back in webhooks).

        No tenant filter — webhooks don't carry tenant context, and the
        reference is globally unique so it identifies the row on its own.
        """
        statement = select(Invoice).where(Invoice.client_reference == client_reference)
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

        Optional status filter (pending|paid|expired|cancelled). No pagination —
        invoice volume is low (a few per user per month).

        TODO: paginate when any tenant exceeds ~5k invoices. Likely wants
        date-range filters too rather than just cursor (admin reporting use
        cases want "last 30 days," not "next 50 rows"). Defer until concrete
        scale or product requirement.
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
        Optional status filter (pending|paid|expired|cancelled).
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

    # Source statuses from which a webhook may transition. PROCESSING is
    # exclusively for providers that support delayed payment methods (Stripe
    # bank transfers): the session is `complete` but settlement is in flight,
    # and a follow-up async event flips status to PAID. Allowing PROCESSING
    # as a source for both mark_paid and update_status lets the same
    # idempotency guard cover the second-hop transition.
    _TRANSITIONABLE = (InvoiceStatus.PENDING.value, InvoiceStatus.PROCESSING.value)

    async def set_checkout_metadata(
        self,
        id: UUID,
        *,
        checkout_url: str,
        provider_session_id: str | None = None,
    ) -> bool:
        """Patch checkout_url and provider_session_id on a still-pending invoice.

        Both fields are written together after the provider returns. Guarded
        by WHERE status='pending' so a concurrent webhook can't be clobbered.
        Returns False if no row was updated (already terminal).
        """
        values: dict = {
            "checkout_url": checkout_url,
            "updated_at": datetime.now(timezone.utc),
        }
        if provider_session_id is not None:
            values["provider_session_id"] = provider_session_id
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == id,
                Invoice.status == InvoiceStatus.PENDING.value,
            )
            .values(**values)
        )
        result = await self.session.exec(stmt)
        return result.rowcount > 0

    async def mark_paid(
        self,
        id: UUID,
        paid_at: datetime,
        webhook_payload: dict,
    ) -> bool:
        """Atomically transition PENDING|PROCESSING → PAID.

        Idempotent via the source-status guard: replayed webhooks find the
        invoice already PAID and the rowcount is 0. PROCESSING is included
        for providers with delayed-settlement events (Stripe ACH).
        """
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == id,
                Invoice.status.in_(self._TRANSITIONABLE),
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
        """Transition PENDING|PROCESSING → non-PAID status.

        For PAID, prefer mark_paid() — it carries the paid_at + payload
        contract explicitly. This method handles non-PAID transitions
        (PROCESSING, EXPIRED, CANCELLED).

        Allowing PROCESSING as a source covers the Stripe case where a
        delayed payment ultimately fails (PROCESSING → CANCELLED) after
        first having moved out of PENDING.
        """
        statement = select(Invoice).where(
            Invoice.id == id,
            Invoice.status.in_(self._TRANSITIONABLE),
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
