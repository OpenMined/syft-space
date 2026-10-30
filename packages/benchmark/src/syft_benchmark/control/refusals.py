"""HTTP refusals the service and console routes share: a missing or disabled
target, a job of another target, and a launch the judge policy or the web
check gate forbids."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from syft_benchmark.config import Settings
from syft_benchmark.control.compose import merge, settings_for
from syft_benchmark.control.schemas import RunRequest
from syft_benchmark.db.models import Job, Target
from syft_benchmark.llm.roles import clash_refusal
from syft_benchmark.runs.gate import FILTER_REQUIRED, filter_missing


def target_or_404(session: Session, key: str) -> Target:
    """The target row, or a 404."""
    row = session.get(Target, key)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"there is no target {key}")
    return row


def job_or_404(session: Session, target_key: str, job_id: str) -> Job:
    """The target's job, or a 404: another target's job does not exist here."""
    job = session.get(Job, job_id)
    if job is None or job.target != target_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"there is no job {job_id}")
    return job


def require_enabled(row: Target) -> None:
    """409 for a disabled target: it is not launched."""
    if not row.enabled:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"target {row.key} is disabled — enable it before measuring",
        )


def refuse_clash(effective: Settings) -> None:
    """422 when a judge and a tested model share a company under ``strict``."""
    reason = clash_refusal(effective)
    if reason is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, reason)


def refuse_unfiltered(effective: Settings, evaluates: bool) -> None:
    """422 when questions would be asked and no web check model is set."""
    if evaluates and filter_missing(effective):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, FILTER_REQUIRED)


def refuse_run_clash(row: Target, request: RunRequest, conf: Settings) -> None:
    """The launch checks on what the run would use: the target plus the request."""
    node_conf, _ = settings_for(row, conf)
    extra = [x for x in (request.instrument, request.probe) if x is not None]
    effective = merge(node_conf, *extra) if extra else node_conf
    refuse_clash(effective)
    refuse_unfiltered(effective, request.evaluate is not False)
