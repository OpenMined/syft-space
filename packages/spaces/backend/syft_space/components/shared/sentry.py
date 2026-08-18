"""Sentry error tracking integration."""

from __future__ import annotations

from typing import Any

import sentry_sdk
from loguru import logger

_diagnostics_enabled = False

SENTRY_DSN = "https://f1ea0d6562d843ef81c3a41d08984b46@o4511056487317504.ingest.us.sentry.io/4511056496033792"


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    if not _diagnostics_enabled:
        return None
    return event


def _before_send_transaction(
    event: dict[str, Any], hint: dict[str, Any]
) -> dict[str, Any] | None:
    if not _diagnostics_enabled:
        return None
    return event


def init_sentry(*, debug: bool = False) -> None:
    """Initialize Sentry SDK for error tracking.

    Events are only sent when diagnostics is enabled by the user.
    """
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
            environment="development" if debug else "production",
            release="syft-space-backend@0.1.0",
        )
        logger.info("Sentry SDK initialized (events gated by diagnostics setting)")
    except Exception as e:
        logger.warning(f"Failed to initialize Sentry: {e}")


def set_diagnostics_enabled(enabled: bool) -> None:
    """Update the diagnostics flag for Sentry event gating."""
    global _diagnostics_enabled
    _diagnostics_enabled = enabled
