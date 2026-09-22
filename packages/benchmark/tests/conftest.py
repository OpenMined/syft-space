"""The tests get a database of their own, and cannot be handed a live one.

Several tests here clear the settings row and every stored credential — that is
what they are for, and the fixture doing it cannot know whose database it is.
Pointed at a running installation it drops the provider key and the methodology,
leaving the service to call a local Ollama for models named at a gateway.

So the database is chosen here rather than inherited: ``BENCH_DATABASE_URL`` is
redirected to a sibling named after it with ``_tests`` on the end, created and
migrated on the spot if missing. ``BENCH_TEST_DATABASE_URL`` overrides the
derivation for a CI that makes its own.
"""

from __future__ import annotations

import base64
import os
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SUFFIX = "_tests"


def _sibling(url: str) -> str:
    """The same server, a database named after this one plus ``_tests``."""
    head, _, name = url.rpartition("/")
    if not head or not name:
        return ""
    database, mark, query = name.partition("?")
    return f"{head}/{database}{SUFFIX}{mark}{query}"


def _create_and_migrate(url: str) -> None:
    """Make the database if it is missing, and bring its schema up to head.

    Raises:
        Exception: the server is not there, or will not have it
    """
    import psycopg

    from alembic import command
    from alembic.config import Config

    head, _, name = url.rpartition("/")
    database = name.partition("?")[0]
    admin = f"{head}/postgres".replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(admin, autocommit=True, connect_timeout=5) as connection:
        exists = connection.execute(
            "select 1 from pg_database where datname = %s", (database,)
        ).fetchone()
        if not exists:
            connection.execute(f'create database "{database}"')

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def pytest_configure(config: pytest.Config) -> None:
    """Point the whole run at the test database before anything reads settings."""
    # Needed by every test that stores a secret. The database is thrown away,
    # so a key made here protects nothing and blocks nobody.
    os.environ.setdefault("BENCH_SECRET_KEY", base64.b64encode(os.urandom(32)).decode())

    wanted = os.environ.get("BENCH_TEST_DATABASE_URL", "")
    if not wanted:
        from syft_benchmark.config import env_settings

        live = env_settings().database_url
        wanted = _sibling(live)
        if not wanted or wanted == live:
            pytest.exit(
                f"refusing to run: {live!r} gives no separate test database. "
                f"Set BENCH_TEST_DATABASE_URL to one.",
                returncode=1,
            )

    os.environ["BENCH_DATABASE_URL"] = wanted

    try:
        _create_and_migrate(wanted)
    except Exception as error:  # noqa: BLE001 — a missing server is not a failure
        # The tests that need one then skip themselves. Said out loud: a suite
        # quietly running half of itself is worse than one that cannot run.
        warnings.warn(
            f"no test database at {wanted}: {error}. Tests that need one will "
            f"be skipped.",
            stacklevel=1,
        )
