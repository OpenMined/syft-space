"""OpenTelemetry tracing.

Off unless an OTLP endpoint is set in the environment. With it unset, every
span made here is a no-op and nothing is sent anywhere.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from loguru import logger
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter
    from sqlalchemy.ext.asyncio import AsyncEngine

# --- Tunables ---

# Either of these turns tracing on; the exporter reads them itself.
ENDPOINT_ENV_VARS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
)

# Service name shown in the viewer when OTEL_SERVICE_NAME is not set.
DEFAULT_SERVICE_NAME = "syft-station"

# Requests not traced: the health probe and the static UI.
EXCLUDED_URLS = "/healthz$,/ui$,/ui/"

# Attribute names. The id is the space's row id in the station database.
SPACE_ID_ATTR = "syft.space.id"
SPACE_SUBDOMAIN_ATTR = "syft.space.subdomain"

# Span attributes that hold a URL, its path or its query string.
URL_ATTRS = ("http.url", "url.full", "http.target", "url.query")

TRACER_NAME = "syft_station"

# A no-op tracer until setup_telemetry replaces it.
_tracer = trace.get_tracer(TRACER_NAME)
_provider: TracerProvider | None = None
_app: FastAPI | None = None

# Attributes for every span started in the current request.
_request_attributes: ContextVar[dict[str, Any] | None] = ContextVar(
    "telemetry_request_attributes", default=None
)


def telemetry_enabled() -> bool:
    """Whether an OTLP endpoint is configured."""
    return any(os.environ.get(name) for name in ENDPOINT_ENV_VARS)


def setup_telemetry(
    app: FastAPI,
    engines: list[AsyncEngine],
    exporter: SpanExporter | None = None,
) -> None:
    """Start tracing for the app, outbound httpx calls and the given engines.

    Does nothing when no OTLP endpoint is configured. Call once, after the
    app's middleware is added and before it serves a request. `exporter`
    replaces the OTLP exporter and turns tracing on by itself; tests use it.
    """
    global _provider, _tracer, _app
    if _provider is not None or not (exporter or telemetry_enabled()):
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        class _RequestAttributes(SpanProcessor):
            """Copies the request's attributes onto each span as it starts."""

            def on_start(self, span: Any, parent_context: Any = None) -> None:
                span.set_attributes(_request_attributes.get() or {})

        if exporter is None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter()

        service_name = os.environ.get("OTEL_SERVICE_NAME") or DEFAULT_SERVICE_NAME
        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        provider.add_span_processor(_RequestAttributes())
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # The provider is passed around, not installed globally, so nothing
        # outside this module starts tracing as a side effect.
        # One span per request; the per-message send/receive spans are noise.
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls=EXCLUDED_URLS,
            exclude_spans=["send", "receive"],
            server_request_hook=_drop_query_string,
        )
        HTTPXClientInstrumentor().instrument(
            tracer_provider=provider,
            request_hook=_drop_query_string,
            async_request_hook=_drop_query_string_async,
        )
        SQLAlchemyInstrumentor().instrument(
            engines=[engine.sync_engine for engine in engines],
            tracer_provider=provider,
        )
        _provider, _app = provider, app
        _tracer = provider.get_tracer(TRACER_NAME)
        logger.info(f"Telemetry on: tracing as '{service_name}'")
    except Exception as e:
        # Tracing must never stop the app from starting.
        logger.warning(f"Failed to set up telemetry: {e}")


def _drop_query_string(span: Any, _request: Any) -> None:
    """Cut the query string from a request span's URL attributes.

    Query strings carry emails here (``/credits/balance?user_email=``).
    """
    attributes = getattr(span, "attributes", None) or {}
    for key in URL_ATTRS:
        value = attributes.get(key)
        if isinstance(value, str) and (key == "url.query" or "?" in value):
            span.set_attribute(key, "" if key == "url.query" else value.split("?")[0])


async def _drop_query_string_async(span: Any, request: Any) -> None:
    _drop_query_string(span, request)


def flush_telemetry() -> None:
    """Send buffered spans now. Safe to call when tracing is off."""
    if _provider is not None:
        _provider.force_flush()


def shutdown_telemetry() -> None:
    """Send buffered spans and stop tracing. Safe to call when tracing is off."""
    global _provider, _tracer, _app
    if _provider is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        if _app is not None:
            FastAPIInstrumentor.uninstrument_app(_app)
        HTTPXClientInstrumentor().uninstrument()
        SQLAlchemyInstrumentor().uninstrument()
        _provider.shutdown()
    except Exception as e:
        logger.warning(f"Failed to shut down telemetry: {e}")
    _provider, _app = None, None
    _tracer = trace.get_tracer(TRACER_NAME)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """Time a block as a span. Attributes with a None value are left out.

    On an exception the span is marked failed with the exception's class name
    only: messages can carry emails or tokens, so they are not recorded.
    """
    kept = {key: value for key, value in attributes.items() if value is not None}
    with _tracer.start_as_current_span(
        name,
        attributes=kept,
        record_exception=False,
        set_status_on_exception=False,
    ) as current:
        try:
            yield current
        except BaseException as error:
            current.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise


def set_request_attributes(*, space_id: str | None = None) -> None:
    """Label this request's spans: the current one and every later one.

    Later ones include the automatic SQL and outbound HTTP spans.

    Args:
        space_id: Id of the space making the request.
    """
    attributes = {SPACE_ID_ATTR: space_id}
    kept = {key: value for key, value in attributes.items() if value is not None}
    _request_attributes.set({**(_request_attributes.get() or {}), **kept})
    trace.get_current_span().set_attributes(kept)
