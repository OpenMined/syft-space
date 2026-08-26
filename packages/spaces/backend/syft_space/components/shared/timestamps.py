"""Parsing of the date formats sources receive from upstream APIs.

Sources put a ``datetime`` in ``IngestFile.metadata`` rather than the raw
string they were given; the vector store decides how to serialize it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an upstream date into an aware UTC ``datetime``.

    Covers ISO 8601 (Atom, Blogger, the WordPress ``*_gmt`` fields) and
    RFC 822 (RSS ``pubDate``). Returns ``None`` for anything unparseable —
    a missing date is not worth failing an ingest over.

    A naive value is read as UTC, which is what the formats that omit an
    offset mean. Letting it default to the machine's local zone would shift
    every such date by the server's offset.
    """
    if not value:
        return None

    parsed: datetime | None = None
    for parser in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            parsed = parser(value)
            break
        except (ValueError, TypeError):
            continue

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
