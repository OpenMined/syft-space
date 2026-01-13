"""Admin API key authentication middleware."""

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from syftai_space.components.auth.public import is_public_route


class AdminKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce admin API key on protected routes.

    Routes marked with @public_route decorator skip authentication.
    Static paths (docs, frontend) are also allowed without auth.

    All other routes require Authorization: Bearer <key> header.
    """

    STATIC_PUBLIC_PATHS = ["/docs", "/redoc", "/openapi.json", "/syftai-server"]
    STATIC_PUBLIC_EXACT = ["/"]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        path = request.url.path
        method = request.method

        # Allow static paths (docs, frontend)
        if self._is_static_public_path(path):
            return await call_next(request)

        # Allow public API routes (discovered from @public_route decorator)
        if is_public_route(path, method):
            return await call_next(request)

        # Require admin key for all other routes
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
        return any(path.startswith(p) for p in self.STATIC_PUBLIC_PATHS)

    def _verify_admin_key(self, request: Request) -> bool:
        """Verify the admin API key from Authorization header."""
        from syftai_space.config import app_settings

        if not app_settings.admin_api_key:
            return True

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:] == app_settings.admin_api_key

        return False
