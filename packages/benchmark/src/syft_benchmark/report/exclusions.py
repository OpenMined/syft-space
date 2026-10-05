"""Leaving a question out of one run's figures, and putting it back."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from syft_benchmark.config import PairStatus, Settings, StatusReason, get_settings
from syft_benchmark.db import Job, QaPair, Result, Run, RunExclusion, session_scope
from syft_benchmark.db.run_cache import invalidate_run, invalidate_runs_with_pairs


@dataclass(frozen=True, slots=True)
class ExclusionView:
    """One exclusion as stored, and whether the pair is now retired."""

    job_id: str
    qa_id: str
    reason: str
    created_at: datetime
    retired: bool


def took_part(session: Session, job_id: str, qa_id: str, target_key: str) -> bool:
    """Whether this target's job has any result for this question."""
    found = session.execute(
        select(Result.id)
        .join(Run, Run.id == Result.run_id)
        .join(Job, Job.id == Run.job_id)
        .where(Job.id == job_id, Job.target == target_key, Result.qa_id == qa_id)
        .limit(1)
    ).first()
    return found is not None


def exclude(
    job_id: str,
    qa_id: str,
    *,
    target_key: str,
    reason: str = "",
    retire: bool = False,
    settings: Settings | None = None,
) -> ExclusionView | None:
    """Exclude a question from a run's figures; idempotent.

    ``retire`` also takes the pair out of future runs (``retired``, reason
    ``owner``). None — the question did not take part in this target's job.
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        if not took_part(session, job_id, qa_id, target_key):
            return None
        session.execute(
            insert(RunExclusion)
            .values(job_id=job_id, qa_id=qa_id, reason=reason)
            .on_conflict_do_update(
                index_elements=[RunExclusion.job_id, RunExclusion.qa_id],
                set_={"reason": reason},
            )
        )
        if retire:
            session.execute(
                update(QaPair)
                .where(QaPair.id == qa_id)
                .values(
                    status=PairStatus.RETIRED.value,
                    status_reason=StatusReason.OWNER.value,
                    status_note=reason,
                )
            )
            invalidate_runs_with_pairs(session, [qa_id])
        invalidate_run(session, job_id)

        row = session.get(RunExclusion, (job_id, qa_id))
        pair = session.get(QaPair, qa_id)
        assert row is not None and pair is not None
        return ExclusionView(
            job_id=row.job_id,
            qa_id=row.qa_id,
            reason=row.reason,
            created_at=row.created_at,
            retired=pair.status == PairStatus.RETIRED.value,
        )


def restore(
    job_id: str,
    qa_id: str,
    *,
    target_key: str,
    settings: Settings | None = None,
) -> bool:
    """Put an excluded question back into a run's figures; idempotent.

    The pair's status is left as it is. False — the question did not take part
    in this target's job.
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        if not took_part(session, job_id, qa_id, target_key):
            return False
        session.execute(
            delete(RunExclusion).where(
                RunExclusion.job_id == job_id, RunExclusion.qa_id == qa_id
            )
        )
        invalidate_run(session, job_id)
        return True
