"""Provider refusals: the error types, how a refusal is classified, how long a
busy one is waited out."""

from __future__ import annotations

import json
import random
import time
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


class LLMError(RuntimeError):
    """The LLM did not answer, or answered with unparseable text."""


class LLMFatalError(LLMError):
    """A refusal a retry does not cure: the key, access, the model name, credits.

    Retrying one would only pay for every pointless attempt: on an external
    provider with a 900-second timeout a wrong key would cost forty-five
    minutes of waiting instead of an instant hint about what to check.
    """

    # The HTTP status (or the body's error code) it came with; 0 — none.
    status: int = 0


class LLMTruncatedError(LLMError):
    """The answer hit the token cap and brought back nothing usable."""


class LLMBusyError(LLMError):
    """A rate limit or an overload: the same call later is likely to pass."""

    def __init__(self, detail: str, retry_after: float | None = None) -> None:
        super().__init__(detail)
        self.retry_after = retry_after


# The codes with nothing to retry: it is the request, the key or the money.
_FATAL_STATUS = frozenset({400, 401, 402, 403, 404, 405, 422})

# Signs of a spent balance in the response body. OpenRouter hands them back
# both with HTTP 200 and with 402 — as text, not as a code.
_FATAL_BODY = (
    "insufficient credits",
    "insufficient_quota",
    "access denied by security policy",
    "no endpoints found",
    "not a valid model id",
)

# Replies that mean "busy, come back later": a rate limit or an overload.
_BUSY_STATUS = frozenset({429, 500, 502, 503, 504, 529})

# How many busy replies one call waits out, apart from ``retries``, and the
# waits: exponential from the base, with jitter, never past the cap. A
# Retry-After from the provider is honoured up to its own cap.
BUSY_RETRIES = 5
_BACKOFF_BASE = 2.0
_BACKOFF_CAP = 60.0
_RETRY_AFTER_CAP = 120.0

# The longest refusal kept in an error: room for the provider's own message.
DETAIL_CAP = 800


def classify(status: int, detail: str, retry_after: float | None = None) -> LLMError:
    """A provider's refusal — fatal, busy, or worth retrying."""
    lowered = detail.lower()
    if status in _FATAL_STATUS or any(mark in lowered for mark in _FATAL_BODY):
        fatal = LLMFatalError(detail)
        fatal.status = status
        return fatal
    if status in _BUSY_STATUS:
        return LLMBusyError(detail, retry_after)
    return LLMError(detail)


def _raw_messages(raw: Any) -> list[str]:
    """The messages in a provider's raw reply, parsed when it is JSON."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return [raw]
    if not isinstance(raw, dict):
        return []
    inner = raw.get("error")
    if isinstance(inner, dict):
        return _error_messages(inner)
    message = inner if isinstance(inner, str) else raw.get("message")
    return [str(message)] if message else []


def _error_messages(error: dict[str, Any]) -> list[str]:
    """An error's message, then those of the provider errors nested in it.

    OpenRouter wraps the provider's refusal: the top message is generic, the
    reason sits in ``metadata.previous_errors[].raw`` or ``metadata.raw``.
    """
    found = [str(error["message"])] if error.get("message") else []
    metadata = error.get("metadata")
    if not isinstance(metadata, dict):
        return found
    for previous in metadata.get("previous_errors") or []:
        if not isinstance(previous, dict):
            continue
        inner = _raw_messages(previous.get("raw")) or _error_messages(previous)
        name = previous.get("provider_name")
        found.extend(f"{name}: {text}" if name else text for text in inner)
    found.extend(_raw_messages(metadata.get("raw")))
    return found


def error_detail(body: Any, fallback: str) -> str:
    """A refusal's text: the provider's messages, or ``fallback`` without any."""
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        messages = _error_messages(error)
    else:
        messages = [error] if isinstance(error, str) else []
    unique = dict.fromkeys(text.strip() for text in messages if text.strip())
    detail = " | ".join(unique) or fallback.strip()
    if len(detail) > DETAIL_CAP:
        detail = detail[: DETAIL_CAP - 3] + "..."
    return detail


def retry_after_of(headers: httpx.Headers | dict[str, str] | None) -> float | None:
    """The Retry-After header in seconds (a number or an HTTP date); None — absent."""
    if not headers:
        return None
    raw = str(headers.get("retry-after") or headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def backoff_delay(attempt: int, retry_after: float | None = None) -> float:
    """Seconds to wait before busy retry number ``attempt`` (from 1)."""
    ceiling = min(_BACKOFF_CAP, _BACKOFF_BASE * 2 ** (attempt - 1))
    delay = random.uniform(ceiling / 2, ceiling)  # noqa: S311 - jitter, not crypto
    if retry_after is not None:
        delay = max(delay, min(retry_after, _RETRY_AFTER_CAP))
    return delay
