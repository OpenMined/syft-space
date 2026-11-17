"""What has already been done, so an interrupted run does not start over.

Every verdict is written at once, so what was done is a query. The unit of
resumption is one judge's verdict on one question: a run can be interrupted in
the middle of a panel.

  * **A failure is a hole, not a result.** An ``ERROR:`` answer is re-asked. A
    ``technical`` verdict on a real answer (the judge call failed) is re-asked
    by a run that needs a verdict; under deferred judging the answer is kept
    and the ``judge`` command grades it again.
  * **Done depends on what the run produces.** An ordinary run produces a
    verdict, so an answer without one is a hole; a deferred run produces an
    answer, and the same row is done.
  * **Freshness as in the report.** A question is done when its LAST record is
    usable.
  * **The non-comparable is not reused.** The methodology profile, the
    effective context source and the settings snapshot (``runs.params``) must
    match: a run at threshold 0.0 and one at 0.45 answer different questions.
  * **A time window.** What is resumed is an interrupted attempt, not
    yesterday's measurement.
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
from syft_benchmark.runs.judge import is_error, is_technical


def window_start(settings: Settings) -> datetime | None:
    """From what moment recorded verdicts count as this attempt's; None — no window."""
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

    The settings snapshot is compared in Python, not in the query: JSONB
    comparison trips over ``0`` versus ``0.0``. An error here only costs
    extra work.
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

    # The latest record per (judge, question) decides, as in the report; the
    # tests are the report's own, so "not assessed" has one definition.
    freshest: dict[tuple[str, str], bool] = {}
    for row in rows:
        answer = str(row.answer or "")
        verdict = str(row.verdict or "")
        if need_verdict:
            usable = (
                not is_error(answer)
                and not is_technical(verdict)
                and verdict != Verdict.PENDING.value
            )
        else:
            usable = not is_error(answer)
        freshest[(row.judge_model, row.qa_id)] = usable

    done: dict[str, set[str]] = {}
    for (judge, qa_id), usable in freshest.items():
        if usable:
            done.setdefault(judge, set()).add(qa_id)
    return done
