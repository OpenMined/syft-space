"""Fire-and-forget query event capture service."""

from uuid import UUID

from loguru import logger

from syft_space.components.analytics.entities import QueryEvent
from syft_space.components.analytics.repository import QueryEventRepository


class QueryEventCollector:
    """Captures query events without blocking the query response.

    All exceptions are swallowed and logged — event capture must
    never degrade query latency or cause query failures.
    """

    def __init__(self, repository: QueryEventRepository):
        self.repository = repository

    async def capture(
        self,
        *,
        tenant_id: UUID,
        endpoint_id: UUID | None,
        endpoint_slug: str,
        dataset_id: UUID | None,
        user_email: str,
        revenue_amount: float,
        currency: str,
        status: str,
    ) -> None:
        """Persist a query event record.

        Args:
            tenant_id: Tenant that owns the queried endpoint
            endpoint_id: Endpoint UUID (None if not found)
            endpoint_slug: Human-readable endpoint slug
            dataset_id: Dataset UUID (None if not applicable)
            user_email: Verified email of the querying user
            revenue_amount: Amount charged for this query
            currency: Currency of the revenue amount
            status: Query outcome status (see QueryEventStatus)
        """
        try:
            event = QueryEvent(
                tenant_id=tenant_id,
                endpoint_id=endpoint_id,
                endpoint_slug=endpoint_slug,
                dataset_id=dataset_id,
                user_email=user_email,
                revenue_amount=revenue_amount,
                currency=currency,
                status=status,
            )
            await self.repository.create(event)
        except Exception as e:
            logger.error(f"Failed to capture query event: {e}")
