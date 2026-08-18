"""Source-layer exceptions.

Raised by browsers/sources when a connect/browse attempt fails in a way the
picker should report distinctly. Each carries the HTTP status the API
boundary should return; ``to_http_exception`` does the conversion (same
pattern as ``XenditError``). Non-HTTP callers (e.g. the ingestion poll loop)
just catch ``SourceError`` like any other exception and never touch the HTTP
side.
"""

from fastapi import HTTPException


class SourceError(Exception):
    """Base for source browse/connect failures. Defaults to HTTP 400."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        """Convert to the HTTPException the API boundary should return."""
        return HTTPException(status_code=self.status_code, detail=self.message)


class SourceAuthError(SourceError):
    """Credentials rejected by the source (HTTP 401)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=401)


class SourceForbiddenError(SourceError):
    """Authenticated, but the source forbids the request (HTTP 403).

    Covers an account lacking the required capability and a WAF /
    User-Agent block.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)
