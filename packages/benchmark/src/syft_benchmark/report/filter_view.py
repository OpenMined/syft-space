"""What a job built and filtered: its filter decisions, and its build counts.

A job's decisions are the ``meta.screening`` records stamped with its id
(``generation.decisions``), on any pair of the target, whoever wrote it. A
pair with no record at all (decided before the stamps existed) gets one
decision inferred from its current status, attributed to the job that wrote it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from syft_benchmark.config import PairStatus, StatusReason
from syft_benchmark.db.models import Job, QaPair
from syft_benchmark.generation import decisions
from syft_benchmark.generation.web_check import CONTROL_NOTE, exclusion
from syft_benchmark.question_order import pair_key

MAX_PAGE = 200


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


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


def _rows(session: Session, target: str, job_ids: Sequence[str]) -> list[QaPair]:
    if not job_ids:
        return []
    rows = list(
        session.execute(
            select(QaPair).where(
                QaPair.space == target,
                or_(
                    QaPair.job_id.in_(job_ids),
                    *(_stamped_by(job_id) for job_id in job_ids),
                ),
            )
        ).scalars()
    )
    for row in rows:
        session.expunge(row)
    return rows


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
    if reason == StatusReason.WEB_ANSWERABLE.value or (
        not _is_control(row) and web.get("verdict")
    ):
        stage = decisions.WEB_CHECK
    elif _is_control(row) or reason == StatusReason.RETRIEVAL_GATE.value:
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


def _decisions_of(
    rows: Sequence[QaPair], job_id: str, written: dict[str, datetime | None]
) -> list[dict[str, Any]]:
    out: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for row in rows:
        meta = row.meta or {}
        entry = decisions.of_job(meta, job_id)
        recorded = entry is not None
        if entry is None:
            if row.job_id != job_id or meta.get(decisions.SCREENING):
                continue
            entry = _inferred(row)
            if entry is None:
                continue
            web_record = meta.get("web_check")
        else:
            web_record = entry.get("web")
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
                    "written_by_job_at": _iso(written.get(row.job_id or "")),
                    "written_at": _iso(row.created_at),
                    "earlier": row.job_id != job_id,
                    "status": row.status,
                    "status_note": row.status_note,
                    "recorded": recorded,
                    "web_check": _web(web_record),
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
    stage: str | None = None,
    outcome: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """The job's filter decisions in the question order, paged; counts before
    filters."""
    rows = _rows(session, job.target, [job.id])
    found = _decisions_of(rows, job.id, _writer_dates(session, rows))
    counts = decisions.outcome_counts(found)
    if stage:
        found = [d for d in found if d["stage"] == stage]
    if outcome:
        found = [d for d in found if d["outcome"] == outcome]
    page = max(1, min(limit, MAX_PAGE))
    return {
        "items": found[offset : offset + page],
        "total": len(found),
        "counts": counts,
    }


def build_counts(
    session: Session, target: str, job_ids: Sequence[str]
) -> dict[str, dict[str, int]]:
    """Per job: questions written, and its filter decisions by outcome."""
    rows = _rows(session, target, job_ids)
    out: dict[str, dict[str, int]] = {}
    for job_id in job_ids:
        found = _decisions_of(rows, job_id, {})
        out[job_id] = {
            "written": sum(1 for row in rows if row.job_id == job_id),
            "checked": len(found),
            **decisions.outcome_counts(found),
        }
    return out
