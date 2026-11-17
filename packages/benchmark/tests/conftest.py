"""The tests get a database of their own, and cannot be handed a live one.

Several tests here clear the settings row and every stored credential — that is
what they are for, and the fixture doing it cannot know whose database it is.
Pointed at a running installation it drops the provider key and the methodology,
leaving the service to call a local Ollama for models named at a gateway.

So the database is chosen here rather than inherited: ``BENCH_DATABASE_URL`` is
redirected to a sibling named after it with ``_tests`` on the end, created and
migrated on the spot if missing. ``BENCH_TEST_DATABASE_URL`` overrides the
derivation for a CI that makes its own; either way, a test database equal to
the live one ends the run before a test starts.

Shared pieces: the ``needs_db`` marker, the ``clean`` and ``client`` fixtures
and the reset of the LLM layer's step-down memory here; database and control-API
helpers in ``support.py``; stubs in ``fakes.py``. Neither module is imported at
the top of this file: they read the settings, and the redirect comes first.
"""

from __future__ import annotations

import base64
import functools
import os
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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


def _test_database(live: str, override: str) -> str:
    """The database the run may use, or ``""`` when there is no safe one.

    ``override`` is ``BENCH_TEST_DATABASE_URL``; without it, the live URL's
    sibling. Whichever way it was obtained, the live database itself is refused.
    """
    wanted = override or _sibling(live)
    return "" if wanted == live else wanted


def pytest_configure(config: pytest.Config) -> None:
    """Point the whole run at the test database before anything reads settings."""
    config.addinivalue_line(
        "markers", "needs_db: needs the test database; skipped without one"
    )

    # Needed by every test that stores a secret. The database is thrown away,
    # so a key made here protects nothing and blocks nobody.
    os.environ.setdefault("BENCH_SECRET_KEY", base64.b64encode(os.urandom(32)).decode())

    from syft_benchmark.config import env_settings

    # Read before the redirect below overwrites BENCH_DATABASE_URL: the
    # environment's database, or the settings' default.
    live = env_settings().database_url
    wanted = _test_database(live, os.environ.get("BENCH_TEST_DATABASE_URL", ""))
    if not wanted:
        pytest.exit(
            f"refusing to run: no test database separate from the live {live!r}. "
            f"Set BENCH_TEST_DATABASE_URL to another database.",
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


@functools.cache
def _database_available() -> bool:
    """One probe of the test database for the whole session."""
    import sqlalchemy as sa

    from syft_benchmark.db.session import session_scope

    try:
        with session_scope() as session:
            session.execute(sa.text("select 1"))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("needs_db") and not _database_available():
        pytest.skip("the benchmark test database is unavailable")


@pytest.fixture
def clean(request: pytest.FixtureRequest) -> Iterator[None]:
    """Wipe the module's rows before and after the test.

    The keys are the module's ``SPACE``, ``KEY``, ``KEY2`` and ``OTHER_KEY``
    strings, the job ids its ``JOB`` and ``OTHER_JOB`` (see ``support.wipe``). A
    module with ``CLEARS_SETTINGS = True`` also loses the installation's settings
    row and every stored credential.
    """
    from support import wipe

    def named(*names: str) -> list[str]:
        values = (getattr(request.module, name, None) for name in names)
        return [value for value in values if isinstance(value, str)]

    keys = named("SPACE", "KEY", "KEY2", "OTHER_KEY")
    jobs = named("JOB", "OTHER_JOB")
    settings = getattr(request.module, "CLEARS_SETTINGS", False)
    wipe(*keys, jobs=jobs, settings=settings)
    yield
    wipe(*keys, jobs=jobs, settings=settings)


@pytest.fixture
def client() -> Any:
    """The control API with the shared test token (``support.AUTH``)."""
    from support import control_client

    return control_client()


@pytest.fixture(autouse=True)
def _fresh_step_downs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty the process-wide memory of parameters a model refused.

    The LLM layer remembers, per model, a reasoning effort or a web-search
    engine it stepped down from and a temperature it was refused. The maps are
    private and have no public reset; left alone, what one test taught them
    would change the requests of every later test.
    """
    from syft_benchmark.llm import tuning, web_search

    monkeypatch.setattr(tuning, "_EFFORT_STEPPED", {})
    monkeypatch.setattr(tuning, "_NO_TEMPERATURE", set())
    monkeypatch.setattr(web_search, "_STEPPED_DOWN", {})
