"""The installation's stored settings and sealed secrets.

The store is where a setting is written, so the console needs a way in:
an installation without a UI is otherwise one where nothing can change.
"""

from __future__ import annotations

import json
import sys
from typing import Annotated

import typer

from syft_benchmark.config import env_settings
from syft_benchmark.db import store
from syft_benchmark.db.crypto import SecretsNotConfigured, SecretUnreadable, new_key

settings_app = typer.Typer(help="The installation's own settings — the bottom layer")
secrets_app = typer.Typer(help="Provider keys and Space tokens, sealed")


@settings_app.command("show")
def settings_show() -> None:
    """What this installation has overridden, and what it comes to.

    The overrides and the effective values are shown apart on purpose: "top-5
    because nobody changed it" and "top-5 because somebody chose it" look the
    same and are not, and only the second survives a change to the default.
    """
    overrides = store.read(env_settings())
    if not overrides:
        typer.secho("nothing is overridden — every setting is at its default", dim=True)
    for field, value in sorted(overrides.items()):
        typer.echo(f"{field} = {json.dumps(value, ensure_ascii=False)}")


@settings_app.command("set")
def settings_set(
    field: Annotated[str, typer.Argument(help="The setting's name")],
    value: Annotated[str, typer.Argument(help="The value, as JSON or as plain text")],
) -> None:
    """Override one setting for the whole installation.

    The value is read as JSON where it is JSON — so a list and a number arrive
    as a list and a number — and as text otherwise, because `default` is a
    perfectly good setting value and quoting it would be a trap.
    """
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value

    try:
        store.update(env_settings(), {field: parsed})
    except (store.SettingRejected, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"{field} = {json.dumps(parsed, ensure_ascii=False)}", fg=typer.colors.GREEN
    )


@settings_app.command("unset")
def settings_unset(
    field: Annotated[str, typer.Argument(help="The setting's name")],
) -> None:
    """Drop an override, putting the setting back to its default."""
    conf = env_settings()
    if field not in store.read(conf):
        typer.secho(f"{field} was not overridden", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    store.update(conf, {field: None})
    typer.secho(f"{field} is back to its default", fg=typer.colors.GREEN)


@secrets_app.command("keygen")
def secrets_keygen() -> None:
    """Print a fresh master key.

    It exists so that nobody invents one. A key typed by a person is a
    password, and a password is not 256 bits of anything.
    """
    typer.echo(f"BENCH_SECRET_KEY={new_key()}")


@secrets_app.command("list")
def secrets_list() -> None:
    """Which secrets are stored and when they were last set.

    Not the values. They go in and do not come out — not here, not through the
    API — and the only thing that needs one is the call it authorises.
    """
    conf = env_settings()
    stored = store.secrets(conf)
    if not stored:
        typer.secho("no secrets are stored", dim=True)
    for item in stored:
        typer.echo(f"{item.name:30} set {item.updated_at:%Y-%m-%d %H:%M} UTC")

    # The ones that are not stored but are in force anyway. Leaving them unsaid
    # would let "the keys are encrypted" be believed about a key in a file.
    for name in store.env_secrets(conf):
        typer.secho(
            f"{name:30} from the environment, in the clear", fg=typer.colors.YELLOW
        )


@secrets_app.command("set")
def secrets_set(
    name: Annotated[str, typer.Argument(help="llm_api_key, judge_key, target:<key>…")],
    value: Annotated[
        str, typer.Option(help="The secret; omitted, it is read from stdin")
    ] = "",
) -> None:
    """Store one secret, sealed.

    Reading from stdin is the point of the option being optional: a key passed
    as an argument is a key in the shell history and in the process list of
    every user on the machine.
    """
    secret = value or sys.stdin.read().strip()
    if not secret:
        typer.secho("nothing was given to store", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    try:
        store.set_secret(env_settings(), name, secret)
    except SecretsNotConfigured as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(f"{name} is stored", fg=typer.colors.GREEN)


@secrets_app.command("unset")
def secrets_unset(
    name: Annotated[str, typer.Argument(help="The secret's name")],
) -> None:
    """Remove a secret."""
    if not store.clear_secret(env_settings(), name):
        typer.secho(f"there is no secret called {name!r}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    typer.secho(f"{name} is gone", fg=typer.colors.GREEN)


@secrets_app.command("rotate")
def secrets_rotate() -> None:
    """Re-seal every secret under the active master key.

    The step in the middle of a rotation: make the new key active, move the old
    one into BENCH_SECRET_KEYS_RETIRED, run this, and only then throw the old
    key away. Rows already on the active key are skipped, so an interrupted
    rotation is finished by running it again.
    """
    try:
        moved = store.rotate(env_settings())
    except (SecretsNotConfigured, SecretUnreadable) as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(f"re-sealed: {moved}", fg=typer.colors.GREEN)
