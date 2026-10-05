"""Reading and removing generated pairs, as opposed to deciding their status.

``filter_stage`` decides whether a pending pair is fit; this module is what an
owner reviewing the outcome needs instead — the actual question and answer,
and a way to take a pair out of the set entirely rather than merely change its
status.

**Deletion is gated, not free.** Only a pair that never took part in a run
may be deleted; the guard is ``db.pair_guard.delete_pairs``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import exists, func, select

from syft_benchmark.config import Settings, get_settings
from syft_benchmark.db import QaPair, Result, session_scope
from syft_benchmark.db.pair_guard import delete_pairs

# A page any larger stops being something a person reviews and starts being
# something a person scrolls past.
MAX_PAGE = 200


@dataclass(slots=True)
class PairView:
    """One generated pair, as an owner reviewing the set needs to see it."""

    id: str
    generator: str
    task_type: str
    cohort: str
    status: str
    status_note: str
    status_reason: str | None
    question: str
    answer: str
    context: str
    expected_behavior: str
    document_title: str
    file_name: str
    meta: dict[str, Any]
    created_at: datetime
    # Whether any Result points at this pair — the one fact that decides
    # whether it can be deleted outright or only retired/rejected.
    has_results: bool


def _view(row: QaPair, *, has_results: bool) -> PairView:
    return PairView(
        id=row.id,
        generator=row.generator,
        task_type=row.task_type,
        cohort=row.cohort,
        status=row.status,
        status_note=row.status_note,
        status_reason=row.status_reason,
        question=row.question,
        answer=row.answer,
        context=row.context,
        expected_behavior=row.expected_behavior,
        document_title=row.document_title,
        file_name=row.file_name,
        meta=dict(row.meta or {}),
        created_at=row.created_at,
        has_results=has_results,
    )


def list_pairs(
    target_key: str,
    *,
    status: str | None = None,
    cohort: str | None = None,
    generator: str | None = None,
    job: str | None = None,
    limit: int = 50,
    offset: int = 0,
    settings: Settings | None = None,
) -> tuple[list[PairView], int]:
    """This target's pairs, newest first, with whether each has results.

    Args:
        target_key: The node under test
        status: Only pairs with this status; None — every status
        cohort: Only this cohort; None — every cohort
        generator: Only this generator's pairs; None — every generator
        job: Only what this launch generated; None — everything the node has.
            Pairs older than the column, or built outside the queue, belong to
            no launch and are matched by no value of this
        limit: Page size, capped at `MAX_PAGE`
        offset: How many to skip, for paging
        settings: The process settings

    Returns:
        The page of pairs, and the total count the filters match (for paging)
    """
    conf = settings or get_settings()
    page = max(1, min(limit, MAX_PAGE))

    with session_scope(conf) as session:
        base = select(QaPair).where(QaPair.space == target_key)
        if status:
            base = base.where(QaPair.status == status)
        if cohort:
            base = base.where(QaPair.cohort == cohort)
        if generator:
            base = base.where(QaPair.generator == generator)
        if job:
            base = base.where(QaPair.job_id == job)

        total = session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()

        rows = list(
            session.execute(
                base.order_by(QaPair.created_at.desc()).limit(page).offset(offset)
            ).scalars()
        )
        if not rows:
            return [], total

        with_results = set(
            session.execute(
                select(Result.qa_id).where(Result.qa_id.in_([row.id for row in rows]))
            )
            .scalars()
            .all()
        )
        views = [_view(row, has_results=row.id in with_results) for row in rows]
        return views, total


def get_pair(
    pair_id: str, *, target_key: str | None = None, settings: Settings | None = None
) -> PairView | None:
    """One pair's full detail, or None if there is no such pair.

    Args:
        pair_id: The pair to read
        target_key: If given, a pair belonging to a different target counts
            as not found — a session token minted for one target must not
            read another's by guessing an id
        settings: The process settings
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        row = session.get(QaPair, pair_id)
        if row is None or (target_key is not None and row.space != target_key):
            return None
        has_results = session.execute(
            select(exists().where(Result.qa_id == pair_id))
        ).scalar_one()
        return _view(row, has_results=bool(has_results))


def delete_pair(
    pair_id: str, *, target_key: str | None = None, settings: Settings | None = None
) -> str:
    """Remove a pair outright — only when nothing measured it yet.

    Args:
        pair_id: The pair to remove
        target_key: If given, a pair belonging to a different target counts
            as not found, for the same reason as in `get_pair`
        settings: The process settings

    Returns:
        "deleted", "not_found", or "has_results" (retire or reject it
        instead — see `filter_stage.override_status`)
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        row = session.get(QaPair, pair_id)
        if row is None or (target_key is not None and row.space != target_key):
            return "not_found"
        return "deleted" if delete_pairs(session, [pair_id]).deleted else "has_results"
