"""The article date kept on each question, for the run report's article range.

The date follows ``sources.article_date``: publication, else added to the
Space, else scraped. Stored as the UTC day ("YYYY-MM-DD") in
``meta.article_date`` and its source in ``meta.article_dated_by``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import delete, select

from syft_benchmark.db import Job, QaPair, RunAggregate, session_scope

DATE_KEY = "article_date"
SOURCE_KEY = "article_dated_by"


class Dated(Protocol):
    """The dates of a ``sources.Document`` (this module reads no text)."""

    @property
    def doc_id(self) -> str: ...
    @property
    def published_at(self) -> datetime | None: ...
    @property
    def added_at(self) -> datetime | None: ...
    @property
    def ingested_at(self) -> datetime | None: ...


def article_stamp(doc: Dated) -> dict[str, str]:
    """``{article_date, article_dated_by}`` for the document; {} when undated."""
    for source, at in (
        ("published", doc.published_at),
        ("added", doc.added_at),
        ("scraped", doc.ingested_at),
    ):
        if at is not None:
            return {DATE_KEY: at.date().isoformat(), SOURCE_KEY: source}
    return {}


def backfill(space: str, documents: Iterable[Dated]) -> int:
    """Stamp the space's questions that have no article date yet.

    Clears the space's cached run figures when any question changed, so older
    runs show the range. Returns how many questions were stamped.
    """
    stamps = {doc.doc_id: article_stamp(doc) for doc in documents}
    stamps = {doc_id: stamp for doc_id, stamp in stamps.items() if stamp}
    if not stamps:
        return 0
    stamped = 0
    with session_scope() as session:
        rows = session.execute(
            select(QaPair).where(
                QaPair.space == space,
                QaPair.doc_id.in_(stamps),
                ~QaPair.meta.has_key(DATE_KEY),
            )
        ).scalars()
        for row in rows:
            meta: dict[str, Any] = dict(row.meta or {})
            meta.update(stamps[row.doc_id])
            row.meta = meta
            stamped += 1
        if stamped:
            session.execute(
                delete(RunAggregate).where(
                    RunAggregate.job_id.in_(select(Job.id).where(Job.target == space))
                )
            )
    return stamped
