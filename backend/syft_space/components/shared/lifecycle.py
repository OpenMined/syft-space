"""Lifecycle service protocol for startup/shutdown management."""

from typing import Protocol


class LifecycleService(Protocol):
    """Protocol for services with startup/shutdown lifecycle.

    Services implementing this protocol can be managed by the application
    lifespan, ensuring consistent startup and shutdown ordering.
    """

    async def startup(self) -> None:
        """Called during application startup."""
        ...

    async def shutdown(self) -> None:
        """Called during application shutdown."""
        ...
