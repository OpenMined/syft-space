"""Internal CLI — container ENTRYPOINT and migration runner.

Not a user-facing tool: the station is installed with Helm. This exists so
the image has a clean entrypoint (`syft-station server`). The server runs
pending migrations itself at startup; `syft-station upgrade-db` runs them
as a standalone step (useful for debugging or pre-flight checks).
"""

import asyncio
from importlib.metadata import version as pkg_version

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def server(
    host: str = typer.Option(None, help="Bind host (default: settings)"),
    port: int = typer.Option(None, help="Bind port (default: settings)"),
    reload: bool = typer.Option(False, help="Auto-reload (dev only)"),
) -> None:
    """Run the station server."""
    import uvicorn

    from syft_station.config import app_settings

    uvicorn.run(
        "syft_station.main:app",
        host=host or app_settings.host,
        port=port or app_settings.port,
        reload=reload,
    )


@app.command(name="upgrade-db")
def upgrade_db() -> None:
    """Run pending database migrations."""
    from syft_station.components.shared.database import AsyncDatabase, SQLiteConfig
    from syft_station.config import app_settings

    async def _run() -> None:
        database = AsyncDatabase(SQLiteConfig(app_settings.sqlite_db_path))
        await database.run_migrations()
        await database.dispose()

    asyncio.run(_run())


@app.command()
def version() -> None:
    """Print the station version."""
    typer.echo(pkg_version("syft-station"))
