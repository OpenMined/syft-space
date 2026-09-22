"""The connection to Postgres.

The engine is created once per process: the daily cycle is a long series of
short transactions, and there is no reason to recreate the pool for each one.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from syft_benchmark.config import Settings, env_settings

# The settings are read from this database, so the first settings lookup of a
# process is a connection. With libpq's default of "no timeout", a host that
# does not answer at all hangs the process instead of falling back to the
# built-in defaults — and the doctor cannot report an unreachable database
# while it is blocked on reaching it.
CONNECT_TIMEOUT_SECONDS = 5


@lru_cache(maxsize=1)
def get_engine(database_url: str | None = None) -> Engine:
    """The engine for the benchmark's database."""
    url = database_url or env_settings().database_url
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """A session that commits on exit and rolls back on error.

    A run is interruptible: every pair and every verdict is written
    immediately rather than at the end, so we keep the transaction's scope
    short and explicit.
    """
    # The environment's settings when none were passed: the assembled ones are
    # read FROM this database, so asking for them here would be a circle.
    factory = sessionmaker(bind=get_engine((settings or env_settings()).database_url))
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
