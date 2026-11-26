"""Turns SyftHub HTTP responses into models or typed errors."""

from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from loguru import logger
from pydantic import BaseModel

from .errors import (
    AuthenticationError,
    ConflictError,
    FailedDependencyError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    SatelliteRequiredError,
    ServerError,
    SyftHubError,
    ValidationError,
)

T = TypeVar("T", bound=BaseModel)


@dataclass
class ParsedError:
    """Parsed error response from SyftHub."""

    message: str
    code: str | None = None
    field: str | None = None
    count: int | None = None


def _parse_error_response(response: httpx.Response) -> ParsedError:
    """Parse SyftHub error response into structured format.

    Handles patterns:
    1. {"detail": {"code/error": "...", "message": "...", ...}} - Structured
    2. {"detail": "string"} - Simple string
    3. {"detail": [...]} - Validation errors
    """
    try:
        data = response.json()
    except Exception:
        return ParsedError(
            message=response.reason_phrase or f"HTTP {response.status_code}"
        )

    detail = data.get("detail") if isinstance(data, dict) else None

    # Pattern 1: Structured dict
    if isinstance(detail, dict):
        count = detail.get("count")
        return ParsedError(
            message=detail.get("message", str(detail)),
            code=detail.get("code") or detail.get("error"),  # Handle both formats
            field=detail.get("field"),
            count=count if isinstance(count, int) else None,
        )

    # Pattern 2: Simple string
    if isinstance(detail, str):
        return ParsedError(message=detail)

    # Pattern 3: Validation errors array (FastAPI/pydantic shape). Keep the
    # field name so a publisher learns *which* value was rejected.
    if isinstance(detail, list):
        return ParsedError(
            message="; ".join(_describe_validation_error(e) for e in detail)
        )

    return ParsedError(
        message=response.text[:200] if response.text else response.reason_phrase or ""
    )


def _describe_validation_error(err: Any) -> str:
    """``{"loc": ["body", "description"], "msg": "..."}`` -> ``description: ...``."""
    if not isinstance(err, dict):
        return str(err)
    msg = err.get("msg", str(err))
    loc = [
        str(part)
        for part in err.get("loc", ())
        if part not in ("body", "query", "path")
    ]
    return f"{'.'.join(loc)}: {msg}" if loc else msg


def _extract_validation_errors(response: httpx.Response) -> list[dict[str, Any]]:
    """Extract validation error details from response."""
    try:
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("detail"), list):
            return data["detail"]
    except Exception as e:
        logger.exception(f"Error extracting validation errors: {e}")
    return []


def _raise_for_status(response: httpx.Response) -> None:
    """Raise appropriate exception based on response status code."""
    parsed = _parse_error_response(response)
    status = response.status_code

    # Ties a failure here to the hub-side request that produced it.
    correlation_id = response.headers.get("X-Correlation-ID")
    if correlation_id:
        logger.warning(
            f"SyftHub error {status} on {response.request.method} "
            f"{response.request.url.path} "
            f"(code={parsed.code}, correlation_id={correlation_id})"
        )

    if status == 400:
        raise ValidationError(parsed.message, status_code=status, code=parsed.code)
    elif status == 401:
        raise AuthenticationError(parsed.message, status_code=status, code=parsed.code)
    elif status == 403:
        raise ForbiddenError(parsed.message, status_code=status, code=parsed.code)
    elif status == 404:
        raise NotFoundError(parsed.message, status_code=status, code=parsed.code)
    elif status == 409:
        raise ConflictError(
            parsed.message, status_code=status, code=parsed.code, field=parsed.field
        )
    elif status == 422:
        errors = _extract_validation_errors(response)
        if parsed.count is not None:
            # `count` is carried only by the ambiguous-satellite error.
            raise SatelliteRequiredError(
                parsed.message,
                status_code=status,
                code=parsed.code,
                errors=errors,
                count=parsed.count,
            )
        raise ValidationError(
            parsed.message, status_code=status, code=parsed.code, errors=errors
        )
    elif status == 424:
        raise FailedDependencyError(
            parsed.message, status_code=status, code=parsed.code
        )
    elif status == 429:
        raise RateLimitError(parsed.message, status_code=status, code=parsed.code)
    elif status >= 500:
        raise ServerError(parsed.message, status_code=status, code=parsed.code)
    else:
        raise SyftHubError(parsed.message, status_code=status, code=parsed.code)


def _handle_response(response: httpx.Response, model: type[T]) -> T:
    """Handle API response: parse success or raise appropriate exception."""
    if response.is_success:
        try:
            return model.model_validate(response.json())
        except ValueError as exc:
            # A 2xx with a body this client cannot read - a proxy error page,
            # a truncated response - is a hub failure, not a success.
            raise ServerError(f"Unreadable response from SyftHub: {exc}") from exc

    _raise_for_status(response)
    # This line is never reached but helps type checker
    raise AssertionError("Unreachable")


def _handle_response_raw(response: httpx.Response) -> dict[str, Any]:
    """Handle API response returning raw dict (for dynamic responses)."""
    if response.is_success:
        try:
            return response.json()
        except ValueError as exc:
            raise ServerError(f"Unreadable response from SyftHub: {exc}") from exc

    _raise_for_status(response)
    # This line is never reached but helps type checker
    raise AssertionError("Unreachable")
