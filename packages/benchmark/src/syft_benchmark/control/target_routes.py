"""Service routes for targets and their jobs: the registry, checks, launching,
console sessions, job state and cancelling."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from syft_benchmark.config import JobKind
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.control import session as console_sessions
from syft_benchmark.control import targets as registry
from syft_benchmark.control.auth import Guard
from syft_benchmark.control.check import IndexUnreachable, articles_in_window, check
from syft_benchmark.control.compose import merge, settings_for
from syft_benchmark.control.refusals import (
    refuse_clash,
    refuse_run_clash,
    refuse_unfiltered,
    require_enabled,
    target_or_404,
)
from syft_benchmark.control.schemas import (
    FilterRequest,
    JobView,
    JudgeRequest,
    RunRequest,
    SessionView,
    TargetSpec,
    TargetView,
    WindowView,
)
from syft_benchmark.db.crypto import SecretsNotConfigured
from syft_benchmark.db.models import Job
from syft_benchmark.db.session import session_scope

router = APIRouter()


@router.get("/targets", response_model=list[TargetView])
def list_targets(conf: Guard) -> list[TargetView]:
    with session_scope(conf) as session:
        rows = registry.all_targets(session)
        keys = [row.key for row in rows]
        # One query apiece for the tokens and the latest jobs, not one per row.
        with_token = registry.tokens_for(session, keys)
        last_jobs = _last_jobs(session, keys)
        views = [registry.view(row, has_token=row.key in with_token) for row in rows]
        for item in views:
            item.last_job = last_jobs.get(item.key)
        return views


@router.get("/targets/{key}", response_model=TargetView)
def get_target(key: str, conf: Guard) -> TargetView:
    with session_scope(conf) as session:
        row = target_or_404(session, key)
        item = registry.view(row, has_token=registry.has_token(session, key))
        item.last_job = _last_job(session, key)
        return item


@router.put("/targets/{key}", response_model=TargetView)
def put_target(key: str, spec: TargetSpec, conf: Guard) -> TargetView:
    """Create a target or rewrite it whole.

    PUT rather than PATCH: with a partial update a cleared checkbox could not
    be told from a field that was not sent.
    """
    if spec.key != key:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"the key in the address ({key}) and in the body ({spec.key}) differ",
        )
    effective = merge(conf, spec.instrument, spec.probe)
    refuse_clash(effective)
    # A target that runs on its own schedule evaluates unattended.
    refuse_unfiltered(effective, spec.enabled and bool(spec.schedule.strip()))
    with session_scope(conf) as session:
        try:
            row = registry.save(session, spec, conf)
        except SecretsNotConfigured as exc:
            # A token was sent and there is nowhere to seal it. Saving the
            # target without it would look like success and fail in a run.
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
        item = registry.view(row, has_token=registry.has_token(session, key))
        item.last_job = _last_job(session, key)
        return item


@router.post("/targets/{key}/check")
def check_target(key: str, conf: Guard) -> dict[str, Any]:
    """Walk the roads to the target: to the index, the node and the models."""
    with session_scope(conf) as session:
        row = target_or_404(session, key)
        node_conf, space = settings_for(row, conf)
    result = check(space, node_conf)
    return {**dataclasses.asdict(result), "ok": result.ok}


@router.get("/targets/{key}/window", response_model=WindowView)
def target_window(
    key: str,
    conf: Guard,
    days: Annotated[int | None, Query(ge=0)] = None,
) -> WindowView:
    """How many articles the time window holds now, by generation's rule.

    ``days`` overrides the saved window, so a page can count before saving.
    """
    with session_scope(conf) as session:
        row = target_or_404(session, key)
        node_conf, space = settings_for(row, conf)
    if days is not None:
        node_conf = node_conf.model_copy(update={"document_window_days": days})
    try:
        counted = articles_in_window(space, node_conf)
    except IndexUnreachable as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return WindowView(
        count=counted.count,
        undated=counted.undated,
        total=counted.total,
        window_days=counted.window_days,
    )


@router.post("/targets/{key}/runs", response_model=JobView, status_code=202)
def start_run(key: str, request: RunRequest, conf: Guard) -> JobView:
    """Put a measurement in the queue; the answer is the job to watch it by."""
    with session_scope(conf) as session:
        row = target_or_404(session, key)
        require_enabled(row)
        refuse_run_clash(row, request, conf)
        job = job_queue.enqueue(session, row, request)
        return JobView.model_validate(job)


@router.post("/targets/{key}/filter", response_model=JobView, status_code=202)
def start_filter(key: str, request: FilterRequest, conf: Guard) -> JobView:
    """Put a filter pass in the queue: screen this target's pending pairs."""
    with session_scope(conf) as session:
        row = target_or_404(session, key)
        require_enabled(row)
        job = job_queue.enqueue(session, row, request, kind=JobKind.FILTER)
        return JobView.model_validate(job)


@router.post("/targets/{key}/judge", response_model=JobView, status_code=202)
def start_judge(key: str, request: JudgeRequest, conf: Guard) -> JobView:
    """Put a judging pass in the queue: grade this target's pending verdicts."""
    with session_scope(conf) as session:
        row = target_or_404(session, key)
        require_enabled(row)
        job = job_queue.enqueue(session, row, request, kind=JobKind.JUDGE)
        return JobView.model_validate(job)


@router.post("/targets/{key}/session", response_model=SessionView)
def start_console_session(key: str, conf: Guard) -> SessionView:
    """Mint a short-lived console session scoped to this one target."""
    with session_scope(conf) as session:
        target_or_404(session, key)
    token, expires_at = console_sessions.mint(key, conf)
    return SessionView(
        token=token, expires_at=datetime.fromtimestamp(expires_at, tz=UTC)
    )


@router.get("/targets/{key}/jobs", response_model=list[JobView])
def target_jobs(key: str, conf: Guard) -> list[JobView]:
    with session_scope(conf) as session:
        return [
            JobView.model_validate(row) for row in job_queue.recent_jobs(session, key)
        ]


@router.post("/jobs/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str, conf: Guard) -> JobView:
    """Ask a job to stop.

    A running one finishes the current question and exits by itself, so the
    response still says "running". What is done stays in the database.
    """
    with session_scope(conf) as session:
        if not job_queue.cancel(session, job_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"job {job_id} has already finished, or there is no such job",
            )
        session.flush()
        job = session.get(Job, job_id)
        return JobView.model_validate(job)


def _last_job(session: Session, key: str) -> JobView | None:
    """The target's latest job, shown in the list without opening the target."""
    row = session.scalars(
        select(Job).where(Job.target == key).order_by(Job.created_at.desc()).limit(1)
    ).first()
    return JobView.model_validate(row) if row is not None else None


def _last_jobs(session: Session, keys: list[str]) -> dict[str, JobView]:
    """The latest job per target, in one query, for the list view."""
    if not keys:
        return {}
    rows = session.scalars(
        select(Job)
        .distinct(Job.target)
        .where(Job.target.in_(keys))
        .order_by(Job.target, Job.created_at.desc())
    )
    return {row.target: JobView.model_validate(row) for row in rows}
