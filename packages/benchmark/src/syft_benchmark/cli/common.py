"""What every command shares: the node keys argument and resolving them."""

from __future__ import annotations

from typing import Annotated

import typer

from syft_benchmark.config import Settings, SpaceConfig
from syft_benchmark.control import targets as registry

SpaceKeys = Annotated[
    list[str] | None, typer.Argument(help="Space keys; empty — all of them")
]


def resolve_nodes(space: list[str] | None) -> list[tuple[Settings, SpaceConfig]]:
    """Resolve keys from the command line into nodes and their settings.

    The registry is the targets table — the one the service reads and the Space
    writes to when an endpoint is opted into measuring. ``config/spaces.json``
    is read only to fill an empty table.

    The settings that come back are the node's, not the installation's: the
    Space's instrument and the node's probe are already applied, so a command
    here measures what the same node measures when the UI launches it.
    """
    try:
        found = registry.resolve(space)
    except KeyError as e:
        typer.secho(str(e.args[0]), fg=typer.colors.YELLOW)
        raise typer.Exit(code=1) from e
    if not found:
        typer.secho(
            "there are no nodes in the registry — a Space adds one when an "
            "endpoint is opted into measuring, or seed the table with "
            "config/spaces.json (see config/spaces.example.json)",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)
    return found
