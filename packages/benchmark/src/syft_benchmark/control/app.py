"""The control API application: the only way the benchmark is driven from
outside. Assembles the routers, the queue worker and the schedule thread.

Who may call which route is set out in ``control/auth.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from syft_benchmark.config import Settings, get_settings
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.control import targets as registry
from syft_benchmark.control.console_routes import router as console_router
from syft_benchmark.control.installation_routes import router as installation_router
from syft_benchmark.control.report_routes import router as report_router
from syft_benchmark.control.target_routes import router as target_router
from syft_benchmark.control.ticker import Ticker
from syft_benchmark.db import store
from syft_benchmark.db.session import session_scope


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Close the jobs the last process left running, then start the queue
    worker and the schedule thread.

    A job left "running" by a dead process has nobody to continue it, and
    without the cleanup it would lock its target's queue forever.
    """
    conf: Settings = app.state.settings
    # Said once: which provider keys are read from the environment in the
    # clear rather than from the sealed store.
    store.warn_about_env_secrets(conf)
    closed = job_queue.sweep(conf)
    if closed:
        logger.warning(f"jobs closed that outlived the restart: {closed}")
    with session_scope(conf) as session:
        seeded = registry.seed(session, conf)
    if seeded:
        logger.info(f"targets carried over from the file: {seeded}")
    worker = job_queue.Worker(conf)
    worker.start()
    app.state.worker = worker
    # A thread of its own: the worker is busy for hours with one measurement.
    ticker = Ticker(conf)
    ticker.start()
    app.state.ticker = ticker
    try:
        yield
    finally:
        ticker.stop()
        worker.stop()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the control API application."""
    conf = settings or get_settings()
    app = FastAPI(
        title="syft-benchmark control",
        version="1",
        summary="Targets, settings and launching measurements",
        lifespan=lifespan,
    )
    app.state.settings = conf

    if conf.control_origins:
        # Empty by default: the Space calls from its own server, and CORS
        # "just in case" would open launching measurements to any browser tab.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=conf.control_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health", summary="Is the service alive")
    def health(request: Request) -> dict[str, Any]:
        """No key needed: this checks that somebody is at the address at all."""
        return {
            "service": "syft-benchmark",
            "control": bool(request.app.state.settings.control_token),
        }

    app.include_router(installation_router)
    app.include_router(target_router)
    app.include_router(console_router)
    app.include_router(report_router)
    return app
