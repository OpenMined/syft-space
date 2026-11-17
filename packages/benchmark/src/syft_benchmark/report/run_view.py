"""The figures of one run (one job): the runs list, the run report, its questions.

One aggregation feeds the runs list, the run report and the summary document,
so the same run never shows two sets of numbers.

The question set of a run is every ``qa_id`` with a result under the job,
whatever the pair's status is now. Each answer (model x arm x block x question)
is read through its counted verdict (``counted.pick``, the job's primary judge).
Only ``closed_book`` ("alone") and ``model_with_context`` ("with") count.
``pending`` and ``technical`` never enter a rate. Trick questions feed only the
trick check.

A finished job's figures are cached in ``run_aggregates`` under
``AGGREGATE_VERSION``; an in-progress job is always computed afresh.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, NamedTuple

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
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
)
from syft_benchmark.db.session import session_scope
from syft_benchmark.generation.article_dates import DATE_KEY
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.question_order import pair_order
from syft_benchmark.report.counted import (
    OUTCOMES,
    AnswerKey,
    Panel,
    group_answers,
    judge_order,
    pick,
    primary_judge,
    resolve_panel,
)
from syft_benchmark.report.job_params import (
    configured_panel,
    generation_of,
    is_finished,
    iso,
    job_gate,
    job_panel,
    window_days_of,
)
from syft_benchmark.report.metrics import accuracy_by_temperature, held_by_round
from syft_benchmark.runs.gate import passes
from syft_benchmark.runs.judge import ERROR_PREFIX
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE

# Bump on any change to what the payload holds or how it is computed: cached
# rows of another version are recomputed on the next read.
AGGREGATE_VERSION = 13

TRICK_GENERATOR = "unanswerable_property"

_REGISTRY_ORDER = {name: i for i, name in enumerate(GENERATORS)}


def generator_order(generator: str) -> tuple[int, str]:
    """Registry order, the one the console uses; unknown generators last."""
    return (_REGISTRY_ORDER.get(generator, len(_REGISTRY_ORDER)), generator)


ALONE = "alone"
WITH = "with"
ARM_OF: dict[str, str] = {
    ContextMode.CLOSED_BOOK.value: ALONE,
    ContextMode.MODEL_WITH_CONTEXT.value: WITH,
}
GROUPS = ("fixed", "either", "still", "worse")
TECHNICAL = Verdict.TECHNICAL.value
CORRECT = Verdict.CORRECT.value
ABSTAIN = Verdict.ABSTAIN.value
HALLUCINATE = Verdict.HALLUCINATE.value
PENDING = Verdict.PENDING.value
WEB_SOURCED = Verdict.WEB_SOURCED.value
INCOMPLETE = Verdict.INCOMPLETE.value
REMOVED_STATUSES = (PairStatus.REJECTED.value, PairStatus.RETIRED.value)


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
    qa_id: str
    verdict: str
    judge_model: str
    retrieval_hit: bool | None
    mode: str
    arm: str
    block: str
    model: str
    denial: dict[str, Any] | None
    repeats: dict[str, Any] | None


def _load_rows(session: Session, job_id: str) -> list[_Row]:
    """The job's answers in the two counted arms, oldest first, only the
    columns the figures need."""
    stmt = (
        select(
            Result.qa_id,
            Result.verdict,
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
            qa_id=qa_id,
            verdict=verdict,
            judge_model=judge or "",
            retrieval_hit=hit,
            mode=mode,
            arm=ARM_OF[mode],
            block=block,
            model=model or "",
            denial=denial if isinstance(denial, dict) else None,
            repeats=repeats if isinstance(repeats, dict) else None,
        )
        for (
            qa_id,
            verdict,
            judge,
            hit,
            mode,
            block,
            model,
            denial,
            repeats,
        ) in session.connection().execute(stmt).all()
    ]


def counting_judges(session: Session, job: Job, *, configured: Panel = ()) -> list[str]:
    """The job's judges in the order a verdict is counted by (``pick``): the
    primary, the panel, then by first verdict in the measured arms.

    Reads only each judge's first verdict, so a caller can count rows as the
    figures do without computing them.
    """
    configured = resolve_panel(configured)
    first = (
        select(Result.judge_model, Result.created_at, Result.id)
        .join(Run, Run.id == Result.run_id)
        .where(Run.job_id == job.id, Run.context_mode.in_(list(ARM_OF)))
        .distinct(Result.judge_model)
        .order_by(Result.judge_model, Result.created_at, Result.id)
        .subquery()
    )
    seen = session.scalars(
        select(first.c.judge_model).order_by(first.c.created_at, first.c.id)
    )
    primary = primary_judge(session, job, configured=configured)
    return judge_order(seen, primary, job_panel(job) or configured)


def _last_errors(session: Session, job_id: str) -> dict[str, str]:
    """model -> its latest failed answer text in the counted direct block."""
    stmt = (
        select(Run.model, Result.answer)
        .join(Run, Run.id == Result.run_id)
        .where(
            Run.job_id == job_id,
            Run.context_mode.in_(list(ARM_OF)),
            Run.block == EvalBlock.DIRECT.value,
            Result.answer.op("~")(rf"^\s*{ERROR_PREFIX}"),
        )
        .order_by(Result.created_at.desc(), Result.id.desc())
    )
    found: dict[str, str] = {}
    for model, answer in session.connection().execute(stmt).all():
        found.setdefault(model or "", answer or "")
    return found


# (marks in the error text, label, what happened). First match wins.
_FAILURES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("-> 402", "credit", "quota"),
        "Out of credits",
        "the provider key has no credits left",
    ),
    (("-> 401", "-> 403", "api key"), "Key refused", "the provider refused the key"),
    (
        ("-> 404", "valid model id", "no endpoints found"),
        "Unknown model",
        "the provider does not serve this model",
    ),
    (("-> 429", "rate limit"), "Rate limited", "the provider kept rate-limiting it"),
    (("timed out", "timeout"), "Timed out", "the model did not answer in time"),
    (("-> 400", "-> 422"), "Request refused", "the provider refused the request"),
)
_DETAIL_CAP = 160


def failure_of(answer: str, failed: int) -> dict[str, str]:
    """A short label and a one-sentence tooltip for a model's failed answers."""
    text = answer.strip().removeprefix(ERROR_PREFIX).strip()
    lowered = text.lower()
    label, what = "Call failed", "the call to the model failed"
    for marks, name, sentence in _FAILURES:
        if any(mark in lowered for mark in marks):
            label, what = name, sentence
            break
    said = re.sub(r"^.*?-> \d{3}:\s*", "", text)
    if len(said) > _DETAIL_CAP:
        said = said[: _DETAIL_CAP - 3] + "..."
    noun = "answer" if failed == 1 else "answers"
    tip = f"{failed} {noun} failed: {what}"
    return {"label": label, "detail": f"{tip} ({said})." if said else f"{tip}."}


def took_part(session: Session, job_id: str, qa_id: str) -> bool:
    """Whether the question has any result under the job."""
    found = session.execute(
        select(Result.id)
        .join(Run, Run.id == Result.run_id)
        .where(Run.job_id == job_id, Result.qa_id == qa_id)
        .limit(1)
    ).first()
    return found is not None


def _question_set_query(job_id: str) -> Any:
    """The qa_id of every question with a result under the job."""
    return (
        select(Result.qa_id)
        .join(Run, Run.id == Result.run_id)
        .where(Run.job_id == job_id)
        .group_by(Result.qa_id)
        .subquery()
    )


def _funnel(
    session: Session,
    job: Job,
    asked_ids: set[str],
    asked: int,
    trick: int,
) -> dict[str, Any]:
    """What the job wrote, what of it never took part and why, what was asked.

    ``asked_ids`` are the questions with a result under the job. ``unchecked``:
    kept questions that were not asked because they had not passed the web
    check (None for a job without a gate snapshot).
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
        if qa in asked_ids:
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


def _articles(
    session: Session, job: Job, asked_ids: Sequence[str], *, asked: bool
) -> dict[str, Any]:
    """The asked questions' articles and their real date range (UTC days), and
    the articles this job wrote questions from."""
    by_doc: dict[str, str | None] = {}
    if asked_ids:
        for doc, day in session.execute(
            select(QaPair.doc_id, QaPair.meta[DATE_KEY].astext).where(
                QaPair.id.in_(asked_ids)
            )
        ):
            if doc:
                by_doc[doc] = by_doc.get(doc) or day
    days = sorted(day for day in by_doc.values() if day)
    new = session.execute(
        select(func.count(func.distinct(QaPair.doc_id))).where(QaPair.job_id == job.id)
    ).scalar_one()
    return {
        "articles": len(by_doc) if asked else None,
        "articles_first": days[0] if days else None,
        "articles_last": days[-1] if days else None,
        "articles_dated": len(days) if asked else None,
        "articles_new": new if new or generation_of(job) else None,
    }


class _RunParams(NamedTuple):
    """The methodology of one of the job's runs, as its ``Run`` row records it."""

    mode: str
    profile: str | None
    context_docs: Any
    denial_rounds: Any
    block: str
    trials: Any
    temperatures: Any


def _run_params(session: Session, job_id: str) -> list[_RunParams]:
    """The distinct methodologies of the job's runs; owner overrides open none."""
    rows = session.execute(
        select(
            Run.context_mode,
            Run.profile,
            Run.params["context_docs"],
            Run.params["denial_rounds"],
            Run.block,
            Run.params["monte_carlo_trials"],
            Run.params["monte_carlo_temperatures"],
        )
        .where(Run.job_id == job_id, Run.judge_model != OWNER_OVERRIDE)
        .distinct()
    ).all()
    return [_RunParams(*row) for row in rows]


def _tally(verdicts: Iterable[str | None]) -> dict[str, int]:
    counts = Counter(v for v in verdicts if v)
    graded = sum(counts[v] for v in OUTCOMES)
    return {
        "correct": counts[CORRECT],
        "abstain": counts[ABSTAIN],
        "hallucinate": counts[HALLUCINATE],
        "web_sourced": counts[WEB_SOURCED],
        # Graded, neither right nor hallucinated: in the rates like abstain.
        "incomplete": counts[INCOMPLETE],
        "pending": counts[PENDING],
        "technical": counts[TECHNICAL],
        "graded": graded,
    }


def compute(session: Session, job: Job, *, configured: Panel = ()) -> dict[str, Any]:
    """The whole payload of one job: summary, report and the question index."""
    configured = resolve_panel(configured)
    first_seen = _question_set_query(job.id)
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
    run_params = _run_params(session, job.id)
    rows = _load_rows(session, job.id)
    errors = _last_errors(session, job.id)

    generator_of = {qa: gen for qa, gen, *_ in pairs}
    trick_ids = {qa for qa, gen in generator_of.items() if gen == TRICK_GENERATOR}
    main_ids = [qa for qa, *_ in pairs if qa not in trick_ids]
    counted_main = set(main_ids)

    judges = counting_judges(session, job, configured=configured)
    panel = [*judges, ""]

    by_answer = group_answers(
        rows, lambda r: AnswerKey.of(r.model, r.mode, r.block, r.qa_id)
    )

    models = sorted(
        {r.model for r in rows if r.model and r.block == EvalBlock.DIRECT.value}
    )
    # (model, arm, qa) -> counted verdict; (model, qa) -> overridden
    direct: dict[tuple[str, str, str], str] = {}
    overridden: set[tuple[str, str]] = set()
    retrieval: dict[tuple[str, str], bool | None] = {}
    blocks: dict[tuple[str, str], list[_Row]] = defaultdict(list)
    agreement: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (model, mode, block, qa), answer_rows in by_answer.items():
        arm = ARM_OF[mode]
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
        (int(p.denial_rounds) for p in run_params if isinstance(p.denial_rounds, int)),
        default=None,
    )
    context_docs = max(
        (int(p.context_docs) for p in run_params if isinstance(p.context_docs, int)),
        default=None,
    )
    profile = next((p.profile for p in run_params if p.profile), None)

    reports: list[dict[str, Any]] = []
    for model in models:
        alone = {qa: direct.get((model, ALONE, qa)) for qa in counted_main}
        with_ = {qa: direct.get((model, WITH, qa)) for qa in counted_main}
        asked_ids = [
            qa for qa in main_ids if alone[qa] is not None or with_[qa] is not None
        ]
        tally = {
            ALONE: _tally(alone[qa] for qa in asked_ids),
            WITH: _tally(with_[qa] for qa in asked_ids),
        }
        figures = _figures(model, len(asked_ids), tally)
        if figures["technical"] and model in errors:
            figures["failure"] = failure_of(errors[model], figures["technical"])

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
                    trick_ids,
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
    # Masking rows carry "llm:<model>".
    generator_model = Counter(
        m.removeprefix("llm:") for *_, m in counted_pairs if m
    ).most_common(1)
    window_days = window_days_of(job)

    articles = _articles(
        session, job, [qa for qa, *_ in counted_pairs], asked=bool(pairs)
    )
    run = {
        "job_id": job.id,
        "created_at": iso(job.created_at),
        "finished_at": iso(job.finished_at),
        "trigger": job.trigger,
        "window_days": window_days,
        **articles,
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
        "articles_from": iso(since),
        "articles_to": iso(job.created_at) if since else None,
        "generator_model": generator_model[0][0] if generator_model else None,
        "kinds": sorted(
            {gen for gen in generator_of.values() if gen}, key=generator_order
        ),
        "trick": len(trick_ids),
        "context_docs": context_docs,
        "profile": profile,
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
                "models": verdicts,
            }
        )

    return {
        "run": run,
        "funnel": _funnel(
            session, job, set(generator_of), len(counted_main), len(trick_ids)
        ),
        "models": reports,
        "judges": judges,
        "method": method,
        "questions": index,
    }


def _denial_rounds(
    rows: Sequence[_Row], run_params: Sequence[_RunParams]
) -> int | None:
    """The challenge limit of the run's denial_loop block; None — it did not run."""
    seen = [
        int(r.denial.get("limit") or 0)
        for r in rows
        if r.block == EvalBlock.DENIAL_LOOP.value and r.denial
    ]
    if max(seen, default=0):
        return max(seen)
    params = [
        int(p.denial_rounds)
        for p in run_params
        if p.block == EvalBlock.DENIAL_LOOP.value and isinstance(p.denial_rounds, int)
    ]
    return max(params, default=None)


def _repeats(
    rows: Sequence[_Row], run_params: Sequence[_RunParams]
) -> dict[str, Any] | None:
    """Repeats per temperature and the temperatures of the run's monte_carlo
    block; None — it did not run."""
    mc = [p for p in run_params if p.block == EvalBlock.MONTE_CARLO.value]
    trials = max((int(p.trials) for p in mc if isinstance(p.trials, int)), default=0)
    temps = {
        float(t)
        for p in mc
        if isinstance(p.temperatures, list)
        for t in p.temperatures
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
        "failure": None,
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
    "failure",
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
        made_up = sum(1 for v in graded if v not in (ABSTAIN, WEB_SOURCED, INCOMPLETE))
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
