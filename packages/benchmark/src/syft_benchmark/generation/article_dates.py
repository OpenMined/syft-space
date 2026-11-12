"""The article date and address kept on each question.

The date is for the run report's article range. It follows
``sources.article_date``: publication, else added to the Space, else scraped.
Stored as the UTC day ("YYYY-MM-DD") in ``meta.article_date`` and its source
in ``meta.article_dated_by``.

The address is the ETL header's ``url``, in ``meta.article_url``: the report
marks an answer whose web citations include the very article its question was
written from.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import delete, or_, select

from syft_benchmark.config import Settings
from syft_benchmark.db import Job, QaPair, RunAggregate, session_scope

DATE_KEY = "article_date"
SOURCE_KEY = "article_dated_by"
URL_KEY = "article_url"


class Dated(Protocol):
    """The dates and address of a ``sources.Document`` (this module reads no text)."""

    @property
    def doc_id(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def published_at(self) -> datetime | None: ...
    @property
    def added_at(self) -> datetime | None: ...
    @property
    def ingested_at(self) -> datetime | None: ...


def article_stamp(doc: Dated) -> dict[str, str]:
    """``{article_date, article_dated_by, article_url}`` for the document,
    each only where known; {} when neither is."""
    stamp: dict[str, str] = {}
    for source, at in (
        ("published", doc.published_at),
        ("added", doc.added_at),
        ("scraped", doc.ingested_at),
    ):
        if at is not None:
            stamp = {DATE_KEY: at.date().isoformat(), SOURCE_KEY: source}
            break
    if doc.url:
        stamp[URL_KEY] = doc.url
    return stamp


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
                or_(~QaPair.meta.has_key(DATE_KEY), ~QaPair.meta.has_key(URL_KEY)),
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
