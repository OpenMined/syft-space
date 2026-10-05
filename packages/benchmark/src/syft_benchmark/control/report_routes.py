"""The console's read API of benchmark results: runs, a run's report, its
questions, and leaving a question out of a run.

Everything is scoped to the session's target; a job of another target is a
404. Figures come from ``report.run_view``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from syft_benchmark.control.app import ConsoleAuth, ConsoleGuard
from syft_benchmark.control.compose import merge
from syft_benchmark.control.schemas import ExclusionRequest, Instrument, Probe
from syft_benchmark.db import Job, Run, Target, session_scope
from syft_benchmark.report import exclusions, run_questions, run_view
from syft_benchmark.report.run_document import build_summary, filename

router = APIRouter(prefix="/console/report", tags=["results"])

PROGRESS_FIELDS = (
    "state",
    "trigger",
    "kind",
    "phase",
    "block",
    "model",
    "step_done",
    "step_total",
    "done",
    "total",
    "message",
)


def _target(session: Session, auth: ConsoleAuth) -> Target:
    row = session.get(Target, auth.target_key)
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"there is no target {auth.target_key}"
        )
    return row


def _panel(target: Target, auth: ConsoleAuth) -> list[str]:
    """The judges configured for the target, primary first."""
    conf = merge(
        auth.settings,
        Instrument.model_validate(target.instrument or {}),
        Probe.model_validate(target.probe or {}),
    )
    return run_view.configured_panel(conf)


def _job(session: Session, auth: ConsoleAuth, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.target != auth.target_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"there is no job {job_id}")
    return job


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _summary(job: Job, run: dict[str, Any]) -> dict[str, Any]:
    return {**run, "card_outdated": run_view.card_outdated(job.card, run)}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _unknown_model(model: str) -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, f"model {model!r} did not answer in this run"
    )


@router.get("/runs")
def list_runs(
    auth: ConsoleGuard,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    job_ids: str | None = None,
    exclude_job_ids: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Every queued or running job, and a page of the finished runs, newest
    first."""
    with session_scope(auth.settings) as session:
        target = _target(session, auth)
        active = session.scalars(
            select(Job)
            .where(
                Job.target == auth.target_key,
                Job.state.in_(run_view.ACTIVE_STATES),
            )
            .order_by(Job.created_at.desc())
        ).all()
        in_progress = [
            {
                "job_id": job.id,
                **{name: getattr(job, name) for name in PROGRESS_FIELDS},
                "created_at": _iso(job.created_at),
                "started_at": _iso(job.started_at),
            }
            for job in active
        ]

        where = [
            Job.target == auth.target_key,
            Job.state.not_in(run_view.ACTIVE_STATES),
            exists().where(Run.job_id == Job.id),
        ]
        if date_from is not None:
            where.append(Job.created_at >= _start_of(date_from))
        if date_to is not None:
            where.append(Job.created_at < _start_of(date_to + timedelta(days=1)))
        wanted = _csv(job_ids)
        if job_ids is not None:
            where.append(Job.id.in_(wanted))
        unwanted = _csv(exclude_job_ids)
        if unwanted:
            where.append(Job.id.not_in(unwanted))

        total = session.execute(
            select(func.count()).select_from(Job).where(*where)
        ).scalar_one()
        jobs = session.scalars(
            select(Job)
            .where(*where)
            .order_by(Job.created_at.desc(), Job.id)
            .limit(limit)
            .offset(offset)
        ).all()
        runs = run_view.summaries(
            session, jobs, configured=lambda: _panel(target, auth)
        )
        return {
            "in_progress": in_progress,
            "items": [_summary(job, runs[job.id]) for job in jobs],
            "total": total,
        }


@router.get("/runs/{job_id}")
def get_run(job_id: str, auth: ConsoleGuard) -> dict[str, Any]:
    """The whole run except per-question rows."""
    with session_scope(auth.settings) as session:
        target = _target(session, auth)
        job = _job(session, auth, job_id)
        report = run_view.report_part(
            session, job, configured=lambda: _panel(target, auth)
        )
        report["run"] = _summary(job, report["run"])
        report["method"] = {**report["method"], "next_run_at": _iso(target.next_run_at)}
        return report


@router.get("/runs/{job_id}/questions")
def list_run_questions(
    job_id: str,
    auth: ConsoleGuard,
    model: str,
    group: str | None = None,
    generator: str | None = None,
    q: str | None = None,
    excluded: str = "include",
    limit: Annotated[int, Query(ge=1, le=run_questions.MAX_PAGE)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """One model's questions in this run, paged; trick questions are not
    listed."""
    if group is not None and group not in run_view.GROUPS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"group must be one of {', '.join(run_view.GROUPS)}",
        )
    if excluded not in run_questions.EXCLUDED_FILTERS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"excluded must be one of {', '.join(run_questions.EXCLUDED_FILTERS)}",
        )
    with session_scope(auth.settings) as session:
        target = _target(session, auth)
        job = _job(session, auth, job_id)
        try:
            return run_questions.list_questions(
                session,
                job,
                model=model,
                group=group,
                generator=generator,
                q=q,
                excluded=excluded,
                limit=limit,
                offset=offset,
                configured=lambda: _panel(target, auth),
            )
        except run_questions.UnknownModel as exc:
            raise _unknown_model(model) from exc


def _detail(
    session: Session, auth: ConsoleAuth, job_id: str, qa_id: str, model: str | None
) -> dict[str, Any]:
    target = _target(session, auth)
    job = _job(session, auth, job_id)
    try:
        detail = run_questions.question_detail(
            session, job, qa_id, model=model, configured=lambda: _panel(target, auth)
        )
    except run_questions.UnknownModel as exc:
        raise _unknown_model(model or "") from exc
    if detail is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"question {qa_id} did not take part in job {job_id}",
        )
    return detail


@router.get("/runs/{job_id}/questions/{qa_id}")
def get_run_question(
    job_id: str, qa_id: str, auth: ConsoleGuard, model: str | None = None
) -> dict[str, Any]:
    """One question of the run in full, for one model (the first by default)."""
    with session_scope(auth.settings) as session:
        return _detail(session, auth, job_id, qa_id, model)


@router.get("/runs/{job_id}/questions/{qa_id}/fragments")
def get_run_question_fragments(
    job_id: str, qa_id: str, auth: ConsoleGuard, model: str | None = None
) -> list[dict[str, Any]]:
    """The passages sent with the with-data answer."""
    with session_scope(auth.settings) as session:
        target = _target(session, auth)
        job = _job(session, auth, job_id)
        try:
            found = run_questions.fragments(
                session,
                job,
                qa_id,
                model=model,
                configured=lambda: _panel(target, auth),
            )
        except run_questions.UnknownModel as exc:
            raise _unknown_model(model or "") from exc
        if found is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"question {qa_id} did not take part in job {job_id}",
            )
        return found


@router.put("/runs/{job_id}/questions/{qa_id}/exclusion")
def exclude_question(
    job_id: str,
    qa_id: str,
    body: ExclusionRequest,
    auth: ConsoleGuard,
    model: str | None = None,
) -> dict[str, Any]:
    """Leave a question out of this run's figures; `retire` also takes it out
    of future runs. Returns the question detail."""
    view = exclusions.exclude(
        job_id,
        qa_id,
        target_key=auth.target_key,
        reason=body.reason,
        retire=body.retire,
        settings=auth.settings,
    )
    if view is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"question {qa_id} did not take part in job {job_id}",
        )
    with session_scope(auth.settings) as session:
        return _detail(session, auth, job_id, qa_id, model)


@router.delete(
    "/runs/{job_id}/questions/{qa_id}/exclusion",
    status_code=status.HTTP_204_NO_CONTENT,
)
def restore_question(job_id: str, qa_id: str, auth: ConsoleGuard) -> None:
    """Put the question back into this run's figures; its status stays."""
    if not exclusions.restore(
        job_id, qa_id, target_key=auth.target_key, settings=auth.settings
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"question {qa_id} did not take part in job {job_id}",
        )


@router.get("/runs/{job_id}/summary.docx")
def download_summary(job_id: str, auth: ConsoleGuard) -> Response:
    """The run's summary document: its figures only, no questions."""
    with session_scope(auth.settings) as session:
        target = _target(session, auth)
        job = _job(session, auth, job_id)
        report = run_view.report_part(
            session, job, configured=lambda: _panel(target, auth)
        )
        title = target.title or target.endpoint or target.key
        name = filename(target.endpoint or target.key, job.created_at)
    return Response(
        content=build_summary(report, title=title),
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
