"""Re-grading the verdicts the old refusal rule gave without a judge.

The rule used to mark an answer ``abstain`` without calling a judge when a
refusal phrase stood anywhere in it ("... so I can't confirm the author") or
was glued to the answer after it ("I don't knowThe ..."). The rule now skips
the judge only for a whole-answer refusal (``runs.refusal``). This finds the
direct-test verdicts the old rule gave, sends each answer the current rule no
longer reads as a refusal to the judge that gave the verdict, and appends the
new verdict as a further row (``runs.regrade``): the old row stays, the new one
records what it replaced under ``audit["regrade"]``, and every figure reads
the new one through the usual precedence (``report.counted.pick``).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from syft_benchmark.config import EvalBlock, Settings, Verdict
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.llm.roles import judge_seat
from syft_benchmark.runs.judge import Gradable, grade_item, is_error, judge_trail
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE, citations_of
from syft_benchmark.runs.refusal import detect_abstain
from syft_benchmark.runs.regrade import (
    REGRADE_KEY,
    VerdictRuns,
    answer_audit,
    answer_extra,
    columns,
    copy_result,
)

# The reasoning the rule recorded on the verdicts it gave without a judge.
RULE_REASONS = ("refused to answer", "refused to explain")
RULE = "refusal"
NOTE = "refusal rule re-grade"


@dataclass(slots=True)
class Candidate:
    """One verdict the old rule gave, on an answer the current rule sends to
    the judge."""

    item: Gradable
    run_row: dict[str, Any]
    result_row: dict[str, Any]

    @property
    def judge(self) -> str:
        return str(self.result_row["judge_model"])

    @property
    def answer(self) -> str:
        return str(self.result_row["answer"] or "")


@dataclass(slots=True)
class Plan:
    """What a re-grade of one target would do."""

    space: str
    # Verdicts the old rule gave that are still the judge's latest.
    found: int = 0
    # Of them, answers the current rule still reads as a refusal: unchanged.
    still_refusals: int = 0
    candidates: list[Candidate] = field(default_factory=list)
    # USD per judge call, by judge model, from the calls already recorded;
    # absent — no priced call to go by.
    unit_cost: dict[str, float] = field(default_factory=dict)

    def by_job_model(self) -> Counter[tuple[str, str, str]]:
        """Candidates per (job, model, judge)."""
        return Counter(
            (str(c.run_row["job_id"] or "-"), str(c.run_row["model"]), c.judge)
            for c in self.candidates
        )

    def estimated_usd(self) -> float | None:
        """The judge calls' cost, by the recorded average; None — no call of
        any of these judges was priced."""
        judges = Counter(c.judge for c in self.candidates)
        known = {
            j: n * self.unit_cost[j] for j, n in judges.items() if j in self.unit_cost
        }
        return round(sum(known.values()), 4) if known else None

    def unpriced_judges(self) -> list[str]:
        return sorted({c.judge for c in self.candidates} - set(self.unit_cost))


@dataclass(slots=True)
class Outcome:
    """What an applied re-grade did."""

    regraded: int = 0
    changed: int = 0
    # Judge calls that failed: nothing stored, the next run tries them again.
    failed: int = 0
    verdicts: Counter[str] = field(default_factory=Counter)
    stopped: str = ""


def _is_rule_verdict(verdict: str, reasoning: str, audit: Any) -> bool:
    return (
        verdict == Verdict.ABSTAIN.value
        and reasoning in RULE_REASONS
        and isinstance(audit, dict)
        and audit.get("judged_without_model") is True
    )


def plan(session: Session, space: str, *, job_ids: Sequence[str] | None = None) -> Plan:
    """The old rule's verdicts on this target's direct test, and which of them
    go to a judge now.

    Per answer and judge only the judge's latest verdict is read: a verdict
    already re-graded, or graded again later, is left alone.
    """
    out = Plan(space=space)
    stmt = (
        select(
            Result.id,
            Result.verdict,
            Result.reasoning,
            Result.judge_model,
            Result.audit["judged_without_model"],
            Run.job_id,
            Run.context_mode,
            Run.context_source,
            Run.model,
            Result.qa_id,
        )
        .join(Run, Run.id == Result.run_id)
        .where(Result.space == space, Run.block == EvalBlock.DIRECT.value)
        .order_by(Result.created_at, Result.id)
    )
    if job_ids:
        stmt = stmt.where(Run.job_id.in_(list(job_ids)))
    latest: dict[tuple[Any, ...], tuple[str, str, str, Any]] = {}
    for (
        rid,
        verdict,
        reasoning,
        judge,
        without,
        job,
        mode,
        source,
        model,
        qa,
    ) in session.execute(stmt).all():
        if not judge or judge == OWNER_OVERRIDE:
            continue
        latest[(job, mode, source, model, qa, judge)] = (
            rid,
            verdict,
            reasoning or "",
            {"judged_without_model": without},
        )
    wanted = [
        rid
        for rid, verdict, reasoning, audit in latest.values()
        if _is_rule_verdict(verdict, reasoning, audit)
    ]
    out.found = len(wanted)
    if not wanted:
        return out

    rows = session.execute(
        select(Result, Run)
        .join(Run, Run.id == Result.run_id)
        .where(Result.id.in_(wanted))
        .order_by(Run.job_id, Run.model, Result.qa_id, Result.judge_model)
    ).all()
    pairs = {
        pair.id: pair
        for pair in session.execute(
            select(QaPair).where(QaPair.id.in_({r.qa_id for r, _ in rows}))
        ).scalars()
    }
    for result, run in rows:
        answer = str(result.answer or "")
        if is_error(answer) or detect_abstain(answer) or result.qa_id not in pairs:
            out.still_refusals += 1
            continue
        out.candidates.append(
            Candidate(
                item=Gradable.of(pairs[result.qa_id]),
                run_row=columns(run),
                result_row=columns(result),
            )
        )
    out.unit_cost = _unit_costs(session, {c.judge for c in out.candidates})
    return out


def _unit_costs(session: Session, judges: set[str]) -> dict[str, float]:
    """The average recorded USD of one verdict's judge calls, per judge."""
    if not judges:
        return {}
    usd = cast(Result.audit["judge_call"]["cost_usd"].astext, Float)
    rows = session.execute(
        select(Result.judge_model, func.avg(usd))
        .where(Result.judge_model.in_(judges), usd.is_not(None))
        .group_by(Result.judge_model)
    ).all()
    return {judge: float(avg) for judge, avg in rows if avg is not None}


def _extra(extra: Any, behavior: str) -> dict[str, Any]:
    """The answer's extra with the new verdict's control outcome."""
    out = answer_extra(extra)
    out.pop("behavior", None)
    if behavior:
        out["behavior"] = behavior
    return out


def apply(
    found: Plan,
    *,
    settings: Settings,
    watch: Callable[[Candidate, str], None] | None = None,
) -> Outcome:
    """Grade every candidate with its judge and append the new verdicts.

    A judge call that fails stores nothing: the old verdict stays the judge's
    latest and a later run picks it up again. A fatal refusal (key, money)
    stops the pass.
    """
    out = Outcome()
    runs: dict[str, VerdictRuns] = {}
    for candidate in found.candidates:
        seat = judge_seat(settings, candidate.judge)
        grade = grade_item(
            candidate.item,
            candidate.answer,
            citations=citations_of(candidate.result_row["audit"]),
            settings=settings,
            judge=seat,
        )
        if grade.failed or grade.verdict is Verdict.PENDING:
            out.failed += 1
            if watch is not None:
                watch(candidate, "failed")
            if grade.fatal:
                out.stopped = grade.reasoning
                break
            continue
        old = candidate.result_row
        audit = answer_audit(old["audit"]) | judge_trail(grade)
        audit[REGRADE_KEY] = {
            "of": old["id"],
            "old_verdict": old["verdict"],
            "old_reasoning": old["reasoning"],
            "rule": RULE,
        }
        verdict_runs = runs.setdefault(
            candidate.judge, VerdictRuns(found.space, candidate.judge, NOTE)
        )
        with session_scope(settings) as session:
            session.add(
                copy_result(
                    old,
                    run_id=verdict_runs.run_id_for(session, candidate.run_row),
                    verdict=grade.verdict.value,
                    reasoning=grade.reasoning,
                    extra=_extra(old["extra"], grade.behavior),
                    audit=audit,
                    judge_model=candidate.judge,
                    judge_served_by=grade.served_by,
                )
            )
        out.regraded += 1
        out.changed += grade.verdict.value != old["verdict"]
        out.verdicts[grade.verdict.value] += 1
        if watch is not None:
            watch(candidate, grade.verdict.value)
    return out
