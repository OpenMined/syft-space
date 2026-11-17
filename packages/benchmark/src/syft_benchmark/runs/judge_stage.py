"""Verdicts added after the run: deferred judging and the owner's overrides.

``judge_pending`` grades, with a live judge, the direct-test answers a deferred
pass left ``pending`` or whose judge call failed; ``override_verdict`` records
the owner's own verdict. Both append rows (``runs.regrade``) and never touch
what is stored. ``pending_tasks`` is the one selector of what a judge still has
to grade, shared with the console export.

Only the direct test is graded here: pressure and repeats issue their verdicts
round by round as they run, and a grader outside the loop has nothing sound to
say about them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from sqlalchemy import select

from syft_benchmark.config import (
    EvalBlock,
    Settings,
    SpaceConfig,
    Verdict,
    get_settings,
)
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.db.run_cache import invalidate_run
from syft_benchmark.llm import judge_provider
from syft_benchmark.runs.judge import (
    Gradable,
    Grade,
    VerdictCounts,
    grade_item,
    is_error,
    is_technical,
    judge_trail,
)
from syft_benchmark.runs.parallel import Progress
from syft_benchmark.runs.regrade import (
    VerdictRuns,
    answer_audit,
    answer_extra,
    columns,
    copy_result,
)

# What an owner's own verdict is recorded under, in place of a judge. It
# stands over the whole panel rather than beside it.
OWNER_OVERRIDE = "owner override"


@dataclass(slots=True, kw_only=True)
class JudgeSummary(VerdictCounts):
    """What came out of one live judging pass."""

    checked: int = 0
    notes: list[str] = field(default_factory=list)

    def line(self) -> str:
        web = f", {self.web_sourced} from the web" if self.web_sourced else ""
        partial = f", {self.incomplete} incomplete" if self.incomplete else ""
        return (
            f"checked {self.checked} — {self.correct} correct, "
            f"{self.abstain} abstained, {self.hallucinate} hallucinated{web}"
            f"{partial}, {self.failed} failed"
        )


@dataclass(slots=True)
class Task:
    """One answer awaiting this judge, with what grading and recording it need."""

    item: Gradable
    run_row: dict[str, Any]
    result_row: dict[str, Any]

    @property
    def answer(self) -> str:
        return str(self.result_row["answer"] or "")

    @property
    def result_id(self) -> str:
        return str(self.result_row["id"])


def citations_of(audit: Any) -> list[dict[str, str]]:
    """The answer's web citations, where the audit record was kept."""
    found = audit.get("citations") if isinstance(audit, dict) else None
    return [c for c in found if isinstance(c, dict)] if isinstance(found, list) else []


def pending_tasks(
    target: str,
    *,
    judge_name: str,
    only_pending: bool = True,
    limit: int | None = None,
    settings: Settings,
) -> list[Task]:
    """The direct-test answers this judge still has to grade.

    Keyed by (arm, source, block, model, question): the answer is shared by the
    whole panel. Wanted: the freshest answer is real and this judge has no
    verdict on it; a verdict counts for the launch (job) whose answer it
    grades, so a later launch's answer is wanted again. Under ``only_pending``
    the answer must also be pending, or a judge call on it failed (this
    judge's or the freshest row's). Without it every such answer is wanted,
    including those other judges graded: a further opinion on the same
    answers. A deferred answer is stamped with the judge it waits for, so only
    a real verdict from this judge means graded.

    Only the direct test: pressure and repeats are judged round by round as
    they run, and a grader outside the loop has nothing sound to say about them.
    """
    # Everything read from a fetched row happens inside the session:
    # `session_scope` expires instances on commit and they cannot refresh
    # afterwards. `Task` carries plain values out.
    with session_scope(settings) as session:
        rows = session.execute(
            select(Result, Run)
            .join(Run, Run.id == Result.run_id)
            .where(
                Result.space == target,
                Run.block == EvalBlock.DIRECT.value,
            )
            .order_by(Result.created_at)
        ).all()

        freshest: dict[tuple[str, ...], tuple[Result, Run]] = {}
        # This judge's latest outcome per answer — the key and the launch it
        # was asked in: True — a verdict, False — its call failed on a real
        # answer.
        mine: dict[tuple[str | None, ...], bool] = {}
        for result, run in rows:
            key = (
                run.context_mode,
                run.context_source,
                run.block,
                run.model,
                result.qa_id,
            )
            if (
                result.judge_model == judge_name
                and result.verdict != Verdict.PENDING.value
                and not is_error(str(result.answer or ""))
            ):
                graded = not is_technical(result.verdict)
                mine[(*key, run.job_id)] = graded
                if graded:
                    continue
            freshest[key] = (result, run)

        def awaits(key: tuple[str, ...], result: Result, run: Run) -> bool:
            outcome = mine.get((*key, run.job_id))
            if outcome or is_error(str(result.answer or "")):
                # Graded already, or nothing to grade: the call did not happen.
                return False
            if not only_pending:
                return True
            return (
                result.verdict == Verdict.PENDING.value
                or is_technical(result.verdict)
                or outcome is False
            )

        wanted = [pair for key, pair in freshest.items() if awaits(key, *pair)]
        wanted.sort(
            key=lambda pair: (
                pair[1].context_mode,
                pair[1].block,
                pair[1].model,
                pair[0].qa_id,
            )
        )
        if limit:
            wanted = wanted[:limit]
        if not wanted:
            return []

        pairs = {
            pair.id: pair
            for pair in session.execute(
                select(QaPair).where(QaPair.id.in_({r.qa_id for r, _ in wanted}))
            ).scalars()
        }

        return [
            Task(
                item=Gradable.of(pairs[result.qa_id]),
                run_row=columns(run),
                result_row=columns(result),
            )
            for result, run in wanted
            if result.qa_id in pairs
        ]


def judge_pending(
    space: SpaceConfig,
    *,
    limit: int | None = None,
    settings: Settings | None = None,
    should_stop: Callable[[], bool] | None = None,
    watch: Callable[[Progress], None] | None = None,
) -> JudgeSummary:
    """Grade this target's pending and judge-failed direct-test answers.

    The first configured judge grades, the one a live evaluate pass would
    have used.

    Args:
        space: The node under test
        limit: How many pending answers to grade; None — all of them
        settings: The process settings
        should_stop: Asked before every answer whether the owner has called
            the pass off
        watch: Told the progress once per answer, as for an evaluate pass

    Returns:
        A summary of what was graded and how it came out
    """
    conf = settings or get_settings()
    report = JudgeSummary()

    seat = judge_provider(conf)

    tasks = pending_tasks(space.key, judge_name=seat.model, limit=limit, settings=conf)
    if not tasks:
        return report

    progress = Progress(total=len(tasks), label=f"{space.key}/judging", watch=watch)
    runs = VerdictRuns(space.key, seat.model, "deferred judging")
    for task in tasks:
        if should_stop is not None and should_stop():
            report.notes.append("judging was stopped at the owner's request")
            break

        verdict = grade_item(
            task.item,
            task.answer,
            citations=citations_of(task.result_row["audit"]),
            settings=conf,
            judge=seat,
        )

        with session_scope(conf) as session:
            session.add(
                copy_result(
                    task.result_row,
                    run_id=runs.run_id_for(session, task.run_row),
                    verdict=verdict.verdict.value,
                    reasoning=verdict.reasoning,
                    extra=_with_behavior(task.result_row["extra"], verdict),
                    audit=answer_audit(task.result_row["audit"]) | judge_trail(verdict),
                    judge_model=seat.model,
                    judge_served_by=verdict.served_by,
                )
            )

        report.checked += 1
        report.count(verdict)
        progress.step(failed=verdict.failed)

    logger.info(f"{space.key}: judging — {report.line()}")
    return report


def _with_behavior(extra: Any, verdict: Grade) -> dict[str, Any]:
    """The answer's extra, with this verdict's control outcome."""
    out = answer_extra(extra)
    out.pop("behavior", None)
    if verdict.behavior:
        out["behavior"] = verdict.behavior
    return out


def override_verdict(
    result_id: str,
    verdict: Verdict,
    *,
    reasoning: str = "",
    owner: str = "",
    target_key: str | None = None,
    settings: Settings | None = None,
) -> str | None:
    """Record the owner's verdict for one existing result, as a new row.

    Args:
        result_id: The existing ``Result`` the owner is overriding
        verdict: The verdict to record
        reasoning: Why; free text, shown next to the verdict
        owner: Who is overriding it, for the audit trail
        target_key: If given, a result belonging to a different target counts
            as not found — a session token minted for one target must not
            override another's by guessing an id
        settings: The process settings

    Returns:
        The id of the new ``Result``, or None if ``result_id`` does not exist
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        query = (
            select(Result, Run)
            .join(Run, Run.id == Result.run_id)
            .where(Result.id == result_id)
        )
        if target_key is not None:
            query = query.where(Result.space == target_key)
        row = session.execute(query).first()
        if row is None:
            return None
        result_row = columns(row[0])
        run_row = columns(row[1])

    # The override belongs to the launch whose answer it overrides, so that
    # launch's own page shows it.
    runs = VerdictRuns(
        str(result_row["space"]),
        OWNER_OVERRIDE,
        f"manual override by {owner}" if owner else "manual override",
    )
    with session_scope(conf) as session:
        audit = answer_audit(result_row["audit"])
        audit["judged_by_owner"] = owner or True
        new = copy_result(
            result_row,
            run_id=runs.run_id_for(session, run_row),
            verdict=verdict.value,
            reasoning=reasoning or "manual override",
            extra=answer_extra(result_row["extra"]),
            audit=audit,
            judge_model=OWNER_OVERRIDE,
        )
        session.add(new)
        new_id = new.id
    return new_id


def withdraw_override(
    result_id: str,
    *,
    target_key: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Take back a verdict the owner recorded by hand.

    The one deletion of a verdict anywhere: an override is the owner's own
    statement, and the judges' verdicts beneath it stand again.

    Args:
        result_id: The override to remove; anything else counts as not found
        target_key: If given, a result belonging to a different target counts
            as not found
        settings: The process settings

    Returns:
        Whether there was such an override to remove
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        query = select(Result).where(
            Result.id == result_id,
            # Only ever the owner's own row; a judge's verdict is a record.
            Result.judge_model == OWNER_OVERRIDE,
        )
        if target_key is not None:
            query = query.where(Result.space == target_key)
        row = session.execute(query).scalar_one_or_none()
        if row is None:
            return False
        run_id = row.run_id
        session.delete(row)
        # The run was opened for this one verdict and holds nothing else.
        run = session.get(Run, run_id)
        if run is not None:
            invalidate_run(session, run.job_id)
            if run.judge_model == OWNER_OVERRIDE:
                session.delete(run)
    return True
