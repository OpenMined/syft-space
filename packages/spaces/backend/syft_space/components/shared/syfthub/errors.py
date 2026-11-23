"""Errors raised by the SyftHub client."""

from typing import Any

from fastapi import HTTPException


class SyftHubError(Exception):
    """Base exception for SyftHub API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str | None = None,
        field: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.field = field
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException.

        When the upstream error carries a structured ``code`` (e.g.
        ``EMAIL_NOT_VERIFIED``), surface it as a dict so the frontend can
        branch on it. Otherwise fall back to the historical string detail so
        existing error toasts keep rendering unchanged.
        """
        if self.code is None and self.field is None:
            return HTTPException(status_code=self.status_code, detail=self.message)

        detail: dict[str, Any] = {"message": self.message}
        if self.code is not None:
            detail["code"] = self.code
        if self.field is not None:
            detail["field"] = self.field
        return HTTPException(status_code=self.status_code, detail=detail)


class AuthenticationError(SyftHubError):
    """Invalid credentials or token expired (401)."""

    pass


class ForbiddenError(SyftHubError):
    """Access forbidden (403)."""

    pass


class NotFoundError(SyftHubError):
    """Resource not found (404)."""

    pass


class ConflictError(SyftHubError):
    """Resource already exists (409)."""

    pass


class ValidationError(SyftHubError):
    """Request validation failed (400, 422)."""

    def __init__(
        self,
        message: str,
        status_code: int = 422,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message, status_code=status_code, code=code)
        self.errors = errors or []


class SatelliteKindMismatchError(ConflictError):
    """409 - the origin is registered as the other kind. Needs an operator."""

    pass


class SatelliteOriginConflictError(ConflictError):
    """409 - another satellite on this account already serves that origin."""

    pass


class SatelliteRequiredError(ValidationError):
    """422 - the account runs 2+ spaces and the call named no satellite."""

    def __init__(
        self,
        message: str,
        status_code: int = 422,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        count: int | None = None,
    ):
        super().__init__(message, status_code=status_code, code=code, errors=errors)
        self.count = count


class FailedDependencyError(SyftHubError):
    """Failed dependency - accounting service issue (424)."""

    pass


class RateLimitError(SyftHubError):
    """Rate limited by SyftHub (429) - callers should back off, not retry."""

    pass


class ServerError(SyftHubError):
    """Server-side error (5xx) - covers 500, 502, 503, 504, etc."""

    pass


class NotAuthenticatedError(SyftHubError):
    """Client not authenticated - login() not called."""

    def __init__(self):
        super().__init__("Not authenticated. Call login() first.", status_code=401)
