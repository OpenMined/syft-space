"""Running the control API."""

from __future__ import annotations

from typing import Annotated

import typer

from syft_benchmark.config import get_settings


def serve(
    host: Annotated[str, typer.Option(help="The address to listen on")] = "",
    port: Annotated[int, typer.Option(help="The port")] = 0,
    reload: Annotated[
        bool, typer.Option("--reload", help="Restart when the code is edited")
    ] = False,
) -> None:
    """Raise the control API: targets, settings and launching runs from the UI.

    The same process also holds the job queue. There is no point separating
    them: the queue is strictly sequential, and a measurement spends almost all
    its time waiting on a socket.
    """
    import uvicorn

    settings = get_settings()
    if not settings.control_token:
        typer.secho(
            "BENCH_CONTROL_TOKEN is not set — the API will come up, but to "
            "everything except /health it will answer that it is not configured",
            fg=typer.colors.YELLOW,
        )
    uvicorn.run(
        "syft_benchmark.control.app:create_app",
        factory=True,
        host=host or settings.control_host,
        port=port or settings.control_port,
        reload=reload,
    )
