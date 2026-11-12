"""The figures of a combined run: several finished leaf jobs read as one.

Every figure is recomputed from the members' answers pooled, never from their
ratios. Each answer's verdict is picked with its own member's judges
(``counted.pick``, the member's primary judge, an owner override first). An
answer asked in more than one member (same model, arm, block and question)
counts once, from the earliest member; ``repeats`` compares the observations.
Sums and ranges over the members' launches (cost, timing, build, funnel) are
taken from what each member recorded.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from syft_benchmark.config import EvalBlock, JobKind
from syft_benchmark.db.models import CombinedMember, Job, Result, Run
from syft_benchmark.report import job_params, run_view
from syft_benchmark.report.counted import (
    OUTCOMES,
    AnswerKey,
    Panel,
    pick,
    resolve_panel,
)
from syft_benchmark.report.job_params import iso
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE
from syft_benchmark.runs.timing import ANSWER, p90

COMBINED = JobKind.COMBINED.value

# Keys of a combined job's params.
MEMBERS = "members"
ORIGIN = "origin"
PERIOD = "period"
PERIOD_START = "period_start"
TITLE = "title"
COMBINED_AT = "combined_at"
ORIGIN_MANUAL = "manual"
ORIGIN_AUTO = "auto"


def is_combined(job: Job) -> bool:
    return job.kind == COMBINED


def member_ids(session: Session, combined_id: str) -> list[str]:
    """The combined run's members, oldest first."""
    return list(
        session.scalars(
            select(CombinedMember.member_job_id)
            .where(CombinedMember.combined_job_id == combined_id)
            .order_by(CombinedMember.position, CombinedMember.member_job_id)
        )
    )


def member_jobs(session: Session, combined_id: str) -> list[Job]:
    ids = member_ids(session, combined_id)
    found = {job.id: job for job in session.scalars(select(Job).where(Job.id.in_(ids)))}
    return [found[i] for i in ids if i in found]


def holders_of(
    session: Session, job_ids: Sequence[str]
) -> dict[str, list[dict[str, Any]]]:
    """Per leaf job, the combined runs holding it: ``[{job_id, title}]``."""
    out: dict[str, list[dict[str, Any]]] = {job_id: [] for job_id in job_ids}
    if not job_ids:
        return out
    for member, combined in session.execute(
        select(CombinedMember.member_job_id, Job)
        .join(Job, Job.id == CombinedMember.combined_job_id)
        .where(CombinedMember.member_job_id.in_(list(job_ids)))
        .order_by(CombinedMember.combined_job_id)
    ):
        title = (combined.params or {}).get(TITLE)
        out[member].append({"job_id": combined.id, "title": title})
    return out


def summary_of(job: Job, members: int) -> dict[str, Any]:
    """The ``combined`` field of a runs-list item."""
    params = job.params or {}
    return {
        "members": members,
        "origin": params.get(ORIGIN) or ORIGIN_MANUAL,
        "period": params.get(PERIOD),
        "period_start": params.get(PERIOD_START),
        "title": params.get(TITLE),
    }


def member_counts(session: Session, combined_ids: Sequence[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if combined_ids:
        counts.update(
            session.scalars(
                select(CombinedMember.combined_job_id).where(
                    CombinedMember.combined_job_id.in_(list(combined_ids))
                )
            )
        )
    return {job_id: counts[job_id] for job_id in combined_ids}


# --- the figures -------------------------------------------------------------


def compute(session: Session, job: Job, *, configured: Panel = ()) -> dict[str, Any]:
    """The whole payload of a combined run (``run_view.compute``'s shape plus
    ``members``, ``repeats``, ``cost`` and ``timing``)."""
    configured = resolve_panel(configured)
    members = member_jobs(session, job.id)
    ids = [m.id for m in members]
    position = {job_id: n for n, job_id in enumerate(ids)}
    pairs = run_view.question_pairs(session, ids)
    run_params = run_view.run_params_of(session, ids)
    rows = run_view.load_rows(session, ids)
    errors = run_view.last_errors(session, ids)
    judges_of = {
        m.id: run_view.counting_judges(session, m, configured=configured)
        for m in members
    }

    observed: dict[AnswerKey, dict[str, list[run_view._Row]]] = defaultdict(dict)
    for row in rows:
        observed[run_view.answer_key(row)].setdefault(row.job_id, []).append(row)
    answers: dict[AnswerKey, run_view.Answer] = {}
    origin: dict[AnswerKey, str] = {}
    repeated: dict[AnswerKey, list[str]] = {}
    for key, by_job in observed.items():
        ordered = sorted(by_job, key=position.__getitem__)
        picks = [
            (job_id, pick(by_job[job_id], [*judges_of[job_id], ""]))
            for job_id in ordered
        ]
        first_job, first = picks[0]
        answers[key] = run_view.Answer(first, by_job[first_job])
        origin[key] = first_job
        if len(picks) > 1:
            repeated[key] = [
                chosen.counted.verdict
                for _, chosen in picks
                if chosen.counted is not None
            ]
    core = run_view.aggregate_core(
        pairs, answers, rows, run_params, errors, origin=origin
    )

    runs = run_view.summaries(session, members, configured=configured)
    parts = {
        m.id: run_view.aggregate_parts(
            session, m, "funnel", "method", configured=configured
        )
        for m in members
    }
    articles = run_view.articles_of(
        session,
        ids,
        [qa for qa, *_ in core.counted_pairs],
        asked=bool(pairs),
        generated=any(job_params.generation_of(m) for m in members),
    )
    run = run_view.run_entry(job, core, articles, asked=bool(pairs), window_days=None)
    froms = [p[1].get("articles_from") for p in parts.values() if p[1]]
    tos = [p[1].get("articles_to") for p in parts.values() if p[1]]
    method = {
        "articles_from": min((v for v in froms if v), default=None),
        "articles_to": max((v for v in tos if v), default=None),
        **core.method,
    }
    return {
        "run": run,
        "funnel": _funnel([p[0] for p in parts.values()]),
        "models": core.reports,
        "judges": _judges([judges_of[i] for i in ids]),
        "method": method,
        "questions": core.index,
        "members": [_member(m, runs[m.id]) for m in members],
        "repeats": _repeats(
            repeated,
            core.counted_main,
            [m["model"] for m in core.reports],
        ),
        "cost": combined_cost(members),
        "timing": combined_timing(session, members),
    }


def _judges(panels: Sequence[Sequence[str]]) -> list[str]:
    """Every member's judges, the first member's order first."""
    return list(dict.fromkeys(j for panel in panels for j in panel))


def _member(job: Job, run: dict[str, Any]) -> dict[str, Any]:
    cost = (job.params or {}).get(job_params.COST)
    cost = cost if isinstance(cost, dict) else {}
    usd = cost.get("total_usd")
    return {
        "job_id": job.id,
        "created_at": iso(job.created_at),
        "started_at": iso(job.started_at),
        "finished_at": iso(job.finished_at),
        "trigger": job.trigger,
        "window_days": job_params.window_days_of(job),
        "documents": run.get("articles"),
        "questions": run.get("questions"),
        "cost_usd": usd if usd is not None else cost.get("usd"),
        "state": job.state,
        "stopped": job_params.stopped_of(job),
        "kind": job.kind,
        "label": (job_params.reask_of(job) or {}).get("label"),
    }


def _sum(values: Sequence[Any]) -> Any:
    numbers = [v for v in values if isinstance(v, int | float)]
    if not numbers:
        return None
    total = sum(numbers)
    return round(total, 6) if isinstance(total, float) else total


def _funnel(funnels: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The members' funnels added up."""
    removed: Counter[str] = Counter()
    for f in funnels:
        removed.update({k: int(v) for k, v in (f.get("removed") or {}).items()})
    return {
        "written": _sum([f.get("written") for f in funnels]),
        "removed": dict(removed),
        "removed_total": _sum([f.get("removed_total") for f in funnels]),
        "unchecked": _sum([f.get("unchecked") for f in funnels]),
        "asked": _sum([f.get("asked") for f in funnels]) or 0,
        "trick": _sum([f.get("trick") for f in funnels]) or 0,
    }


def _repeats(
    repeated: dict[AnswerKey, list[str]],
    counted_main: set[str],
    models: Sequence[str],
) -> dict[str, Any]:
    """How the direct answers asked in more than one member compare, per
    model and arm, members in time order."""
    by: dict[tuple[str, str], list[list[str]]] = defaultdict(list)
    questions: set[str] = set()
    for key, verdicts in repeated.items():
        if key.block != EvalBlock.DIRECT.value or key.qa_id not in counted_main:
            continue
        by[(key.model, run_view.ARM_OF[key.context_mode])].append(verdicts)
        questions.add(key.qa_id)
    return {
        "questions": len(questions),
        "models": [
            {
                "model": model,
                **{arm: _stability(by.get((model, arm), [])) for arm in run_view.ARMS},
            }
            for model in models
        ],
    }


def _stability(series: Sequence[Sequence[str]]) -> dict[str, Any] | None:
    if not series:
        return None
    observations = graded = right = compared = agreed = up = down = 0
    for verdicts in series:
        observations += len(verdicts)
        outcomes = [v for v in verdicts if v in OUTCOMES]
        graded += len(outcomes)
        right += sum(1 for v in outcomes if v == run_view.CORRECT)
        if len(outcomes) >= 2:
            compared += 1
            agreed += len(set(outcomes)) == 1
        for before, after in zip(outcomes, outcomes[1:], strict=False):
            was, now = before == run_view.CORRECT, after == run_view.CORRECT
            up += not was and now
            down += was and not now
    return {
        "questions": len(series),
        "observations": observations,
        "graded": graded,
        "compared": compared,
        "agreed": agreed,
        "agreement": run_view.rate(agreed, compared),
        "right": right,
        "accuracy": run_view.rate(right, graded),
        "wrong_to_right": up,
        "right_to_wrong": down,
    }


# --- what the members' launches recorded ------------------------------------


def combined_cost(members: Sequence[Job]) -> dict[str, Any] | None:
    """The members' costs added up; the key spend runs from the first
    member's ``spend_before`` to the last one's ``spend_after``."""
    costs = [
        c
        for m in members
        if isinstance(c := (m.params or {}).get(job_params.COST), dict)
    ]
    if not costs:
        return None
    by_role: dict[str, float] = {}
    for c in costs:
        for role, usd in (c.get("by_role") or {}).items():
            if isinstance(usd, int | float):
                by_role[role] = round(by_role.get(role, 0.0) + usd, 6)
    return {
        "spend_before": costs[0].get("spend_before"),
        "spend_after": costs[-1].get("spend_after"),
        "usd": _sum([c.get("usd") for c in costs]),
        "usd_calls": _sum([c.get("usd_calls") for c in costs]),
        "total_usd": _sum([c.get("total_usd") for c in costs]),
        "by_role": by_role or None,
    }


def _answer_latencies(
    session: Session, job_ids: Sequence[str]
) -> dict[str, list[float]]:
    """Per tested model, the latency of each answer (copies for later verdicts
    left out)."""
    first = (
        select(Run.model, Result.latency_s)
        .join(Run, Run.id == Result.run_id)
        .where(
            Run.job_id.in_(list(job_ids)),
            Run.judge_model != OWNER_OVERRIDE,
            Result.latency_s > 0,
        )
        .distinct(Run.job_id, Run.context_mode, Run.block, Run.model, Result.qa_id)
        .order_by(
            Run.job_id,
            Run.context_mode,
            Run.block,
            Run.model,
            Result.qa_id,
            Result.created_at,
        )
    )
    out: dict[str, list[float]] = defaultdict(list)
    for model, latency in session.execute(first):
        out[model or ""].append(float(latency))
    return out


def combined_timing(session: Session, members: Sequence[Job]) -> dict[str, Any] | None:
    """The members' timings added up. A call's ``mean_s`` is weighted by its
    count; ``p90_s`` is recomputed from the answers' latencies for the answer
    role, null otherwise."""
    timings = [t for m in members if (t := job_params.timing_of(m))]
    if not timings:
        return None
    phases: dict[str, float] = {}
    passes: dict[tuple[str, str, str], dict[str, Any]] = {}
    calls: dict[tuple[str, str], dict[str, Any]] = {}
    for t in timings:
        for p in t.get("phases") or []:
            if isinstance(p, dict):
                name = str(p.get("phase"))
                phases[name] = phases.get(name, 0.0) + float(p.get("s") or 0)
        for p in t.get("passes") or []:
            if not isinstance(p, dict):
                continue
            run = (str(p.get("arm")), str(p.get("block")), str(p.get("model")))
            got = passes.setdefault(
                run,
                {"arm": run[0], "block": run[1], "model": run[2], "s": 0.0},
            )
            got["s"] += float(p.get("s") or 0)
            got["questions"] = got.get("questions", 0) + int(p.get("questions") or 0)
            got["stopped"] = got.get("stopped") or p.get("stopped") or ""
        for c in t.get("calls") or []:
            if not isinstance(c, dict):
                continue
            key = (str(c.get("model")), str(c.get("role")))
            got = calls.setdefault(
                key,
                {
                    "model": key[0],
                    "role": key[1],
                    "count": 0,
                    "failed": 0,
                    "total_s": 0.0,
                    "max_s": 0.0,
                },
            )
            got["count"] += int(c.get("count") or 0)
            got["failed"] += int(c.get("failed") or 0)
            got["total_s"] += float(c.get("total_s") or 0)
            got["max_s"] = max(got["max_s"], float(c.get("max_s") or 0))
    latencies = _answer_latencies(session, [m.id for m in members])
    call_rows = []
    for (model, role), c in calls.items():
        found = latencies.get(model) if role == ANSWER else None
        call_rows.append(
            {
                "model": model,
                "role": role,
                "count": c["count"],
                "failed": c["failed"],
                "mean_s": round(c["total_s"] / c["count"], 2) if c["count"] else 0.0,
                "p90_s": round(p90(found), 2) if found else None,
                "max_s": round(c["max_s"], 2),
                "total_s": round(c["total_s"], 2),
            }
        )
    concurrency = [t.get("concurrency") for t in timings]
    return {
        "total_s": round(sum(float(t.get("total_s") or 0) for t in timings), 2),
        "phases": [{"phase": p, "s": round(s, 2)} for p, s in phases.items()],
        "passes": [{**p, "s": round(p["s"], 2)} for p in passes.values()],
        "calls": call_rows,
        "concurrency": concurrency[0]
        if all(c == concurrency[0] for c in concurrency)
        else None,
    }


def combined_generation(members: Sequence[Job]) -> list[dict[str, Any]]:
    """The members' builds per kind added up (``pipeline.KindStats``)."""
    kinds: dict[str, dict[str, Any]] = {}
    for m in members:
        for k in job_params.generation_of(m):
            name = str(k.get("kind"))
            got = kinds.setdefault(name, {"kind": name, "dropped": {}})
            for field, value in k.items():
                if field in ("kind", "dropped"):
                    continue
                if isinstance(value, int) and not isinstance(value, bool):
                    got[field] = got.get(field, 0) + value
                elif field not in got or (value and not got[field]):
                    got[field] = value
            for reason, n in (k.get("dropped") or {}).items():
                got["dropped"][reason] = got["dropped"].get(reason, 0) + int(n)
    return list(kinds.values())


def combined_build(
    counts: dict[str, dict[str, int]], member_list: Sequence[str]
) -> dict[str, int]:
    """The members' build counts added up (``filter_view.build_counts``)."""
    total: Counter[str] = Counter()
    for job_id in member_list:
        total.update(counts.get(job_id) or {})
    return dict(total)
