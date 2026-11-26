"""The article date, address and header kept on each question.

The date is for the run report's article range. It follows
``sources.article_date``: publication, else indexed by the Space, else scraped.
Stored as the UTC day ("YYYY-MM-DD") in ``meta.article_date`` and its source
in ``meta.article_dated_by``.

The address is the ETL header's ``url``, in ``meta.article_url``: the report
marks an answer whose web citations include the very article its question was
written from.

The header's outlet and author, in ``meta.article_outlet`` and
``meta.article_author``, make up the article header (``pair_header``) that
the grounding check reads with the passage and arm C shows over the oracle
chunk.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, Protocol

from sqlalchemy import delete, or_, select

from syft_benchmark.config import Settings
from syft_benchmark.db import Job, QaPair, RunAggregate, session_scope

DATE_KEY = "article_date"
SOURCE_KEY = "article_dated_by"
URL_KEY = "article_url"
# The header's outlet and author, where it names them.
OUTLET_KEY = "article_outlet"
AUTHOR_KEY = "article_author"

_MONTHS = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)  # fmt: skip


class Dated(Protocol):
    """The dates and address of a ``sources.Document`` (this module reads no text)."""

    @property
    def doc_id(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def source(self) -> str: ...
    @property
    def author(self) -> str: ...
    @property
    def published_at(self) -> datetime | None: ...
    @property
    def indexed_at(self) -> datetime | None: ...
    @property
    def ingested_at(self) -> datetime | None: ...


def article_stamp(doc: Dated) -> dict[str, str]:
    """``{article_date, article_dated_by, article_url, article_outlet,
    article_author}`` for the document, each only where known."""
    stamp: dict[str, str] = {}
    for source, at in (
        ("published", doc.published_at),
        ("added", doc.indexed_at),
        ("scraped", doc.ingested_at),
    ):
        if at is not None:
            stamp = {DATE_KEY: at.date().isoformat(), SOURCE_KEY: source}
            break
    if doc.url:
        stamp[URL_KEY] = doc.url
    if doc.source:
        stamp[OUTLET_KEY] = doc.source
    if doc.author:
        stamp[AUTHOR_KEY] = doc.author
    return stamp


def format_header(title: str, author: str, outlet: str, published: str) -> str:
    """An article header on one line, the fields known; empty — none."""
    parts = (
        ("Title", title.strip()),
        ("Author", author.strip()),
        ("Outlet", outlet.strip()),
        ("Published", published.strip()[:10]),
    )
    return " | ".join(f"{label}: {value}" for label, value in parts if value)


def pair_header(title: str, meta: dict[str, Any] | None) -> str:
    """The header of a question's article, from its title and stamp."""
    meta = meta or {}
    published = (
        str(meta.get(DATE_KEY) or "") if meta.get(SOURCE_KEY) == "published" else ""
    )
    return format_header(
        title,
        str(meta.get(AUTHOR_KEY) or ""),
        str(meta.get(OUTLET_KEY) or ""),
        published,
    )


def header_words(title: str, meta: dict[str, Any] | None) -> str:
    """The question's article header as text a claim is checked against: the
    header, and its publish date with the month named ("November 2026")."""
    meta = meta or {}
    header = pair_header(title, meta)
    if meta.get(SOURCE_KEY) != "published":
        return header
    try:
        day = date.fromisoformat(str(meta.get(DATE_KEY) or ""))
    except ValueError:
        return header
    return f"{header} ({day.day} {_MONTHS[day.month - 1]} {day.year})"


def backfill(space: str, documents: Iterable[Dated], conf: Settings) -> int:
    """Stamp the space's questions that have no article date or address yet.

    A key a question already has is kept. Clears the space's cached run
    figures when any question changed, so older runs show the range. Returns
    how many questions were stamped.
    """
    stamps = {doc.doc_id: article_stamp(doc) for doc in documents}
    stamps = {doc_id: stamp for doc_id, stamp in stamps.items() if stamp}
    if not stamps:
        return 0
    stamped = 0
    with session_scope(conf) as session:
        rows = session.execute(
            select(QaPair).where(
                QaPair.space == space,
                QaPair.doc_id.in_(stamps),
                or_(
                    ~QaPair.meta.has_key(DATE_KEY),
                    ~QaPair.meta.has_key(URL_KEY),
                    ~QaPair.meta.has_key(OUTLET_KEY),
                ),
            )
        ).scalars()
        for row in rows:
            meta: dict[str, Any] = dict(row.meta or {})
            missing = {k: v for k, v in stamps[row.doc_id].items() if k not in meta}
            if not missing:
                continue
            row.meta = meta | missing
            stamped += 1
        if stamped:
            session.execute(
                delete(RunAggregate).where(
                    RunAggregate.job_id.in_(select(Job.id).where(Job.target == space))
                )
            )
    return stamped
