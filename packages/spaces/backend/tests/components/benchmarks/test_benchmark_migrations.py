"""Migrations that rebuild benchmark_connections keep each target's connection.

SQLite's batch mode rebuilds a table by copying it and dropping the old one.
The Space migrates with foreign keys on, so that drop fires ON DELETE SET NULL
on benchmark_targets.connection_id unless the migration puts the links back.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "syft_space" / "alembic.ini"

# The last revision before the first rebuild of benchmark_connections.
BEFORE_REBUILDS = "b7d2e4f19a60"


def _placeholder(declared_type: str) -> object:
    kind = declared_type.upper()
    if "INT" in kind or "BOOL" in kind:
        return 0
    if "DATETIME" in kind:
        return "2026-01-01 00:00:00"
    if "JSON" in kind:
        return "{}"
    return ""


def _insert(conn, table: str, values: dict[str, object]) -> None:
    """Insert a row, filling every other NOT NULL column without a default."""
    row = dict(values)
    for _, name, declared_type, notnull, default, _ in conn.execute(
        text(f"PRAGMA table_info({table})")
    ):
        if notnull and default is None and name not in row:
            row[name] = _placeholder(declared_type)
    columns = ", ".join(row)
    params = ", ".join(f":{name}" for name in row)
    conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({params})"), row)


def test_rebuilding_connections_keeps_target_links(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")

    @event.listens_for(engine, "connect")
    def _foreign_keys_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    cfg = Config(str(ALEMBIC_INI))

    def migrate(revision: str) -> None:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, revision)

    migrate(BEFORE_REBUILDS)
    connection_id, target_id = uuid4().hex, uuid4().hex
    with engine.begin() as conn:
        _insert(conn, "benchmark_connections", {"id": connection_id})
        _insert(
            conn,
            "benchmark_targets",
            {"id": target_id, "connection_id": connection_id},
        )

    migrate("head")

    with engine.connect() as conn:
        stored = conn.execute(
            text("SELECT connection_id FROM benchmark_targets WHERE id = :id"),
            {"id": target_id},
        ).scalar_one()
    engine.dispose()
    assert stored == connection_id
