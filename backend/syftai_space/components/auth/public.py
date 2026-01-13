"""Public route decorator and discovery for routes that skip admin auth."""

import re
from collections.abc import Callable
from typing import TypeVar

from loguru import logger
from starlette.routing import Mount, Route

F = TypeVar("F", bound=Callable)
PUBLIC_ROUTE_MARKER = "public_route"

# Module-level storage (populated by discover_public_routes)
_public_patterns: list[tuple[str, re.Pattern]] = []


def public_route(func: F) -> F:
    """Decorator to mark a route as public (no admin auth required).

    Usage:
        @public_route
        @router.post("/{slug}/query")
        async def query_endpoint(...):
            ...
    """
    setattr(func, PUBLIC_ROUTE_MARKER, True)
    return func


def discover_public_routes(app) -> None:
    """Scan app routes and register those marked with @public_route.

    Call this after all routes are registered.
    """
    _public_patterns.clear()
    _scan_routes(app.routes, "")
    logger.info(f"Discovered {len(_public_patterns)} public routes")


def is_public_route(path: str, method: str) -> bool:
    """Check if path+method is a public route."""
    return any(m == method and p.match(path) for m, p in _public_patterns)


def _scan_routes(routes, prefix: str) -> None:
    """Recursively scan routes for @public_route marker."""
    for route in routes:
        if isinstance(route, Mount):
            _scan_routes(route.routes, prefix + route.path)
        elif isinstance(route, Route):
            endpoint = getattr(route, "endpoint", None)
            if endpoint and getattr(endpoint, PUBLIC_ROUTE_MARKER, False):
                full_path = prefix + route.path
                pattern = re.compile(
                    "^" + re.sub(r"\{[^}]+\}", r"[^/]+", full_path) + "$"
                )
                for method in route.methods or {"GET"}:
                    _public_patterns.append((method, pattern))
