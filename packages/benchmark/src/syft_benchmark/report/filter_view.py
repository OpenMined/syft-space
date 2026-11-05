"""What a job built and filtered: its filter decisions, and its build counts.

A job's decisions are the ``meta.screening`` records stamped with its id
(``generation.decisions``), on any pair of the target, whoever wrote it. A
pair with no record at all gets one decision inferred from its current status,
attributed to the job that wrote it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import case, func, or_, select, text, type_coerce
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from syft_benchmark.config import PairStatus, StatusReason
from syft_benchmark.db.models import Job, QaPair
from syft_benchmark.generation import decisions
from syft_benchmark.generation.web_check import CONTROL_NOTE, exclusion
from syft_benchmark.question_order import pair_key
from syft_benchmark.report.job_params import iso

MAX_PAGE = 200


def _stamped_by(job_id: Any) -> Any:
    """``meta @> {"screening": [{"job_id": job_id}]}``; ``job_id`` a value or column."""
    return QaPair.meta.op("@>")(
        func.jsonb_build_object(
            "screening",
            func.jsonb_build_array(func.jsonb_build_object("job_id", job_id)),
        )
    )


def touched_by_job() -> Any:
    """An EXISTS over pairs this job wrote or decided on (correlated to ``Job``)."""
    return (
        select(QaPair.id)
        .where(
            QaPair.space == Job.target,
            or_(QaPair.job_id == Job.id, _stamped_by(Job.id)),
        )
        .exists()
    )


def job_pairs(
    session: Session,
    target: str,
    job_ids: Sequence[str],
    *,
    generator: str | None = None,
) -> list[QaPair]:
    """The target's pairs these jobs wrote or decided on, detached; only
    ``generator``'s when given."""
    if not job_ids:
        return []
    query = select(QaPair).where(*_of_jobs(target, job_ids))
    if generator:
        query = query.where(QaPair.generator == generator)
    rows = list(session.execute(query).scalars())
    for row in rows:
        session.expunge(row)
    return rows


def _of_jobs(target: str, job_ids: Sequence[str]) -> tuple[Any, ...]:
    """The target's pairs these jobs wrote or decided on."""
    return (
        QaPair.space == target,
        or_(
            QaPair.job_id.in_(job_ids),
            *(_stamped_by(job_id) for job_id in job_ids),
        ),
    )


def _slim_screening(meta: Any) -> Any:
    """``meta.screening`` cut to each record's job and outcome."""
    screening = meta.op("->")(decisions.SCREENING)
    record = func.jsonb_array_elements(screening).table_valued("value").alias("record")
    slim = (
        select(
            func.jsonb_agg(
                func.jsonb_build_object(
                    "job_id",
                    record.c.value.op("->")("job_id"),
                    "outcome",
                    record.c.value.op("->")("outcome"),
                )
            )
        )
        .select_from(record)
        .scalar_subquery()
    )
    return case((func.jsonb_typeof(screening) == "array", slim), else_=screening)


def _slim_web_check(meta: Any) -> Any:
    """``meta.web_check`` cut to the fields ``_inferred`` reads."""
    web = meta.op("->")("web_check")
    return func.jsonb_build_object(
        *(
            part
            for key in ("error", "verdict", "checked_at")
            for part in (key, web.op("->")(key))
        )
    )


def _decision_states(
    session: Session, target: str, job_ids: Sequence[str]
) -> list[QaPair]:
    """``job_pairs`` cut to what counting decisions reads, unattached to a session.

    The full ``meta`` is large (the writer's prompts, the raw web checks), and
    every reference to it in a query reads it out of TOAST again, so it is read
    once in an inner query and cut down there.
    """
    if not job_ids:
        return []
    inner = (
        select(
            QaPair.id,
            QaPair.job_id,
            QaPair.task_type,
            QaPair.status,
            QaPair.status_reason,
            QaPair.status_note,
            type_coerce(QaPair.meta.op("||")(text("'{}'::jsonb")), JSONB).label("meta"),
        )
        .where(*_of_jobs(target, job_ids))
        .offset(0)
        .subquery()
    )
    meta = inner.c.meta
    found = session.execute(
        select(
            inner.c.id,
            inner.c.job_id,
            inner.c.task_type,
            inner.c.status,
            inner.c.status_reason,
            inner.c.status_note,
            _slim_screening(meta),
            _slim_web_check(meta),
            meta.op("->")("grading"),
            meta.op("->")("key_facts"),
        )
    )
    keys = (decisions.SCREENING, "web_check", "grading", "key_facts")
    return [
        QaPair(
            id=qa_id,
            job_id=job_id,
            task_type=task_type,
            status=status,
            status_reason=reason,
            status_note=note,
            meta={
                key: value
                for key, value in zip(keys, values, strict=True)
                if value is not None
            },
        )
        for qa_id, job_id, task_type, status, reason, note, *values in found
    ]


# Reasons decided as the question is written (the ``writing`` stage).
_WRITING_REASONS = frozenset(
    {StatusReason.WRONG_LANGUAGE.value, StatusReason.AMBIGUOUS_ENTITY.value}
)
# Reasons decided by a live retrieval search (the ``control`` stage).
_SEARCH_REASONS = frozenset(
    {StatusReason.RETRIEVAL_GATE.value, StatusReason.NOT_ANSWERABLE.value}
)
# Reasons decided by the web check.
_WEB_REASONS = frozenset(
    {StatusReason.WEB_ANSWERABLE.value, StatusReason.PUBLIC_KNOWLEDGE.value}
)


def _is_control(row: QaPair) -> bool:
    return exclusion(row) == CONTROL_NOTE


def _inferred(row: QaPair) -> dict[str, Any] | None:
    """A decision read off the current status of an unstamped pair."""
    meta = row.meta or {}
    found = meta.get("web_check")
    web: dict[str, Any] = found if isinstance(found, dict) else {}
    status = row.status
    reason = row.status_reason
    if status == PairStatus.PENDING.value:
        if web.get("error"):
            return {
                "stage": decisions.WEB_CHECK,
                "outcome": decisions.FAILED,
                "note": row.status_note,
                "reason": None,
                "at": web.get("checked_at"),
            }
        return None
    removed = status == PairStatus.REJECTED.value
    if reason in _WRITING_REASONS:
        stage = decisions.WRITING
    elif reason in _WEB_REASONS or (not _is_control(row) and web.get("verdict")):
        stage = decisions.WEB_CHECK
    elif _is_control(row) or reason in _SEARCH_REASONS:
        stage = decisions.CONTROL
    else:
        stage = decisions.GROUNDING
    return {
        "stage": stage,
        "outcome": decisions.REMOVED if removed else decisions.KEPT,
        # A retired pair's note says why it left the set, not why it passed.
        "note": row.status_note if removed or status == PairStatus.ACTIVE.value else "",
        "reason": reason if removed else None,
        "at": web.get("checked_at"),
    }


def _web(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict) or not record.get("model"):
        return None
    requests = record.get("web_search_requests")
    return {
        "model": str(record.get("model") or ""),
        "judge": str(record.get("judge") or ""),
        "answer": str(record.get("answer") or ""),
        "verdict": str(record.get("verdict") or ""),
        "reasoning": str(record.get("reasoning") or ""),
        "citations": [
            {"url": str(c.get("url")), "title": str(c.get("title") or "")}
            for c in record.get("citations") or []
            if isinstance(c, dict) and c.get("url")
        ],
        "searches": requests if isinstance(requests, int) else None,
        "engine": str(record.get("search") or ""),
        "searched": (bool(record["web_search"]) if "web_search" in record else None),
        "search_unused": bool(record.get("web_search_unused")),
        "error": str(record["error"]) if record.get("error") else None,
        "checked_at": record.get("checked_at"),
    }


@dataclass(frozen=True, slots=True)
class Decision:
    """One filter decision of a job on a pair.

    ``web`` is the raw web check record behind it; ``recorded`` is false for a
    decision inferred from the pair's status.
    """

    row: QaPair
    entry: dict[str, Any]
    web: Any
    recorded: bool


def job_decisions(rows: Sequence[QaPair], job_id: str) -> list[Decision]:
    """Every filter decision of the job among ``rows``, in ``rows`` order."""
    out: list[Decision] = []
    for row in rows:
        meta = row.meta or {}
        entry = decisions.of_job(meta, job_id)
        if entry is not None:
            out.append(Decision(row, entry, entry.get("web"), recorded=True))
            continue
        if row.job_id != job_id or meta.get(decisions.SCREENING):
            continue
        inferred = _inferred(row)
        if inferred is not None:
            out.append(Decision(row, inferred, meta.get("web_check"), recorded=False))
    return out


def _decisions_of(
    rows: Sequence[QaPair], job_id: str, written: dict[str, datetime | None]
) -> list[dict[str, Any]]:
    out: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for d in job_decisions(rows, job_id):
        row, entry = d.row, d.entry
        out.append(
            (
                pair_key(row.generator, row.created_at, row.id),
                {
                    "qa_id": row.id,
                    "question": row.question,
                    "answer": row.answer,
                    "generator": row.generator,
                    "task_type": row.task_type,
                    "stage": entry.get("stage"),
                    "outcome": entry.get("outcome"),
                    "reason": str(entry.get("note") or ""),
                    "reason_code": entry.get("reason"),
                    "at": entry.get("at"),
                    "written_by_job": row.job_id,
                    "written_by_job_at": iso(written.get(row.job_id or "")),
                    "written_at": iso(row.created_at),
                    "earlier": row.job_id != job_id,
                    "status": row.status,
                    "status_note": row.status_note,
                    "recorded": d.recorded,
                    "web_check": _web(d.web),
                },
            )
        )
    # The question order (report API, "Question order").
    out.sort(key=lambda item: item[0])
    return [decision for _, decision in out]


def _writer_dates(
    session: Session, rows: Sequence[QaPair]
) -> dict[str, datetime | None]:
    ids = {row.job_id for row in rows if row.job_id}
    if not ids:
        return {}
    found = session.execute(select(Job.id, Job.created_at).where(Job.id.in_(ids)))
    return {job_id: at for job_id, at in found}


def job_filter(
    session: Session,
    job: Job,
    *,
    generator: str | None = None,
    stage: str | None = None,
    outcome: str | None = None,
    limit: int | None = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """The job's filter decisions in the question order; only ``generator``'s
    when given. Counts are of that kind, before the stage and outcome filters.

    Paged by ``limit``, capped at ``MAX_PAGE``; ``None`` returns every decision
    from ``offset`` on. The list is computed whole on each call, so a reader
    that needs all of one kind asks once rather than page by page.
    """
    rows = job_pairs(session, job.target, [job.id], generator=generator)
    found = _decisions_of(rows, job.id, _writer_dates(session, rows))
    counts = decisions.outcome_counts(found)
    if stage:
        found = [d for d in found if d["stage"] == stage]
    if outcome:
        found = [d for d in found if d["outcome"] == outcome]
    end = None if limit is None else offset + max(1, min(limit, MAX_PAGE))
    return {
        "items": found[offset:end],
        "total": len(found),
        "counts": counts,
    }


def counts_of(rows: Sequence[QaPair], job_id: str) -> dict[str, int]:
    """Among ``rows``: the questions the job wrote, its filter decisions, and
    those by outcome."""
    found = [d.entry for d in job_decisions(rows, job_id)]
    return {
        "written": sum(1 for row in rows if row.job_id == job_id),
        "checked": len(found),
        **decisions.outcome_counts(found),
    }


def build_counts(
    session: Session, target: str, job_ids: Sequence[str]
) -> dict[str, dict[str, int]]:
    """Per job: questions written, and its filter decisions by outcome."""
    rows = _decision_states(session, target, job_ids)
    return {job_id: counts_of(rows, job_id) for job_id in job_ids}
