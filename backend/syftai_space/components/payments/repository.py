"""PaymentService repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select

from syftai_space.components.payments.entities import PaymentService
from syftai_space.components.shared.database import BaseRepository, Database


class PaymentServiceRepository(BaseRepository[PaymentService]):
    """Repository for PaymentService CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the payment service repository.

        Args:
            db: Database instance
        """
        super().__init__(db, PaymentService)

    def get_by_tenant(self, tenant_id: UUID) -> PaymentService | None:
        """Get payment service by tenant ID.

        Args:
            tenant_id: Tenant ID

        Returns:
            PaymentService if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(PaymentService).where(
                PaymentService.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def create(
        self,
        tenant_id: UUID,
        *,
        url: str = "",
        email: str = "",
        password: str = "",
    ) -> PaymentService:
        """Create a payment service for a tenant.

        Args:
            tenant_id: Tenant ID
            url: Payment service URL
            email: Payment service email
            password: Payment service password

        Returns:
            Created payment service
        """
        with self.db.get_session() as session:
            payment_service = PaymentService(
                tenant_id=tenant_id,
                url=url,
                email=email,
                password=password,
            )
            session.add(payment_service)
            session.commit()
            session.refresh(payment_service)
            return payment_service

    def update(
        self,
        tenant_id: UUID,
        *,
        url: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> PaymentService | None:
        """Update payment service for a tenant.

        Args:
            tenant_id: Tenant ID
            url: Payment service URL
            email: Payment service email
            password: Payment service password

        Returns:
            Updated payment service if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(PaymentService).where(
                PaymentService.tenant_id == tenant_id
            )
            payment_service = session.exec(statement).first()

            if not payment_service:
                return None

            # Update fields if provided
            if url is not None:
                payment_service.url = url
            if email is not None:
                payment_service.email = email
            if password is not None:
                payment_service.password = password

            payment_service.updated_at = datetime.now(timezone.utc)

            session.add(payment_service)
            session.commit()
            session.refresh(payment_service)
            return payment_service
