"""Public route decorator for marking routes that don't require authentication."""

from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)

PUBLIC_ROUTE_MARKER = "public_route"


def public_route(func: F) -> F:
    """Decorator to mark a route as public (no auth required).

    Usage:
        @public_route
        @router.post("/{slug}/query")
        async def query_endpoint(...):
            ...

    The middleware checks for this marker via:
        getattr(endpoint, PUBLIC_ROUTE_MARKER, False)
    """
    setattr(func, PUBLIC_ROUTE_MARKER, True)
    return func
