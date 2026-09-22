"""What has already been done — so an interrupted run does not start over.

A port of ``_load_completed_and_cache`` from LiveTruth's `eval_arena/base.py`
onto our schema. There, what was done got collected by walking the session's
JSONL files; here it is already in the database — every verdict is written
immediately rather than at the end — and it can be collected with a query.

A measurement is interruptible by design, and that is no accident: it runs for
hours, the node gets rebooted, the provider drops out, a human presses Ctrl-C.
What is expensive in it is not what has already been recorded but what will
have to be asked again.

**The unit of resumption is one judge's verdict on one question**, not a run
and not a question. A run gets interrupted in the middle of a panel: the first
judge managed to assess the answer, the second did not — and "the question is
done" would take away from the second work it never did.

Three conditions, without which resumption turns into forgery.

**A failure is a hole, not a result.** A row with the answer ``ERROR:`` is
written so that the run is visible in full, but there is no verdict in it: the
metrics filter it out of the denominator. Counting it as done means fixing a
failure of the rig in place forever — it is exactly what has to be re-asked.

**What counts as done depends on what this run produces.** An ordinary run
produces a verdict, and for it an answer without a verdict is a hole. A run
with deferred judging produces an ANSWER, and the same row is done as far as it
is concerned: it will be judged by a separate command, and there is no reason
to re-ask the model. One definition for both cases would necessarily err in one
direction or the other — either re-asking what was collected, or silently
leaving a question without a verdict.

**Freshness is computed the same way as in the report.** A question can be
re-asked as many times as you like, and the latest verdict goes into the
metrics. Which means a question counts as done when its LAST record is not a
failure: otherwise resumption would skip a question the report will count as
failed anyway.

**The non-comparable is not reused.** The methodology profile, the effective
context source and the measurement's settings snapshot have to match. The
similarity threshold is an axis of the measurement, not a constant: a run at
0.0 and a run at 0.45 answer different questions, and adding their halves into
one share means getting a quantity that means nothing. That is exactly what
``runs.params`` was created for.

The time window is the fourth condition, and it is not about correctness but
about intent. What is resumed is an interrupted attempt, not a cancellation of
yesterday's measurement: without a window the daily cycle would measure nothing
on its second day, having decided that everything was already done.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    EvalBlock,
    Settings,
    Verdict,
)
from syft_benchmark.db import Result, Run, session_scope

# The mark of a row that has no verdict. The same one by which the report
# filters failed calls out of the denominator: two different definitions of
# "not assessed" would drift apart, and resumption would start skipping what
# the report counts as a hole.
_FAILED = "ERROR:"


def window_start(settings: Settings) -> datetime | None:
    """From what moment to count what is recorded as ours.

    ``0`` means "no window": sometimes a measurement that ran for a week is
    resumed, and cutting it off at the start of the day would be exactly what
    the human did not want.
    """
    hours = settings.resume_window_hours
    if hours <= 0:
        return None
    return datetime.now(UTC) - timedelta(hours=hours)


def _matching_runs(
    space: str,
    mode: ContextMode,
    *,
    source: ContextSource,
    block: EvalBlock,
    model: str,
    settings: Settings,
    params: dict[str, Any],
    since: datetime | None,
) -> list[str]:
    """Runs whose verdicts are comparable with the one going now.

    The settings snapshot is compared in full and on the Python side rather
    than in the query: comparing JSONB is delicate over trifles like ``0``
    versus ``0.0``, and there are not many runs per Space. An error in this
    direction is safe — extra work, not someone else's verdict in the report.
    """
    where = [
        Run.space == space,
        Run.context_mode == mode.value,
        Run.context_source == source.value,
        Run.block == block.value,
        Run.model == model,
        Run.profile == settings.methodology_profile,
    ]
    if since is not None:
        where.append(Run.started_at >= since)

    with session_scope(settings) as session:
        rows = session.execute(select(Run.id, Run.params).where(*where)).all()
    return [row.id for row in rows if dict(row.params or {}) == params]


def done_units(
    space: str,
    mode: ContextMode,
    *,
    source: ContextSource,
    block: EvalBlock,
    model: str,
    settings: Settings,
    params: dict[str, Any],
    since: datetime | None,
    need_verdict: bool = True,
) -> dict[str, set[str]]:
    """The questions this judge does not need to be re-asked.

    Args:
        space: The Space key
        mode: The measurement arm
        source: What was mixed in in arm C — the effective one, key included
        block: The test block
        model: The answerer: a model name or ``endpoint``
        settings: The process settings
        params: The measurement settings snapshot the current run goes with
        since: Not earlier than this moment; None — no window
        need_verdict: Whether a verdict is needed for a question to count as
            done. ``False`` for a run with deferred judging: it produces an
            answer, not a verdict, and an answer without a verdict is work
            done as far as it is concerned

    Returns:
        Per judge — the set of ``qa_id`` it does not need to be re-asked
    """
    run_ids = _matching_runs(
        space,
        mode,
        source=source,
        block=block,
        model=model,
        settings=settings,
        params=params,
        since=since,
    )
    if not run_ids:
        return {}

    with session_scope(settings) as session:
        rows = session.execute(
            select(
                Result.judge_model,
                Result.qa_id,
                Result.answer,
                Result.verdict,
                Result.created_at,
            )
            .where(Result.run_id.in_(run_ids))
            .order_by(Result.created_at)
        ).all()

    # The last record for the ("judge", "question") pair is what decides. The
    # walk goes in ascending time order, so each next one overrides the
    # previous — by the same rule the report picks the latest verdict with.
    freshest: dict[tuple[str, str], bool] = {}
    for row in rows:
        usable = not str(row.answer or "").startswith(_FAILED)
        if need_verdict and str(row.verdict or "") == Verdict.PENDING.value:
            usable = False
        freshest[(row.judge_model, row.qa_id)] = usable

    done: dict[str, set[str]] = {}
    for (judge, qa_id), usable in freshest.items():
        if usable:
            done.setdefault(judge, set()).add(qa_id)
    return done
