"""Invoice repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select

from syft_space.components.payments.entities import Invoice, InvoiceStatus
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class InvoiceRepository(AsyncBaseRepository[Invoice]):
    """Repository for Invoice CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Invoice)

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Invoice | None:
        """Get an invoice by ID within a tenant."""
        async with self.db.get_session() as session:
            statement = select(Invoice).where(
                Invoice.id == id, Invoice.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_external_id(self, external_id: str) -> Invoice | None:
        """Get an invoice by external provider ID.

        No tenant filter — webhooks don't know the tenant.
        """
        async with self.db.get_session() as session:
            statement = select(Invoice).where(Invoice.external_id == external_id)
            result = await session.exec(statement)
            return result.first()

    async def update_status(
        self,
        id: UUID,
        status: InvoiceStatus,
        paid_at: datetime | None = None,
        webhook_payload: dict | None = None,
    ) -> bool:
        """Update invoice status. Idempotent — only transitions from PENDING.

        Returns True if the update was applied, False if already transitioned.
        """
        async with self.db.get_session() as session:
            statement = select(Invoice).where(
                Invoice.id == id,
                Invoice.status == InvoiceStatus.PENDING.value,
            )
            result = await session.exec(statement)
            invoice = result.first()
            if not invoice:
                return False

            invoice.status = status.value
            invoice.updated_at = datetime.now(timezone.utc)
            if paid_at:
                invoice.paid_at = paid_at
            if webhook_payload:
                invoice.webhook_payload = webhook_payload

            session.add(invoice)
            await session.commit()
            return True

    async def get_by_endpoint_id(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> list[Invoice]:
        """Get all invoices for an endpoint."""
        async with self.db.get_session() as session:
            statement = (
                select(Invoice)
                .where(
                    Invoice.endpoint_id == endpoint_id,
                    Invoice.tenant_id == tenant_id,
                )
                .order_by(Invoice.created_at.desc())
            )
            result = await session.exec(statement)
            return list(result.all())

    async def has_pending_by_endpoint_id(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> bool:
        """Check if any pending invoices exist for an endpoint."""
        async with self.db.get_session() as session:
            statement = select(Invoice).where(
                Invoice.endpoint_id == endpoint_id,
                Invoice.tenant_id == tenant_id,
                Invoice.status == InvoiceStatus.PENDING.value,
            )
            result = await session.exec(statement)
            return result.first() is not None
