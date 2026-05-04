"""Endpoint component interfaces (Dependency Inversion boundaries)."""

from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

# Deletion check callback — wired in main.py, keeps payment imports out of endpoints.
# Returns an error message string if deletion is blocked, None if deletable.
DeletionCheck = Callable[[UUID, UUID], Coroutine[Any, Any, str | None]]

# Metadata enricher — called before policy hooks to inject cross-component
# services (e.g., balance_service) into the policy context metadata dict.
# Keeps payment imports out of the query handler.
MetadataEnricher = Callable[[dict], Coroutine[Any, Any, None]]
