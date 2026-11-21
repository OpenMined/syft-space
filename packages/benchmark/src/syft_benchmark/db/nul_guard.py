"""NUL characters never reach Postgres.

Postgres cannot store U+0000: a ``text`` value refuses the byte, and ``jsonb``
refuses the ``\\u0000`` escape that ``json.dumps`` turns it into. Text from the
outside world carries it now and then — a PDF title decoded with the wrong
codec in a web-search citation was enough to fail the write of a whole pass.

The character carries no meaning in anything we store, so it is dropped on the
way out of the driver rather than at each place that writes: every string
parameter and every JSON document passes through the connection's adapters,
whatever wrote it — an ORM flush, a Core ``insert``/``update``, a batched
insert or a raw ``text()`` statement — and a column added later is covered
without anyone remembering to.
"""

from __future__ import annotations

import json
from typing import Any

from psycopg.abc import Buffer
from psycopg.types.json import set_json_dumps
from psycopg.types.string import StrBinaryDumper, StrDumperUnknown

NUL = "\x00"


def strip_nul(value: Any) -> Any:
    """``value`` with U+0000 removed from every string in it, keys included."""
    if isinstance(value, str):
        return value.replace(NUL, "") if NUL in value else value
    if isinstance(value, dict):
        return {strip_nul(key): strip_nul(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [strip_nul(item) for item in value]
    return value


def dumps_without_nul(value: Any) -> str:
    """``json.dumps`` of ``value`` after :func:`strip_nul`.

    Stripping before serializing rather than after: a literal backslash-u-0000
    in the text is escaped to ``\\\\u0000``, which Postgres accepts, and must
    stay as it is.
    """
    return json.dumps(strip_nul(value))


class _TextDumper(StrDumperUnknown):
    """The default text-format string dumper, minus NUL."""

    def dump(self, obj: str) -> Buffer | None:
        return super().dump(obj.replace(NUL, "") if NUL in obj else obj)


class _BinaryDumper(StrBinaryDumper):
    """The default binary-format string dumper, minus NUL."""

    def dump(self, obj: str) -> Buffer | None:
        return super().dump(obj.replace(NUL, "") if NUL in obj else obj)


def install(dbapi_connection: Any, _record: Any = None) -> None:
    """Make a psycopg connection drop NUL from what it sends.

    Shaped as a SQLAlchemy ``connect`` event listener.
    """
    dbapi_connection.adapters.register_dumper(str, _TextDumper)
    dbapi_connection.adapters.register_dumper(str, _BinaryDumper)
    set_json_dumps(dumps_without_nul, dbapi_connection)
