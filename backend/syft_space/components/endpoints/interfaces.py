"""Endpoint component interfaces (Dependency Inversion boundaries)."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from syft_space.components.endpoints.schemas import (
        ChatMessageRequest,
        QueryEndpointResponse,
    )

# Deletion check callback — wired in main.py, keeps payment imports out of endpoints.
# Returns an error message string if deletion is blocked, None if deletable.
DeletionCheck = Callable[[UUID, UUID], Coroutine[Any, Any, str | None]]

# Metadata enricher — called before policy hooks to inject cross-component
# services (e.g., balance_service) into the policy context metadata dict.
# Keeps payment imports out of the query handler.
MetadataEnricher = Callable[[dict], Coroutine[Any, Any, None]]


class QueryOutcome(str, Enum):
    """Outcome of a query as observed by the endpoints component.

    Domain enum owned by `endpoints` — distinct from analytics' wire-level
    QueryEventStatus, even though the values currently align. The analytics
    adapter translates from this to its own status code.
    """

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    NOT_PUBLISHED = "not_published"
    PAYMENT_REQUIRED = "payment_required"
    POLICY_VIOLATION = "policy_violation"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class QueryOutcomeEvent:
    """Domain event describing the outcome of one query.

    Self-describing: carries only the IDs the adapter needs, never a live
    ORM instance. Translation into an analytics row (status mapping,
    query-text extraction, cost-line derivation from response) is the
    adapter's job.
    """

    tenant_id: UUID
    user_email: str
    endpoint_slug: str
    endpoint_id: UUID | None
    dataset_id: UUID | None
    outcome: QueryOutcome
    messages: "str | list[ChatMessageRequest]"
    response: "QueryEndpointResponse | None"


# Reporter callable — wired in main.py to the analytics adapter.
# Keeps analytics imports out of endpoints.
QueryEventReporter = Callable[[QueryOutcomeEvent], Coroutine[Any, Any, None]]
