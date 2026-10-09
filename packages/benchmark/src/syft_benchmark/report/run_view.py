"""The figures of one run (one job): the runs list, the run report, its questions.

One aggregation feeds the runs list, the run report, the summary document and
the job-scoped card, so the same run never shows two sets of numbers.

The question set of a run is every ``qa_id`` with a result under the job,
whatever the pair's status is now. The counted verdict of an answer (model x
arm x block x question) is the latest owner override, else the freshest verdict
of the job's primary judge (``primary_judge``, fixed per job), else the
freshest verdict of the next judge in panel order.
Only ``closed_book`` ("alone") and ``model_with_context`` ("with") count.
``pending`` and ``technical`` never enter a rate. Trick questions feed only the
trick check. Excluded questions are left out of every figure.

A finished job's figures are cached in ``run_aggregates`` under
``AGGREGATE_VERSION``; an in-progress job is always computed afresh.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Generic, Protocol, TypeVar

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    JobState,
    ManualStatusPriority,
    PairStatus,
    Settings,
    StatusReason,
    Verdict,
    get_settings,
)
from syft_benchmark.db.models import (
    Job,
    QaPair,
    Result,
    Run,
    RunAggregate,
    RunExclusion,
)
from syft_benchmark.db.session import session_scope
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.question_order import pair_order
from syft_benchmark.report.metrics import accuracy_by_temperature, held_by_round
from syft_benchmark.runs.gate import passes
from syft_benchmark.runs.judge import ERROR_PREFIX, is_technical
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE

# Bump on any change to what the payload holds or how it is computed: cached
# rows of another version are recomputed on the next read.
AGGREGATE_VERSION = 7

TRICK_GENERATOR = "unanswerable_property"

_REGISTRY_ORDER = {name: i for i, name in enumerate(GENERATORS)}


def generator_order(generator: str) -> tuple[int, str]:
    """Registry order, the one the console uses; unknown generators last."""
    return (_REGISTRY_ORDER.get(generator, len(_REGISTRY_ORDER)), generator)


# The configured judges, primary first, or how to get them: only a
# computation needs them, a cached read does not.
Panel = Sequence[str] | Callable[[], Sequence[str]]


ALONE = "alone"
WITH = "with"
ARM_OF: dict[str, str] = {
    ContextMode.CLOSED_BOOK.value: ALONE,
    ContextMode.MODEL_WITH_CONTEXT.value: WITH,
}
GROUPS = ("fixed", "either", "still", "worse")
OUTCOMES = frozenset(
    {
        Verdict.CORRECT.value,
        Verdict.ABSTAIN.value,
        Verdict.HALLUCINATE.value,
        Verdict.WEB_SOURCED.value,
    }
)
TECHNICAL = Verdict.TECHNICAL.value
CORRECT = Verdict.CORRECT.value
ABSTAIN = Verdict.ABSTAIN.value
HALLUCINATE = Verdict.HALLUCINATE.value
PENDING = Verdict.PENDING.value
WEB_SOURCED = Verdict.WEB_SOURCED.value
ACTIVE_STATES = (JobState.QUEUED.value, JobState.RUNNING.value)
REMOVED_STATUSES = (PairStatus.REJECTED.value, PairStatus.RETIRED.value)


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


def verdict_of(verdict: str, answer: str) -> str:
    """The stored verdict, with failed calls of any vintage read as technical."""
    return TECHNICAL if is_technical(verdict, answer or "") else verdict


def group_of(alone: str | None, with_: str | None) -> str | None:
    """Where a question lands when both arms have an outcome."""
    if alone not in OUTCOMES or with_ not in OUTCOMES:
        return None
    right_alone = alone == CORRECT
    right_with = with_ == CORRECT
    if right_with:
        return "either" if right_alone else "fixed"
    return "worse" if right_alone else "still"


def rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def lift(rate_alone: float | None, rate_with: float | None) -> int | None:
    """Points gained with the data, rounded to a whole point."""
    if rate_alone is None or rate_with is None:
        return None
    return round((rate_with - rate_alone) * 100)


@dataclass(slots=True)
class _Row:
    id: str
    qa_id: str
    verdict: str
    judge_model: str
    retrieval_hit: bool | None
    arm: str
    block: str
    model: str
    denial: dict[str, Any] | None
    repeats: dict[str, Any] | None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def is_finished(job: Job) -> bool:
    return job.state not in ACTIVE_STATES


def configured_panel(settings: Settings) -> list[str]:
    """The judges as configured, primary first."""
    return list(dict.fromkeys(settings.judge_models or [settings.judge_model]))


# Keys of the judging snapshot a job carries in ``jobs.params``.
JUDGE_PANEL = "judge_panel"
JUDGE_POLICY = "judge_policy"
PRIMARY_JUDGE = "primary_judge"
# The web check gate the launch asked through.
WEB_CHECK_MODEL = "web_check_model"
WEB_CHECK_JUDGE = "web_check_judge"
MANUAL_PRIORITY = "manual_status_priority"
# What the job spent: {spend_before, spend_after, usd, usd_calls, total_usd,
# by_role} (report API, "Cost and time").
COST = "cost"
# The build per kind (``pipeline.KindStats.as_dict``).
GENERATION = "generation"
# Where the job's time went (``runs.timing``; report API, "Timing").
TIMING = "timing"
SNAPSHOT_KEYS = frozenset(
    {
        JUDGE_PANEL,
        JUDGE_POLICY,
        PRIMARY_JUDGE,
        WEB_CHECK_MODEL,
        WEB_CHECK_JUDGE,
        MANUAL_PRIORITY,
        COST,
        GENERATION,
        TIMING,
    }
)


def record_generation(
    job_id: str, kinds: list[dict[str, Any]], settings: Settings | None = None
) -> None:
    """Keep the job's per-kind build stats in its params."""
    with session_scope(settings) as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.params = {**(job.params or {}), GENERATION: kinds}


def generation_of(job: Job) -> list[dict[str, Any]]:
    """The job's per-kind build stats; empty — it built nothing (or before they
    were kept)."""
    kinds = (job.params or {}).get(GENERATION)
    return [k for k in kinds if isinstance(k, dict)] if isinstance(kinds, list) else []


def web_check_judge(settings: Settings) -> str:
    """The web check judge: ``filter_judge_model``, else Judge 1; empty without
    a web check model."""
    if not settings.filter_model:
        return ""
    if settings.filter_judge_model:
        return settings.filter_judge_model
    panel = configured_panel(settings)
    return panel[0] if panel else ""


def judging_snapshot(settings: Settings) -> dict[str, Any]:
    """The judging and the web check gate a launch goes by, for ``jobs.params``."""
    return {
        JUDGE_PANEL: configured_panel(settings),
        JUDGE_POLICY: settings.judge_policy.value,
        WEB_CHECK_MODEL: settings.filter_model or "",
        WEB_CHECK_JUDGE: web_check_judge(settings),
        MANUAL_PRIORITY: settings.manual_status_priority.value,
    }


def how_tested(job: Job) -> dict[str, Any]:
    """The job's web check model and judge, and what it spent (``method``)."""
    params = job.params or {}
    cost = params.get(COST)
    return {
        WEB_CHECK_MODEL: str(params.get(WEB_CHECK_MODEL) or "") or None,
        WEB_CHECK_JUDGE: str(params.get(WEB_CHECK_JUDGE) or "") or None,
        COST: _cost(cost) if isinstance(cost, dict) else None,
    }


def _cost(cost: dict[str, Any]) -> dict[str, Any]:
    """The stored cost; ``total_usd`` and ``by_role`` null for older jobs."""
    by_role = cost.get("by_role")
    return {
        **cost,
        "total_usd": cost.get("total_usd"),
        "by_role": dict(by_role) if isinstance(by_role, dict) else None,
    }


def job_times(job: Job) -> dict[str, Any]:
    """When the job started and finished, and how long it took (seconds);
    null while unknown."""
    took = (
        round((job.finished_at - job.started_at).total_seconds(), 2)
        if job.started_at is not None and job.finished_at is not None
        else None
    )
    return {
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
        "duration_s": took,
    }


def timing_of(job: Job) -> dict[str, Any] | None:
    """The job's phase, pass and call timings; None — not kept (yet)."""
    timing = (job.params or {}).get(TIMING)
    return dict(timing) if isinstance(timing, dict) else None


def job_gate(job: Job) -> Settings | None:
    """The web check gate of the job's launch; None for a job without a snapshot."""
    params = job.params or {}
    if WEB_CHECK_MODEL not in params:
        return None
    return Settings.model_construct(
        filter_model=str(params.get(WEB_CHECK_MODEL) or "") or None,
        manual_status_priority=ManualStatusPriority(
            params.get(MANUAL_PRIORITY) or ManualStatusPriority.FILTER.value
        ),
    )


def job_panel(job: Job) -> list[str]:
    """The judges configured when the job ran, primary first; empty if unknown."""
    panel = (job.params or {}).get(JUDGE_PANEL)
    if not isinstance(panel, list):
        return []
    return [j for j in dict.fromkeys(panel) if isinstance(j, str) and j]


def judges_seen(session: Session, job_id: str) -> list[str]:
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
    frozen in ``params``; else it is frozen now (a finished job only): the
    card's instrument judge if it graded the job, else the first configured
    judge that did, else the first to grade.
    """
    seen = judges_seen(session, job.id)
    for judge in job_panel(job):
        if judge in seen:
            return judge
    params = dict(job.params or {})
    frozen = params.get(PRIMARY_JUDGE)
    if isinstance(frozen, str) and frozen:
        return frozen
    if not seen:
        return None
    card = job.card if isinstance(job.card, dict) else {}
    instrument = card.get("instrument")
    named = instrument.get("judge") if isinstance(instrument, dict) else None
    if named in seen:
        chosen = str(named)
    else:
        if callable(configured):
            configured = configured()
        chosen = next((j for j in configured if j in seen), seen[0])
    if is_finished(job):
        job.params = {**params, PRIMARY_JUDGE: chosen}
    return chosen


def judge_order(
    seen: Iterable[str], primary: str | None, panel: Sequence[str]
) -> list[str]:
    """The judges that graded this run: the primary, then ``panel`` order,
    then by first appearance."""
    seen_list = [j for j in dict.fromkeys(seen) if j and j != OWNER_OVERRIDE]
    ordered = [j for j in panel if j in seen_list]
    ordered += [j for j in seen_list if j not in ordered]
    if primary in ordered:
        ordered.remove(primary)
        ordered.insert(0, primary)
    return ordered


# --- computing ------------------------------------------------------------


def _load_rows(session: Session, job_id: str) -> list[_Row]:
    """The job's answers in the two counted arms, oldest first, only the
    columns the figures need."""
    stmt = (
        select(
            Result.id,
            Result.qa_id,
            Result.verdict,
            Result.answer.op("~")(rf"^\s*{ERROR_PREFIX}"),
            Result.judge_model,
            Result.retrieval_hit,
            Run.context_mode,
            Run.block,
            Run.model,
            Result.extra["denial"].op("-")("log"),
            Result.extra["monte_carlo"].op("-")("log"),
        )
        .join(Run, Run.id == Result.run_id)
        .where(Run.job_id == job_id, Run.context_mode.in_(list(ARM_OF)))
        .order_by(Result.created_at, Result.id)
    )
    return [
        _Row(
            id=rid,
            qa_id=qa_id,
            verdict=TECHNICAL if failed or verdict == TECHNICAL else verdict,
            judge_model=judge or "",
            retrieval_hit=hit,
            arm=ARM_OF[mode],
            block=block,
            model=model or "",
            denial=denial if isinstance(denial, dict) else None,
            repeats=repeats if isinstance(repeats, dict) else None,
        )
        for (
            rid,
            qa_id,
            verdict,
            failed,
            judge,
            hit,
            mode,
            block,
            model,
            denial,
            repeats,
        ) in session.connection().execute(stmt).all()
    ]


def took_part(session: Session, job_id: str, qa_id: str) -> bool:
    """Whether the question has any result under the job."""
    found = session.execute(
        select(Result.id)
        .join(Run, Run.id == Result.run_id)
        .where(Run.job_id == job_id, Result.qa_id == qa_id)
        .limit(1)
    ).first()
    return found is not None


def question_set_query(job_id: str) -> Any:
    """qa_id and first appearance of every question with a result under the job."""
    return (
        select(Result.qa_id, func.min(Result.created_at).label("first_at"))
        .join(Run, Run.id == Result.run_id)
        .where(Run.job_id == job_id)
        .group_by(Result.qa_id)
        .subquery()
    )


def _funnel(
    session: Session,
    job: Job,
    took_part: set[str],
    asked: int,
    trick: int,
) -> dict[str, Any]:
    """What the job wrote, what of it never took part and why, what was asked.

    ``unchecked``: kept questions that were not asked because they had not
    passed the web check (None for a job without a gate snapshot).
    """
    gate = job_gate(job)
    rows = session.connection().execute(
        select(
            QaPair.id,
            QaPair.status,
            QaPair.status_reason,
            QaPair.task_type,
            QaPair.meta,
        ).where(QaPair.job_id == job.id, QaPair.generator != TRICK_GENERATOR)
    )
    written = 0
    unchecked = 0
    removed: dict[str, int] = {}
    for qa, status, reason, task_type, meta in rows:
        written += 1
        if qa in took_part:
            continue
        if status not in REMOVED_STATUSES:
            probe = QaPair(id=qa, task_type=task_type, meta=meta or {})
            if gate is not None and not passes(probe, gate):
                unchecked += 1
            continue
        key = reason or StatusReason.OTHER.value
        removed[key] = removed.get(key, 0) + 1
    return {
        "written": written or None,
        "removed": removed,
        "removed_total": sum(removed.values()) if written else None,
        "unchecked": unchecked if gate is not None and written else None,
        "asked": asked,
        "trick": trick,
    }


def _tally(verdicts: Iterable[str | None]) -> dict[str, int]:
    counts = Counter(v for v in verdicts if v)
    graded = sum(counts[v] for v in OUTCOMES)
    return {
        "correct": counts[CORRECT],
        "abstain": counts[ABSTAIN],
        "hallucinate": counts[HALLUCINATE],
        "web_sourced": counts[WEB_SOURCED],
        "pending": counts[PENDING],
        "technical": counts[TECHNICAL],
        "graded": graded,
    }


def compute(session: Session, job: Job, *, configured: Panel = ()) -> dict[str, Any]:
    """The whole payload of one job: summary, report and the question index."""
    if callable(configured):
        configured = configured()
    first_seen = question_set_query(job.id)
    pairs = (
        session.connection()
        .execute(
            select(
                QaPair.id,
                QaPair.generator,
                QaPair.document_title,
                QaPair.doc_id,
                QaPair.model,
            )
            .join(first_seen, first_seen.c.qa_id == QaPair.id)
            # The question order (report API, "Question order").
            .order_by(*pair_order(QaPair.generator, QaPair.created_at, QaPair.id))
        )
        .all()
    )
    excluded = set(
        session.execute(
            select(RunExclusion.qa_id).where(RunExclusion.job_id == job.id)
        ).scalars()
    )
    run_params = session.execute(
        select(
            Run.context_mode,
            Run.profile,
            Run.params["context_docs"],
            Run.params["denial_rounds"],
            Run.block,
            Run.params["monte_carlo_trials"],
            Run.params["monte_carlo_temperatures"],
        )
        .where(Run.job_id == job.id, Run.judge_model != OWNER_OVERRIDE)
        .distinct()
    ).all()
    rows = _load_rows(session, job.id)

    generator_of = {qa: gen for qa, gen, *_ in pairs}
    trick_ids = {qa for qa, gen in generator_of.items() if gen == TRICK_GENERATOR}
    main_ids = [qa for qa, *_ in pairs if qa not in trick_ids]
    counted_main = {qa for qa in main_ids if qa not in excluded}
    counted_trick = trick_ids - excluded

    primary = primary_judge(session, job, configured=configured)
    judges = judge_order(
        (r.judge_model for r in rows), primary, job_panel(job) or configured
    )
    panel = [*judges, ""]

    by_answer: dict[tuple[str, str, str, str], list[_Row]] = defaultdict(list)
    for row in rows:
        by_answer[(row.model, row.arm, row.block, row.qa_id)].append(row)

    models = sorted(
        {r.model for r in rows if r.model and r.block == EvalBlock.DIRECT.value}
    )
    # (model, arm, qa) -> counted verdict; (model, qa) -> overridden
    direct: dict[tuple[str, str, str], str] = {}
    overridden: set[tuple[str, str]] = set()
    retrieval: dict[tuple[str, str], bool | None] = {}
    blocks: dict[tuple[str, str], list[_Row]] = defaultdict(list)
    agreement: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (model, arm, block, qa), answer_rows in by_answer.items():
        chosen = pick(answer_rows, panel)
        counted = chosen.counted
        if counted is None:
            continue
        if block == EvalBlock.DIRECT.value:
            direct[(model, arm, qa)] = counted.verdict
            if chosen.override is not None:
                overridden.add((model, qa))
            if arm == WITH:
                retrieval[(model, qa)] = counted.retrieval_hit
            if qa in counted_main:
                graded = {
                    r.judge_model: r.verdict
                    for r in answer_rows
                    if r.judge_model not in ("", OWNER_OVERRIDE)
                }
                outcomes = [v for v in graded.values() if v in OUTCOMES]
                if len(outcomes) >= 2:
                    agreement[model][0] += 1
                    agreement[model][1] += len(set(outcomes)) == 1
        elif arm == WITH and qa in counted_main and counted.verdict in OUTCOMES:
            blocks[(model, block)].append(counted)

    denial_limit_param = max(
        (int(p[3]) for p in run_params if isinstance(p[3], int)), default=None
    )
    context_docs = max(
        (int(p[2]) for p in run_params if isinstance(p[2], int)), default=None
    )
    profile = next((p[1] for p in run_params if p[1]), None)

    reports: list[dict[str, Any]] = []
    for model in models:
        alone = {qa: direct.get((model, ALONE, qa)) for qa in counted_main}
        with_ = {qa: direct.get((model, WITH, qa)) for qa in counted_main}
        asked_ids = [
            qa
            for qa in main_ids
            if qa in counted_main and (alone[qa] is not None or with_[qa] is not None)
        ]
        tally = {
            ALONE: _tally(alone[qa] for qa in asked_ids),
            WITH: _tally(with_[qa] for qa in asked_ids),
        }
        figures = _figures(model, len(asked_ids), tally)

        groups = dict.fromkeys(GROUPS, 0)
        kinds: dict[str, Counter[str]] = defaultdict(Counter)
        for qa in asked_ids:
            g = group_of(alone[qa], with_[qa])
            if g:
                groups[g] += 1
            kind = kinds[generator_of[qa]]
            kind["asked"] += 1
            kind["graded_alone"] += alone[qa] in OUTCOMES
            kind["graded_with"] += with_[qa] in OUTCOMES
            kind["right_alone"] += alone[qa] == CORRECT
            kind["right_with"] += with_[qa] == CORRECT
            kind["web_alone"] += alone[qa] == WEB_SOURCED
            kind["web_with"] += with_[qa] == WEB_SOURCED
        kind_rows: list[dict[str, Any]] = []
        for generator, k in kinds.items():
            r_alone = rate(k["right_alone"], k["graded_alone"])
            r_with = rate(k["right_with"], k["graded_with"])
            kind_rows.append(
                {
                    "generator": generator,
                    "asked": k["asked"],
                    "graded_alone": k["graded_alone"],
                    "graded_with": k["graded_with"],
                    "right_alone": k["right_alone"],
                    "right_with": k["right_with"],
                    "rate_alone": r_alone,
                    "rate_with": r_with,
                    "lift": lift(r_alone, r_with),
                    "web_alone": k["web_alone"],
                    "web_with": k["web_with"],
                }
            )
        kind_rows.sort(key=lambda k: generator_order(k["generator"]))

        reports.append(
            {
                **figures,
                "tally": tally,
                "kinds": kind_rows,
                "groups": groups,
                "checks": _checks(
                    model,
                    asked_ids,
                    counted_trick,
                    direct,
                    retrieval,
                    blocks,
                    agreement.get(model, [0, 0]),
                    denial_limit_param,
                ),
            }
        )

    reports.sort(
        key=lambda m: (m["rate_with"] is None, -(m["rate_with"] or 0), m["model"])
    )
    summary_models = [_figures_only(m) for m in reports]
    lifts = [m["lift"] for m in reports if m["lift"] is not None]

    counted_pairs = [p for p in pairs if p[0] in counted_main]
    documents = {doc for _, _, _, doc, _ in counted_pairs if doc}
    generator_model = Counter(m for *_, m in counted_pairs if m).most_common(1)
    card = job.card if isinstance(job.card, dict) else {}
    dataset = card.get("dataset") if isinstance(card.get("dataset"), dict) else {}
    window_days = dataset.get("window_days") if dataset else None
    window_days = int(window_days) if isinstance(window_days, int) else None

    run = {
        "job_id": job.id,
        "created_at": _iso(job.created_at),
        "finished_at": _iso(job.finished_at),
        "trigger": job.trigger,
        "window_days": window_days,
        "articles": len(documents) if pairs else None,
        "questions": len(counted_main) if pairs else None,
        "models": summary_models,
        "lift_lo": min(lifts) if lifts else None,
        "lift_hi": max(lifts) if lifts else None,
    }
    since = (
        job.created_at - timedelta(days=window_days)
        if window_days and job.created_at
        else None
    )
    method = {
        "articles_from": _iso(since),
        "articles_to": _iso(job.created_at) if since else None,
        "generator_model": generator_model[0][0] if generator_model else None,
        "kinds": sorted(
            {gen for gen in generator_of.values() if gen}, key=generator_order
        ),
        "trick": len(counted_trick),
        "context_docs": context_docs,
        "judges": judges,
        "profile": profile,
        "next_run_at": None,
        "denial_rounds": _denial_rounds(rows, run_params),
        "repeats": _repeats(rows, run_params),
    }

    titles = {qa: title for qa, _, title, _, _ in pairs}
    index = []
    for n, qa in enumerate(main_ids, start=1):
        verdicts = {}
        for model in models:
            a = direct.get((model, ALONE, qa))
            w = direct.get((model, WITH, qa))
            if a is None and w is None:
                continue
            verdicts[model] = [a, w, group_of(a, w), (model, qa) in overridden]
        index.append(
            {
                "qa_id": qa,
                "n": n,
                "generator": generator_of[qa],
                "title": titles[qa] or "",
                "excluded": qa in excluded,
                "models": verdicts,
            }
        )

    return {
        "run": run,
        "funnel": _funnel(
            session, job, set(generator_of), len(counted_main), len(counted_trick)
        ),
        "models": reports,
        "judges": judges,
        "method": method,
        "questions": index,
    }


def _denial_rounds(rows: Sequence[_Row], run_params: Sequence[Any]) -> int | None:
    """The challenge limit of the run's denial_loop block; None — it did not run."""
    seen = [
        int(r.denial.get("limit") or 0)
        for r in rows
        if r.block == EvalBlock.DENIAL_LOOP.value and r.denial
    ]
    if max(seen, default=0):
        return max(seen)
    params = [
        int(p[3])
        for p in run_params
        if p[4] == EvalBlock.DENIAL_LOOP.value and isinstance(p[3], int)
    ]
    return max(params, default=None)


def _repeats(rows: Sequence[_Row], run_params: Sequence[Any]) -> dict[str, Any] | None:
    """Repeats per temperature and the temperatures of the run's monte_carlo
    block; None — it did not run."""
    mc = [p for p in run_params if p[4] == EvalBlock.MONTE_CARLO.value]
    trials = max((int(p[5]) for p in mc if isinstance(p[5], int)), default=0)
    temps = {
        float(t)
        for p in mc
        if isinstance(p[6], list)
        for t in p[6]
        if isinstance(t, int | float)
    }
    if trials and temps:
        return {"trials": trials, "temperatures": sorted(temps)}
    seen = [
        r.repeats
        for r in rows
        if r.block == EvalBlock.MONTE_CARLO.value
        and r.repeats
        and r.repeats.get("trials")
    ]
    if not seen:
        return None
    by_temp = [m.get("by_temperature") or {} for m in seen]
    temps = {float(t) for bt in by_temp if isinstance(bt, dict) for t in bt}
    if not temps:
        return None
    per_temp = max(-(-int(m["trials"]) // len(temps)) for m in seen)
    return {"trials": per_temp, "temperatures": sorted(temps)}


def _figures(
    model: str, asked: int, tally: dict[str, dict[str, int]]
) -> dict[str, Any]:
    alone, with_ = tally[ALONE], tally[WITH]
    rate_alone = rate(alone["correct"], alone["graded"])
    rate_with = rate(with_["correct"], with_["graded"])
    return {
        "model": model,
        "asked": asked,
        "graded_alone": alone["graded"],
        "graded_with": with_["graded"],
        "right_alone": alone["correct"],
        "right_with": with_["correct"],
        "rate_alone": rate_alone,
        "rate_with": rate_with,
        "lift": lift(rate_alone, rate_with),
        "made_up_alone": rate(alone["hallucinate"], alone["graded"]),
        "made_up_with": rate(with_["hallucinate"], with_["graded"]),
        "pending": alone["pending"] + with_["pending"],
        "technical": alone["technical"] + with_["technical"],
    }


FIGURE_KEYS = (
    "model",
    "asked",
    "graded_alone",
    "graded_with",
    "right_alone",
    "right_with",
    "rate_alone",
    "rate_with",
    "lift",
    "made_up_alone",
    "made_up_with",
    "pending",
    "technical",
)


def _figures_only(report: dict[str, Any]) -> dict[str, Any]:
    return {key: report[key] for key in FIGURE_KEYS}


def _checks(
    model: str,
    asked_ids: Sequence[str],
    trick_ids: set[str],
    direct: dict[tuple[str, str, str], str],
    retrieval: dict[tuple[str, str], bool | None],
    blocks: dict[tuple[str, str], list[_Row]],
    agreement: Sequence[int],
    denial_limit_param: int | None,
) -> dict[str, Any]:
    pressed = [
        r.denial
        for r in blocks.get((model, EvalBlock.DENIAL_LOOP.value), [])
        if r.denial
    ]
    limit = max((int(d.get("limit") or 0) for d in pressed), default=0) or (
        denial_limit_param or 0
    )
    held = held_by_round(pressed, limit) if pressed else []
    kept = sum(1 for d in pressed if not d.get("flipped"))

    repeats = [
        r.repeats
        for r in blocks.get((model, EvalBlock.MONTE_CARLO.value), [])
        if r.repeats and r.repeats.get("trials")
    ]
    same = (
        round(sum(float(m.get("consistency") or 0) for m in repeats) / len(repeats), 4)
        if repeats
        else None
    )
    temperatures = accuracy_by_temperature(
        m.get("by_temperature") or {} for m in repeats
    )

    def trick(arm: str) -> tuple[int, int, int]:
        """Graded, made up (anything but abstaining or the web), from the web."""
        graded = [direct.get((model, arm, qa)) for qa in trick_ids]
        graded = [v for v in graded if v in OUTCOMES]
        web = sum(1 for v in graded if v == WEB_SOURCED)
        made_up = sum(1 for v in graded if v not in (ABSTAIN, WEB_SOURCED))
        return len(graded), made_up, web

    trick_asked, trick_answered, trick_web = trick(WITH)
    trick_alone_asked, trick_alone_answered, trick_alone_web = trick(ALONE)

    hits = [retrieval.get((model, qa)) for qa in asked_ids]
    searched = [h for h in hits if h is not None]
    found = sum(1 for h in searched if h)
    answers, agreed = int(agreement[0]), int(agreement[1])
    return {
        "challenged": len(pressed),
        "denial_limit": (limit or None) if pressed else None,
        "held_by_round": held,
        "kept_right": rate(kept, len(pressed)),
        "repeated": len(repeats),
        "same_answer": same,
        "by_temperature": [
            {"t": float(t), "accuracy": acc} for t, acc in temperatures.items()
        ],
        "trick_asked": trick_asked,
        "trick_answered": trick_answered,
        "trick_alone_asked": trick_alone_asked,
        "trick_alone_answered": trick_alone_answered,
        "trick_web": trick_web,
        "trick_alone_web": trick_alone_web,
        "searched": len(searched),
        "search_found": rate(found, len(searched)),
        "missed": len(searched) - found,
        "answers": answers,
        "judges_agreed": agreed,
        "agreement": rate(agreed, answers),
    }


# --- the cache ------------------------------------------------------------


def _store(session: Session, job_id: str, payload: dict[str, Any]) -> None:
    session.execute(
        insert(RunAggregate)
        .values(job_id=job_id, version=AGGREGATE_VERSION, payload=payload)
        .on_conflict_do_update(
            index_elements=[RunAggregate.job_id],
            set_={
                "version": AGGREGATE_VERSION,
                "payload": payload,
                "computed_at": func.now(),
            },
        )
    )


def aggregate(session: Session, job: Job, *, configured: Panel = ()) -> dict[str, Any]:
    """The job's full payload: cached for a finished job, else computed."""
    if is_finished(job):
        row = session.execute(
            select(RunAggregate.payload).where(
                RunAggregate.job_id == job.id,
                RunAggregate.version == AGGREGATE_VERSION,
            )
        ).scalar_one_or_none()
        if row is not None:
            return dict(row)
    payload = compute(session, job, configured=configured)
    if is_finished(job):
        _store(session, job.id, payload)
    return payload


def warm(job_id: str, settings: Settings | None = None) -> None:
    """Compute and cache a finished job's figures, so the first read is fast."""
    try:
        with session_scope(settings) as session:
            job = session.get(Job, job_id)
            if job is None or not is_finished(job):
                return
            if session.execute(
                select(Run.id).where(Run.job_id == job_id).limit(1)
            ).first():
                aggregate(
                    session,
                    job,
                    configured=configured_panel(settings or get_settings()),
                )
    except Exception:  # noqa: BLE001 - a cold cache is only slower, never wrong
        logger.exception(f"job {job_id}: its figures were not precomputed")


def aggregate_parts(
    session: Session, job: Job, *parts: str, configured: Panel = ()
) -> list[Any]:
    """Top-level keys of the payload, without loading the rest when cached."""
    if is_finished(job):
        found = session.execute(
            select(*(RunAggregate.payload[part] for part in parts)).where(
                RunAggregate.job_id == job.id,
                RunAggregate.version == AGGREGATE_VERSION,
            )
        ).first()
        if found is not None:
            return list(found)
    payload = aggregate(session, job, configured=configured)
    return [payload[part] for part in parts]


def report_part(
    session: Session, job: Job, *, configured: Panel = ()
) -> dict[str, Any]:
    """The payload without the question index."""
    if is_finished(job):
        found = session.execute(
            select(RunAggregate.payload.op("-")("questions")).where(
                RunAggregate.job_id == job.id,
                RunAggregate.version == AGGREGATE_VERSION,
            )
        ).first()
        if found is not None:
            return dict(found[0])
    payload = dict(aggregate(session, job, configured=configured))
    payload.pop("questions", None)
    return payload


def summaries(
    session: Session, jobs: Sequence[Job], *, configured: Panel = ()
) -> dict[str, dict[str, Any]]:
    """The run summary of each job, computing the ones not cached."""
    ids = [job.id for job in jobs if is_finished(job)]
    cached: dict[str, dict[str, Any]] = {}
    if ids:
        cached = {
            job_id: run
            for job_id, run in session.execute(
                select(RunAggregate.job_id, RunAggregate.payload["run"]).where(
                    RunAggregate.job_id.in_(ids),
                    RunAggregate.version == AGGREGATE_VERSION,
                )
            )
        }
    out: dict[str, dict[str, Any]] = {}
    for job in jobs:
        out[job.id] = (
            cached.get(job.id) or aggregate(session, job, configured=configured)["run"]
        )
    return out


# --- the card -------------------------------------------------------------


def card_models(report: dict[str, Any]) -> dict[str, Any]:
    """One model's row of the card, from this module's figures."""
    tally = report["tally"][WITH]
    attempted = tally["hallucinate"] + tally["correct"]
    checks = report["checks"]
    made_up = (report["made_up_alone"], report["made_up_with"])
    return {
        "model": report["model"],
        "samples": report["graded_with"],
        "accuracy": report["rate_with"],
        "fabrication": rate(checks["trick_answered"], checks["trick_asked"]),
        "lmi": rate(tally["hallucinate"], attempted),
        "context_gain": (
            round(made_up[1] - made_up[0], 4) if None not in made_up else None
        ),
        "closed_accuracy": report["rate_alone"],
    }


def card_outdated(card: dict[str, Any] | None, run: dict[str, Any]) -> bool:
    """Whether the card's per-model figures differ from the live ones."""
    if not isinstance(card, dict) or not isinstance(card.get("models"), list):
        return False
    stored = {str(m.get("model")): m for m in card["models"] if isinstance(m, dict)}
    live = {m["model"]: m for m in run.get("models") or [] if m["graded_with"]}
    if set(stored) != set(live):
        return True

    def differs(a: Any, b: Any) -> bool:
        if a is None or b is None:
            return a is not b
        return abs(float(a) - float(b)) > 5e-5

    for name, figures in live.items():
        row = stored[name]
        if int(row.get("samples") or 0) != figures["graded_with"]:
            return True
        if differs(row.get("accuracy"), figures["rate_with"]):
            return True
        if differs(row.get("closed_accuracy"), figures["rate_alone"]):
            return True
    return False
