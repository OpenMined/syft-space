"""Fire-and-forget query event capture service."""

from collections.abc import Sequence
from uuid import UUID

from loguru import logger

from syft_space.components.analytics.entities import QueryCostLine, QueryEvent
from syft_space.components.analytics.repository import QueryEventRepository


class QueryEventCollector:
    """Captures query events and their cost lines without blocking the
    query response.

    All exceptions are swallowed and logged — event capture must never
    degrade query latency or cause query failures.
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
        status: str,
        query_text: str = "",
        cost_lines: Sequence[tuple[str, float, str]] = (),
    ) -> None:
        """Persist a query event row plus one row per chargeable component.

        Args:
            tenant_id: Tenant that owns the queried endpoint
            endpoint_id: Endpoint UUID (None if not found)
            endpoint_slug: Human-readable endpoint slug
            dataset_id: Dataset UUID (None if not applicable)
            user_email: Verified email of the querying user
            status: Query outcome status (see QueryEventStatus)
            query_text: Raw query text submitted by the user
            cost_lines: Tuples of (component, amount, currency) — one per
                charged response component (e.g. "summary" / "references").
        """
        try:
            event = QueryEvent(
                tenant_id=tenant_id,
                endpoint_id=endpoint_id,
                endpoint_slug=endpoint_slug,
                dataset_id=dataset_id,
                user_email=user_email,
                status=status,
                query_text=query_text,
            )
            lines = [
                QueryCostLine(
                    query_event_id=event.id,
                    tenant_id=tenant_id,
                    timestamp=event.timestamp,
                    user_email=user_email,
                    endpoint_id=endpoint_id,
                    dataset_id=dataset_id,
                    status=status,
                    component=component,
                    amount=amount,
                    currency=currency,
                )
                for component, amount, currency in cost_lines
            ]
            await self.repository.create_with_lines(event, lines)
        except Exception as e:
            logger.error(f"Failed to capture query event: {e}")
