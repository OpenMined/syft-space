"""Admin API key authentication middleware."""

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from syftai_space.components.auth.public import PUBLIC_ROUTE_MARKER


class AdminKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce admin API key on protected routes.

    Routes marked with @public_route decorator skip authentication.
    Static paths (docs, frontend) are also allowed without auth.

    All other routes require Authorization: Bearer <key> header.
    """

    # Static paths that don't have route handlers (can't use decorator)
    STATIC_PUBLIC_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/syftai-server",  # Frontend static files
    ]

    STATIC_PUBLIC_EXACT = ["/"]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        path = request.url.path

        # Check if route is marked as public via @public_route decorator
        endpoint = request.scope.get("endpoint")
        if endpoint and getattr(endpoint, PUBLIC_ROUTE_MARKER, False):
            return await call_next(request)

        # Allow static public paths (docs, frontend, etc.)
        if self._is_static_public_path(path):
            return await call_next(request)

        # All other routes require admin key
        if not self._verify_admin_key(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "Admin API key required"},
            )

        return await call_next(request)

    def _is_static_public_path(self, path: str) -> bool:
        """Check static paths that can't use decorators."""
        if path in self.STATIC_PUBLIC_EXACT:
            return True
        return any(path.startswith(prefix) for prefix in self.STATIC_PUBLIC_PATHS)

    def _verify_admin_key(self, request: Request) -> bool:
        """Verify the admin API key from Authorization header."""
        from syftai_space.config import app_settings

        # If no admin key configured, allow all (dev mode)
        if not app_settings.admin_api_key:
            return True

        # Check Authorization: Bearer <token> header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:]  # Strip "Bearer " prefix
            return provided_key == app_settings.admin_api_key

        return False
