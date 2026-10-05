"""Dropping a run's cached aggregate when something it was computed from changes.

The aggregate (``run_aggregates``) is recomputed on the next read once its row
is gone.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from syft_benchmark.db.models import Result, Run, RunAggregate


def invalidate_run(session: Session, job_id: str | None) -> None:
    """Drop the cached aggregate of one job."""
    if job_id:
        invalidate_runs(session, [job_id])


def invalidate_runs(session: Session, job_ids: Iterable[str | None]) -> None:
    """Drop the cached aggregates of these jobs."""
    wanted = sorted({j for j in job_ids if j})
    if wanted:
        session.execute(delete(RunAggregate).where(RunAggregate.job_id.in_(wanted)))


def jobs_with_pairs(session: Session, pair_ids: Iterable[str]) -> list[str]:
    """The jobs in which any of these pairs has a result."""
    wanted = list(set(pair_ids))
    if not wanted:
        return []
    rows = session.execute(
        select(Run.job_id)
        .join(Result, Result.run_id == Run.id)
        .where(Result.qa_id.in_(wanted), Run.job_id.is_not(None))
        .distinct()
    ).scalars()
    return [job for job in rows if job]


def invalidate_runs_with_pairs(session: Session, pair_ids: Iterable[str]) -> None:
    """Drop the cached aggregates of every job these pairs took part in."""
    invalidate_runs(session, jobs_with_pairs(session, pair_ids))
