"""Stage 4 on its own: judging the answers a deferred pass left pending.

``evaluate --defer-judging`` (``run_pass(..., defer_judging=True)``) already
records every answer with ``verdict = pending`` instead of calling a judge —
that half of the mechanism has existed since judging grew a deferred mode.
What has only ever existed is the OTHER half done by hand: paste the pending
answers out with ``export-judging``, have a human or a console chat grade
them, paste the verdicts back in with ``import-judging``. This module is that
second half done live instead of on paper — the same judge model a live
evaluate pass would have called, called now, over what is already recorded.

The selection is ``console.py``'s: only the direct test (pressure and repeats
issue their verdicts as they go, over their own rounds — a grader outside the
loop has nothing sound to say about them), the freshest recorded answer per
(arm, source, block, model, question), never a failed call, never a question
this judge has already graded.

Grading never mutates a ``Result`` row — nothing in this codebase does. A
verdict is **added**: a new ``Run`` per (arm, source, block, model)
combination graded and a new ``Result`` per verdict, exactly as
``import_judging`` already does for a console judge. Every reader that picks
"the" verdict for a question already takes the freshest row, so the new one
simply becomes the answer without anything older being touched or lost.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import func, select

from syft_benchmark.config import (
    EvalBlock,
    Settings,
    SpaceConfig,
    Verdict,
    get_settings,
)
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.llm import Provider, judge_providers
from syft_benchmark.runs.judge import (
    ERROR_PREFIX,
    grade,
    grade_behavior,
    grade_key_facts,
)
from syft_benchmark.runs.parallel import Progress

# A page any larger stops being something a person reviews and starts being
# something a person scrolls past.
MAX_PAGE = 200


@dataclass(slots=True)
class JudgeSummary:
    """What came out of one live judging pass."""

    target: str
    checked: int = 0
    correct: int = 0
    abstain: int = 0
    hallucinate: int = 0
    failed: int = 0
    notes: list[str] = field(default_factory=list)

    def line(self) -> str:
        return (
            f"checked {self.checked} — {self.correct} correct, "
            f"{self.abstain} abstained, {self.hallucinate} hallucinated, "
            f"{self.failed} failed"
        )


@dataclass(slots=True)
class _Task:
    """One pending answer, with what grading it and what recording it needs."""

    result_id: str
    qa_id: str
    question: str
    expected: str
    answer: str
    grading: str
    key_facts: list[str]
    is_mcq: bool
    run_row: dict[str, Any]
    result_row: dict[str, Any]


def _pending_tasks(
    target: str, *, judge_name: str, limit: int | None, settings: Settings
) -> list[_Task]:
    """The pending direct-test answers this judge has not graded yet.

    Same key and the same three exclusions as ``console._judging_tasks``:
    keyed by (arm, source, block, model, question) rather than by run or by
    judge, because the answer is shared by the whole panel; a failed call is
    dropped, as is anything this judge already graded.
    """
    # Everything that touches a fetched row's attributes has to happen before
    # this session closes: `session_scope` expires every instance on commit,
    # and an expired instance can no longer refresh itself once the session
    # that loaded it is gone — reading `run.context_mode` after the `with`
    # block raises "not bound to a Session". `_Task` below is what survives
    # the block: plain strings and dicts, not ORM instances.
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
        judged: set[tuple[str, ...]] = set()
        for result, run in rows:
            key = (
                run.context_mode,
                run.context_source,
                run.block,
                run.model,
                result.qa_id,
            )
            # A deferred answer already carries the judge it is waiting for —
            # `_save_result` stamps `judge_model` at write time, before any
            # verdict exists — so a bare name match here would count every
            # still-pending placeholder as already graded and skip it. Only a
            # real verdict from this judge means "already graded".
            if (
                result.judge_model == judge_name
                and result.verdict != Verdict.PENDING.value
            ):
                judged.add(key)
                continue
            freshest[key] = (result, run)

        wanted = [
            pair
            for key, pair in freshest.items()
            if key not in judged
            and not str(pair[0].answer or "").startswith(ERROR_PREFIX)
            and pair[0].verdict == Verdict.PENDING.value
        ]
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

        tasks: list[_Task] = []
        for result, run in wanted:
            pair = pairs.get(result.qa_id)
            if pair is None:
                continue
            meta = pair.meta or {}
            tasks.append(
                _Task(
                    result_id=result.id,
                    qa_id=result.qa_id,
                    question=pair.question,
                    expected=pair.answer,
                    answer=str(result.answer or ""),
                    grading=str(meta.get("grading") or "judge"),
                    key_facts=[str(f) for f in meta.get("key_facts", [])],
                    is_mcq=pair.task_type == "choice",
                    run_row={
                        column.name: getattr(run, column.name)
                        for column in Run.__table__.columns
                    },
                    result_row={
                        column.name: getattr(result, column.name)
                        for column in Result.__table__.columns
                    },
                )
            )
    return tasks


def judge_pending(
    space: SpaceConfig,
    *,
    limit: int | None = None,
    settings: Settings | None = None,
    judge: Provider | None = None,
    should_stop: Callable[[], bool] | None = None,
    watch: Callable[[Progress], None] | None = None,
) -> JudgeSummary:
    """Grade this target's pending direct-test answers.

    Args:
        space: The node under test
        limit: How many pending answers to grade; None — all of them
        settings: The process settings
        judge: Who grades; None — the installation's first configured judge,
            the same one a live evaluate pass would have used
        should_stop: Asked before every answer whether the owner has called
            the pass off
        watch: Told how many of how many pending answers are graded, once per
            answer — the same observer an evaluate pass reports to, so a
            live judging run gets a numeric bar rather than a bare spinner

    Returns:
        A summary of what was graded and how it came out
    """
    conf = settings or get_settings()
    report = JudgeSummary(target=space.key)

    seat = judge
    if seat is None:
        judges = judge_providers(conf)
        seat = judges[0] if judges else None
    if seat is None:
        report.notes.append("no judge is configured — nothing was graded")
        return report

    tasks = _pending_tasks(space.key, judge_name=seat.model, limit=limit, settings=conf)
    if not tasks:
        return report

    progress = Progress(total=len(tasks), label=f"{space.key}/judging", watch=watch)
    runs: dict[tuple[str, ...], str] = {}
    for task in tasks:
        if should_stop is not None and should_stop():
            report.notes.append("judging was stopped at the owner's request")
            break

        if task.grading == "behavior":
            # A control question: no correct answer exists, and behaviour is
            # read off the text alone — no model is called for it.
            verdict = grade_behavior(task.answer)
        elif task.grading == "key_facts":
            verdict = grade_key_facts(
                task.answer, task.key_facts, settings=conf, judge=seat
            )
        else:
            verdict = grade(
                task.question,
                task.expected,
                task.answer,
                is_mcq=task.is_mcq,
                settings=conf,
                judge=seat,
            )

        key = (
            str(task.run_row["context_mode"]),
            str(task.run_row["context_source"]),
            str(task.run_row["block"]),
            str(task.run_row["model"]),
        )
        if key not in runs:
            run_id = uuid.uuid4().hex
            runs[key] = run_id
            with session_scope(conf) as session:
                session.add(
                    Run(
                        id=run_id,
                        space=space.key,
                        endpoint=str(task.run_row["endpoint"] or ""),
                        context_mode=key[0],
                        context_source=key[1],
                        profile=str(task.run_row["profile"] or ""),
                        params=dict(task.run_row["params"] or {}),
                        block=key[2],
                        model=key[3],
                        model_vendor=str(task.run_row["model_vendor"] or ""),
                        judge_model=seat.model,
                        note="deferred judging",
                    )
                )

        audit = dict(task.result_row["audit"] or {})
        if verdict.judge_system:
            audit["judge_system"] = verdict.judge_system
        if verdict.judge_user:
            audit["judge_user"] = verdict.judge_user
        if verdict.judge_raw:
            audit["judge_raw"] = verdict.judge_raw

        with session_scope(conf) as session:
            session.add(
                Result(
                    id=uuid.uuid4().hex,
                    run_id=runs[key],
                    qa_id=task.qa_id,
                    space=space.key,
                    endpoint=str(task.result_row["endpoint"] or ""),
                    endpoint_response_type=str(
                        task.result_row["endpoint_response_type"] or ""
                    ),
                    answer=str(task.result_row["answer"] or ""),
                    verdict=verdict.verdict.value,
                    reasoning=verdict.reasoning,
                    expected_behavior=str(
                        task.result_row["expected_behavior"] or "answer"
                    ),
                    grounded=task.result_row["grounded"],
                    grounded_note=str(task.result_row["grounded_note"] or ""),
                    retrieval_hit=task.result_row["retrieval_hit"],
                    retrieval_rank=task.result_row["retrieval_rank"],
                    retrieved=task.result_row["retrieved"] or [],
                    extra=dict(task.result_row["extra"] or {}),
                    audit=audit,
                    latency_s=0.0,
                    model=str(task.result_row["model"] or ""),
                    # The same answer, so the same upstream. Only the grader
                    # changed.
                    served_by=str(task.result_row["served_by"] or ""),
                    judge_model=seat.model,
                    judge_served_by=verdict.served_by,
                )
            )

        report.checked += 1
        if verdict.failed:
            report.failed += 1
        elif verdict.verdict is Verdict.CORRECT:
            report.correct += 1
        elif verdict.verdict is Verdict.ABSTAIN:
            report.abstain += 1
        else:
            report.hallucinate += 1
        progress.step(failed=verdict.failed)

    logger.info(f"{space.key}: judging — {report.line()}")
    return report


def override_verdict(
    result_id: str,
    verdict: Verdict,
    *,
    reasoning: str = "",
    owner: str = "",
    target_key: str | None = None,
    settings: Settings | None = None,
) -> str | None:
    """Record a verdict by hand for one existing result, whatever it says now.

    Same append-only pattern as automatic judging: this never mutates the
    original row, it inserts a new ``Result`` under a new ``Run`` tagged as
    manually judged, and — because every reader already takes the freshest
    row per question — that new one simply becomes the answer.

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
        result_row = {
            column.name: getattr(row[0], column.name)
            for column in Result.__table__.columns
        }
        run_row = {
            column.name: getattr(row[1], column.name)
            for column in Run.__table__.columns
        }

    run_id = uuid.uuid4().hex
    with session_scope(conf) as session:
        session.add(
            Run(
                id=run_id,
                space=str(result_row["space"]),
                endpoint=str(run_row["endpoint"] or ""),
                context_mode=str(run_row["context_mode"] or ""),
                context_source=str(run_row["context_source"] or ""),
                profile=str(run_row["profile"] or ""),
                params=dict(run_row["params"] or {}),
                block=str(run_row["block"] or ""),
                model=str(run_row["model"] or ""),
                model_vendor=str(run_row["model_vendor"] or ""),
                judge_model="owner override",
                note=f"manual override by {owner}" if owner else "manual override",
            )
        )
        audit = dict(result_row["audit"] or {})
        audit["judged_by_owner"] = owner or True
        new_id = uuid.uuid4().hex
        session.add(
            Result(
                id=new_id,
                run_id=run_id,
                qa_id=str(result_row["qa_id"]),
                space=str(result_row["space"]),
                endpoint=str(result_row["endpoint"] or ""),
                endpoint_response_type=str(result_row["endpoint_response_type"] or ""),
                answer=str(result_row["answer"] or ""),
                verdict=verdict.value,
                reasoning=reasoning or "manual override",
                expected_behavior=str(result_row["expected_behavior"] or "answer"),
                grounded=result_row["grounded"],
                grounded_note=str(result_row["grounded_note"] or ""),
                retrieval_hit=result_row["retrieval_hit"],
                retrieval_rank=result_row["retrieval_rank"],
                retrieved=result_row["retrieved"] or [],
                extra=dict(result_row["extra"] or {}),
                audit=audit,
                latency_s=0.0,
                model=str(result_row["model"] or ""),
                served_by=str(result_row["served_by"] or ""),
                judge_model="owner override",
            )
        )
    return new_id


@dataclass(slots=True)
class ResultView:
    """One verdict, as an owner reviewing judging needs to see it."""

    id: str
    qa_id: str
    question: str
    answer: str
    generator: str
    verdict: str
    reasoning: str
    judge_model: str
    context_mode: str
    block: str
    model: str
    created_at: datetime
    # Whether this is the row every other reader in the codebase already
    # treats as "the" verdict for its (arm, source, block, model, question) —
    # the freshest by `created_at`. Overriding only ever makes sense for one.
    is_latest: bool


def get_result(
    result_id: str, *, target_key: str | None = None, settings: Settings | None = None
) -> ResultView | None:
    """One result's full detail, or None if there is no such result.

    Args:
        result_id: The result to read
        target_key: If given, a result belonging to a different target counts
            as not found, same reason as everywhere else in this module
        settings: The process settings
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
        result, run = row

        pair = session.get(QaPair, result.qa_id)
        key_columns = (
            Run.context_mode == run.context_mode,
            Run.context_source == run.context_source,
            Run.block == run.block,
            Run.model == run.model,
        )
        freshest_id = session.execute(
            select(Result.id)
            .join(Run, Run.id == Result.run_id)
            .where(
                Result.space == result.space,
                Result.qa_id == result.qa_id,
                *key_columns,
            )
            .order_by(Result.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        return ResultView(
            id=result.id,
            qa_id=result.qa_id,
            question=pair.question if pair else "",
            answer=result.answer,
            generator=pair.generator if pair else "",
            verdict=result.verdict,
            reasoning=result.reasoning,
            judge_model=result.judge_model,
            context_mode=run.context_mode,
            block=run.block,
            model=run.model,
            created_at=result.created_at,
            is_latest=freshest_id == result.id,
        )


def list_results(
    target_key: str,
    *,
    verdict: str | None = None,
    qa_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    settings: Settings | None = None,
) -> tuple[list[ResultView], int]:
    """This target's results, newest first.

    Args:
        target_key: The node under test
        verdict: Only results with this verdict; None — every verdict
        qa_id: Only results for this pair; None — every pair
        limit: Page size, capped at `MAX_PAGE`
        offset: How many to skip, for paging
        settings: The process settings

    Returns:
        The page of results, and the total count the filters match
    """
    conf = settings or get_settings()
    page = max(1, min(limit, MAX_PAGE))

    with session_scope(conf) as session:
        base = (
            select(Result, Run)
            .join(Run, Run.id == Result.run_id)
            .where(Result.space == target_key)
        )
        if verdict:
            base = base.where(Result.verdict == verdict)
        if qa_id:
            base = base.where(Result.qa_id == qa_id)

        total = session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()

        rows = session.execute(
            base.order_by(Result.created_at.desc()).limit(page).offset(offset)
        ).all()
        if not rows:
            return [], total

        pairs = {
            pair.id: pair
            for pair in session.execute(
                select(QaPair).where(
                    QaPair.id.in_({result.qa_id for result, _ in rows})
                )
            ).scalars()
        }

        # The freshest row per key, over the whole history rather than just
        # this page, so `is_latest` is accurate on page two as well.
        freshest: dict[tuple[str, ...], str] = {}
        history = session.execute(
            select(
                Result.id,
                Result.qa_id,
                Run.context_mode,
                Run.context_source,
                Run.block,
                Run.model,
            )
            .join(Run, Run.id == Result.run_id)
            .where(Result.space == target_key)
            .order_by(Result.created_at)
        ).all()
        for row in history:
            key = (
                row.context_mode,
                row.context_source,
                row.block,
                row.model,
                row.qa_id,
            )
            freshest[key] = row.id

        # Built while the session is still open: `rows` holds ORM instances,
        # and reading their columns after the block exits would touch a
        # detached object.
        views = []
        for result, run in rows:
            pair = pairs.get(result.qa_id)
            key = (
                run.context_mode,
                run.context_source,
                run.block,
                run.model,
                result.qa_id,
            )
            views.append(
                ResultView(
                    id=result.id,
                    qa_id=result.qa_id,
                    question=pair.question if pair else "",
                    answer=result.answer,
                    generator=pair.generator if pair else "",
                    verdict=result.verdict,
                    reasoning=result.reasoning,
                    judge_model=result.judge_model,
                    context_mode=run.context_mode,
                    block=run.block,
                    model=run.model,
                    created_at=result.created_at,
                    is_latest=freshest.get(key) == result.id,
                )
            )
    return views, total
