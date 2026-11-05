"""Which verdict of an answer counts, and who the primary judge is.

The counted verdict is the latest owner override, else the freshest verdict of
the primary judge, else that of the next judge in panel order. Every figure is
counted this way; the other judges' verdicts only feed agreement.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Generic, NamedTuple, Protocol, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from syft_benchmark.config import Verdict
from syft_benchmark.db.models import Job, Result, Run
from syft_benchmark.report.job_params import PRIMARY_JUDGE, is_finished, job_panel
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE

# The verdicts that are a graded outcome; pending and technical never enter a rate.
OUTCOMES = frozenset(
    {
        Verdict.CORRECT.value,
        Verdict.ABSTAIN.value,
        Verdict.HALLUCINATE.value,
        Verdict.WEB_SOURCED.value,
        Verdict.INCOMPLETE.value,
    }
)

# The configured judges, primary first, or how to get them: only a
# computation needs them, a cached read does not.
Panel = Sequence[str] | Callable[[], Sequence[str]]


def resolve_panel(configured: Panel) -> list[str]:
    return list(configured() if callable(configured) else configured)


class AnswerKey(NamedTuple):
    """One answer: a model's reply to one question in one arm and block.

    Its rows are the verdicts on that reply, one per judge seat plus owner
    overrides, and ``pick`` chooses the counted one among them. The run's
    context source is deliberately not part of it: an answer stays one answer
    whichever source fed it.
    """

    model: str
    context_mode: str
    block: str
    qa_id: str

    @classmethod
    def of(
        cls, model: str | None, context_mode: str, block: str, qa_id: str
    ) -> AnswerKey:
        return cls(model or "", context_mode, block, qa_id)


R = TypeVar("R")


def group_answers(
    rows: Iterable[R], key: Callable[[R], AnswerKey]
) -> dict[AnswerKey, list[R]]:
    """``rows`` grouped by the answer they belong to, each in input order.

    Every view that marks or counts the counted verdict groups through here, so
    the figures, the question list and the export agree on it.
    """
    groups: dict[AnswerKey, list[R]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return groups


class _Judged(Protocol):
    judge_model: str


T = TypeVar("T", bound=_Judged)


@dataclass(frozen=True, slots=True)
class Picked(Generic[T]):
    """The rows that decide one answer's verdict."""

    counted: T | None
    judged: T | None
    override: T | None


def pick(rows: Sequence[T], panel: Sequence[str]) -> Picked[T]:
    """The counted verdict among one answer's rows, oldest first.

    ``panel`` is the judges in precedence order, primary first; a judge not in
    it ranks after it, by first appearance.
    """
    freshest: dict[str, T] = {}
    override: T | None = None
    for row in rows:
        if row.judge_model == OWNER_OVERRIDE:
            override = row
        else:
            freshest[row.judge_model] = row
    judged: T | None = None
    for judge in panel:
        if judge in freshest:
            judged = freshest[judge]
            break
    else:
        if freshest:
            judged = next(iter(freshest.values()))
    return Picked(counted=override or judged, judged=judged, override=override)


def judge_order(
    seen: Iterable[str], primary: str | None, panel: Sequence[str]
) -> list[str]:
    """The judges that graded: the primary, then ``panel`` order, then by first
    appearance."""
    seen_list = [j for j in dict.fromkeys(seen) if j and j != OWNER_OVERRIDE]
    ordered = [j for j in panel if j in seen_list]
    ordered += [j for j in seen_list if j not in ordered]
    if primary in ordered:
        ordered.remove(primary)
        ordered.insert(0, primary)
    return ordered


def _job_judges(session: Session, job_id: str) -> list[str]:
    """The judges that graded this job, by first verdict."""
    first = func.min(Result.created_at)
    return list(
        session.execute(
            select(Result.judge_model)
            .join(Run, Run.id == Result.run_id)
            .where(
                Run.job_id == job_id,
                Result.judge_model.not_in(["", OWNER_OVERRIDE]),
            )
            .group_by(Result.judge_model)
            .order_by(first, Result.judge_model)
        ).scalars()
    )


def primary_judge(session: Session, job: Job, *, configured: Panel = ()) -> str | None:
    """The judge whose verdict counts for this job.

    The first judge of the job's own panel that graded it; else the one
    frozen in ``params``; else one is chosen and, for a finished job, frozen:
    the first configured judge that graded it, else the first to grade.
    """
    seen = _job_judges(session, job.id)
    for judge in job_panel(job):
        if judge in seen:
            return judge
    params = dict(job.params or {})
    frozen = params.get(PRIMARY_JUDGE)
    if isinstance(frozen, str) and frozen:
        return frozen
    if not seen:
        return None
    chosen = next((j for j in resolve_panel(configured) if j in seen), seen[0])
    if is_finished(job):
        job.params = {**params, PRIMARY_JUDGE: chosen}
    return chosen
