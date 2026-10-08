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
from syft_benchmark.db.run_cache import invalidate_run, invalidate_runs
from syft_benchmark.llm import Provider, judge_providers
from syft_benchmark.question_order import answer_order, pair_order
from syft_benchmark.runs.judge import (
    ControlCase,
    Grade,
    control_case,
    grade,
    grade_control,
    grade_key_facts,
    is_control,
    is_technical,
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
    web_sourced: int = 0
    notes: list[str] = field(default_factory=list)

    def line(self) -> str:
        web = f", {self.web_sourced} from the web" if self.web_sourced else ""
        return (
            f"checked {self.checked} — {self.correct} correct, "
            f"{self.abstain} abstained, {self.hallucinate} hallucinated{web}, "
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
    # A control question's brief for the behaviour judge; None — not one.
    control: ControlCase | None
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
            # Nothing to grade: the call did not happen.
            and not is_technical(pair[0].verdict, str(pair[0].answer or ""))
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
                    control=(
                        control_case(pair.generator, pair.question, pair.answer, meta)
                        if is_control(pair.generator, meta)
                        else None
                    ),
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
    try:
        for task in tasks:
            if should_stop is not None and should_stop():
                report.notes.append("judging was stopped at the owner's request")
                break

            if task.control is not None:
                verdict = grade_control(
                    task.control,
                    task.answer,
                    citations=_citations_of(task.result_row["audit"]),
                    settings=conf,
                    judge=seat,
                )
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

            job_id = task.run_row["job_id"]
            key = (
                str(task.run_row["context_mode"]),
                str(task.run_row["context_source"]),
                str(task.run_row["block"]),
                str(task.run_row["model"]),
                str(job_id or ""),
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
                            # The verdict belongs to the launch whose answer it grades.
                            job_id=job_id,
                            judge_model=seat.model,
                            note="deferred judging",
                        )
                    )

            audit = dict(task.result_row["audit"] or {})
            if verdict.judge_system:
                audit["judge_system"] = verdict.judge_system
            if verdict.judge_user:
                audit["judge_user"] = verdict.judge_user
                # The key the transcript reads.
                audit["judge_prompt"] = verdict.judge_user
                audit.pop("judged_without_model", None)
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
                        extra=_with_behavior(task.result_row["extra"], verdict),
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
            elif verdict.verdict is Verdict.WEB_SOURCED:
                report.web_sourced += 1
            else:
                report.hallucinate += 1
            progress.step(failed=verdict.failed)
    finally:
        if runs:
            with session_scope(conf) as session:
                invalidate_runs(session, {key[4] for key in runs})

    logger.info(f"{space.key}: judging — {report.line()}")
    return report


def _with_behavior(extra: Any, verdict: Grade) -> dict[str, Any]:
    """The answer's extra, with this verdict's control outcome."""
    out = dict(extra or {})
    out.pop("behavior", None)
    if verdict.behavior:
        out["behavior"] = verdict.behavior
    return out


# What an owner's own verdict is recorded under, in place of a judge.
# Reading verdicts has to tell it from a grader's opinion: an override
# stands over the whole panel rather than beside it.
OWNER_OVERRIDE = "owner override"


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
                # The override belongs to the launch whose answer it
                # overrides. Without this it belongs to no launch, and the
                # run's own page — which reads one launch — would show the
                # verdict it replaced and not the owner's.
                job_id=run_row["job_id"],
                judge_model=OWNER_OVERRIDE,
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
                judge_model=OWNER_OVERRIDE,
            )
        )
        invalidate_run(session, run_row["job_id"])
    return new_id


def withdraw_override(
    result_id: str,
    *,
    target_key: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Take back a verdict the owner recorded by hand.

    The one deletion in this module, and it removes nothing that was
    measured: an override is the owner's own statement, and a statement its
    author withdraws should not go on standing over a panel that never
    changed its mind. The graders' verdicts underneath it were never
    touched, so they simply stand again.

    Args:
        result_id: The override to remove; anything else counts as not found
        target_key: If given, a result belonging to a different target counts
            as not found, same reason as everywhere else in this module
        settings: The process settings

    Returns:
        Whether there was such an override to remove
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        query = select(Result).where(
            Result.id == result_id,
            # Only ever the owner's own row. A judge's verdict is a record of
            # what was said and is not ours to erase.
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


@dataclass(slots=True)
class DenialView:
    """How the pressure on one answer ended, as the console needs to read it.

    `rounds` is how many objections were actually put — the loop stops at the
    one the model gives in on, so a flipped outcome has `rounds == flip_round`
    and a held one ran the full configured number.
    """

    rounds: int
    flipped: bool
    flip_round: int | None
    note: str
    # The objections configured for the run `rounds` belongs to: without it
    # "held 4 rounds" cannot be told from "the run stopped after 4".
    limit: int
    # Round by round: the objection put and the answer it drew.
    log: list[dict[str, Any]]


@dataclass(slots=True)
class RepeatsView:
    """How far one answer repeated when the question was asked again.

    `consistency` is the share of the repeats that gave the most frequent
    answer, not the share that were correct: a model that says the same wrong
    thing every time is consistent, and that is a different fact from accuracy.
    """

    trials: int
    accuracy: float
    consistency: float
    by_temperature: dict[str, float]
    note: str
    # Every repeat: its temperature, what came back, whether it counted.
    log: list[dict[str, Any]]


def _log_of(block: dict[str, Any]) -> list[dict[str, Any]]:
    """A block's transcript, or nothing where it was recorded before this.

    Rows measured before transcripts were kept carry none, and that is not a
    gap to fill in: the exchange was not recorded and cannot be reconstructed.
    """
    log = block.get("log")
    return (
        [entry for entry in log if isinstance(entry, dict)]
        if isinstance(log, list)
        else []
    )


def _denial_of(extra: Any) -> DenialView | None:
    """The denial block's outcome out of `Result.extra`, if it ran."""
    block = extra.get("denial") if isinstance(extra, dict) else None
    if not isinstance(block, dict):
        return None
    flip_round = block.get("flip_round")
    return DenialView(
        rounds=int(block.get("rounds") or 0),
        flipped=bool(block.get("flipped")),
        flip_round=int(flip_round) if flip_round is not None else None,
        note=str(block.get("note") or ""),
        limit=int(block.get("limit") or 0),
        log=_log_of(block),
    )


def behavior_of(extra: Any) -> str | None:
    """A control answer's ``extra.behavior``; None — not one, or graded before it."""
    value = extra.get("behavior") if isinstance(extra, dict) else None
    return str(value) if value else None


def _text_metrics_of(extra: Any) -> dict[str, float] | None:
    """`Result.extra["text_metrics"]`, the numeric scores only; None — absent."""
    scores = (extra or {}).get("text_metrics") if isinstance(extra, dict) else None
    if not isinstance(scores, dict):
        return None
    numeric = {
        str(key): float(value)
        for key, value in scores.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }
    return numeric or None


def _repeats_of(extra: Any) -> RepeatsView | None:
    """The monte carlo block's outcome out of `Result.extra`, if it ran."""
    block = extra.get("monte_carlo") if isinstance(extra, dict) else None
    if not isinstance(block, dict):
        return None
    by_temperature = block.get("by_temperature")
    return RepeatsView(
        trials=int(block.get("trials") or 0),
        accuracy=float(block.get("accuracy") or 0.0),
        consistency=float(block.get("consistency") or 0.0),
        by_temperature={
            str(key): float(value)
            for key, value in (
                by_temperature.items() if isinstance(by_temperature, dict) else ()
            )
        },
        note=str(block.get("note") or ""),
        log=_log_of(block),
    )


@dataclass(slots=True)
class FragmentView:
    """One chunk the endpoint's retrieval returned for a question."""

    file_name: str
    score: float
    content: str


@dataclass(slots=True)
class PromptsView:
    """What was actually sent — for the answer, and for the verdict on it.

    Straight out of ``Result.audit``: a prompt depends on the settings of the
    moment and cannot be rebuilt later. Any field can be empty — the record is
    absent with ``audit_log`` off, the judge fields wherever the verdict cost
    no call.

    SENSITIVE, hence not in the ordinary listing: in arm C
    ``responder_prompt`` carries the text of the chunks that were found.
    """

    responder_system: str
    responder_prompt: str
    # The material mixed into the arm C prompt, on its own as well: the reader
    # wants both the prompt as sent and the part of it that came from the data.
    context: str
    judge_system: str
    judge_prompt: str
    judge_raw: str
    # The verdict was reached without asking a model at all — an option letter
    # matched arithmetically, an abstention recognised by a regex. An empty
    # judge prompt then means nothing was asked, not that nothing was kept.
    judged_without_model: bool


@dataclass(slots=True)
class CallView:
    """How the call that produced an answer ended.

    The budget doubles until the answer fits or reaches ``answer_max_tokens``,
    so ``truncated`` means it reached that ceiling and still did not finish. A
    truncated answer is judged like any other, which is why this travels with
    every row. Read out of the audit record, so absent with ``audit_log`` off.
    """

    truncated: bool
    finish_reason: str
    # The budget the call ended on, after any doubling — the number to raise.
    max_tokens: int | None
    length_retries: int


def _citations_of(audit: Any) -> list[dict[str, str]]:
    """The answer's web citations, where the record was kept."""
    found = audit.get("citations") if isinstance(audit, dict) else None
    return [c for c in found if isinstance(c, dict)] if isinstance(found, list) else []


def _unused_search(audit: Any) -> bool:
    """Search was offered and nothing was cited."""
    return isinstance(audit, dict) and bool(audit.get("web_search_unused"))


def _call_of(audit: Any) -> CallView | None:
    """How the answerer's call ended, where the record was kept."""
    call = audit.get("call") if isinstance(audit, dict) else None
    if not isinstance(call, dict):
        return None
    tokens = call.get("max_tokens")
    return CallView(
        truncated=bool(call.get("truncated")),
        finish_reason=str(call.get("finish_reason") or ""),
        max_tokens=int(tokens) if isinstance(tokens, int) else None,
        length_retries=int(call.get("length_retries") or 0),
    )


def _params_int(params: Any, name: str) -> int | None:
    """One number out of a run's methodology snapshot, where it has one.

    None where the run does not carry it: a default here would be a claim
    about how that run was measured.
    """
    value = params.get(name) if isinstance(params, dict) else None
    return int(value) if isinstance(value, int) else None


def _prompts_of(audit: Any) -> PromptsView | None:
    """The audit trail of one row, or None where none was kept."""
    if not isinstance(audit, dict) or not audit:
        return None
    return PromptsView(
        responder_system=str(audit.get("responder_system") or ""),
        responder_prompt=str(audit.get("responder_prompt") or ""),
        context=str(audit.get("context") or ""),
        judge_system=str(audit.get("judge_system") or ""),
        judge_prompt=str(audit.get("judge_prompt") or ""),
        judge_raw=str(audit.get("judge_raw") or ""),
        judged_without_model=bool(audit.get("judged_without_model")),
    )


def _fragments_of(result: Result) -> list[FragmentView] | None:
    """What the endpoint found for this row, or None where nothing was asked.

    None rather than an empty list: nothing is asked in the closed-book arm,
    and a panel saying "0 fragments" there would read as a retrieval that came
    back empty — which is a different fact, and a worse one.
    """
    rows = result.retrieved if isinstance(result.retrieved, list) else []
    if not rows and result.retrieval_hit is None:
        return None
    return [
        FragmentView(
            file_name=str(doc.get("file_name") or ""),
            score=float(doc.get("score") or 0.0),
            content=str(doc.get("content") or ""),
        )
        for doc in rows
        if isinstance(doc, dict)
    ]


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

    # What the block did, where it was one that does something beyond asking.
    # The answer stored on a block row is the one the block STARTED from, so
    # without these two a pressure row and a repeat row are the direct row
    # printed again, and the verdict on them looks unaccountable.
    denial: DenialView | None = None
    repeats: RepeatsView | None = None

    # Whether the chunk the question grew from was found, and where. Without
    # them an abstention is unreadable: on a miss it is correct behaviour, on a
    # hit it is blindness. NULL where nothing was retrieved, as in closed book.
    retrieval_hit: bool | None = None
    retrieval_rank: int | None = None

    # How the call ended, and the two ceilings of its run. Scalars, so they
    # travel with every row.
    call: CallView | None = None
    context_docs: int | None = None
    fragment_max_chars: int | None = None

    # Web search evidence, from the audit record: what the answer cited, and
    # whether it was offered search and cited nothing.
    citations: list[dict[str, str]] = field(default_factory=list)
    web_search_unused: bool = False
    # A control question's outcome (``ControlOutcome``); None elsewhere.
    behavior: str | None = None
    # BLEU / ROUGE / BERTScore against the gold answer; None — not computed.
    text_metrics: dict[str, float] | None = None

    # Asked for by name: the trail runs to `audit_max_chars` per field, which
    # over a hundred rows is megabytes. Fetched one question at a time.
    prompts: PromptsView | None = None
    fragments: list[FragmentView] | None = None


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
        # An override stands over the whole panel; failing that, each grader's
        # own freshest verdict stands for that grader. `list_results` says the
        # same thing over a page of rows.
        override_id = session.execute(
            select(Result.id)
            .join(Run, Run.id == Result.run_id)
            .where(
                Result.space == result.space,
                Result.qa_id == result.qa_id,
                Result.judge_model == OWNER_OVERRIDE,
                *key_columns,
            )
            .order_by(Result.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        freshest_id = (
            override_id
            or session.execute(
                select(Result.id)
                .join(Run, Run.id == Result.run_id)
                .where(
                    Result.space == result.space,
                    Result.qa_id == result.qa_id,
                    Result.judge_model == result.judge_model,
                    *key_columns,
                )
                .order_by(Result.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        )

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
            denial=_denial_of(result.extra),
            repeats=_repeats_of(result.extra),
            retrieval_hit=result.retrieval_hit,
            retrieval_rank=result.retrieval_rank,
            call=_call_of(result.audit),
            citations=_citations_of(result.audit),
            web_search_unused=_unused_search(result.audit),
            behavior=behavior_of(result.extra),
            text_metrics=_text_metrics_of(result.extra),
            context_docs=_params_int(run.params, "context_docs"),
            fragment_max_chars=_params_int(run.params, "fragment_max_chars"),
        )


def list_results(
    target_key: str,
    *,
    verdict: str | None = None,
    qa_id: str | None = None,
    job: str | None = None,
    limit: int = 50,
    offset: int = 0,
    prompts: bool = False,
    settings: Settings | None = None,
) -> tuple[list[ResultView], int]:
    """This target's results in the question order.

    Args:
        target_key: The node under test
        verdict: Only results with this verdict; None — every verdict
        qa_id: Only results for this pair; None — every pair
        job: Only what this launch asked; None — everything the node has
        limit: Page size, capped at `MAX_PAGE`
        offset: How many to skip, for paging
        prompts: Also return the audit trail and the text of the chunks that
            were found. Off by default and deliberately so — the trail is
            capped at `audit_max_chars` per field, so a hundred rows of it is
            a download rather than a listing. Meant to be asked for with
            `qa_id`, one question at a time.
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
        if job:
            base = base.where(Run.job_id == job)

        total = session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()

        # The question order (report API, "Question order"); a result whose
        # pair is gone sorts last.
        ordered = base.outerjoin(QaPair, QaPair.id == Result.qa_id).order_by(
            *pair_order(QaPair.generator, QaPair.created_at, Result.qa_id),
            *answer_order(
                Run.context_mode,
                Run.block,
                Run.model,
                Result.judge_model,
                Result.created_at,
                Result.id,
            ),
        )
        rows = session.execute(ordered.limit(page).offset(offset)).all()
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
        #
        # The judge is part of the key, and has to be: a panel grades one
        # answer several times over, and without it the second judge's opinion
        # would read as having replaced the first — "superseded" — when it
        # replaced nothing. The report has always cut by judge for the same
        # reason (see `judge_agreement`); only this listing did not.
        freshest: dict[tuple[str, ...], str] = {}
        overridden: dict[tuple[str, ...], str] = {}
        history = session.execute(
            select(
                Result.id,
                Result.qa_id,
                Result.judge_model,
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
            answer = (
                row.context_mode,
                row.context_source,
                row.block,
                row.model,
                row.qa_id,
            )
            freshest[(*answer, row.judge_model)] = row.id
            if row.judge_model == OWNER_OVERRIDE:
                overridden[answer] = row.id

        # Built while the session is still open: `rows` holds ORM instances,
        # and reading their columns after the block exits would touch a
        # detached object.
        views = []
        for result, run in rows:
            pair = pairs.get(result.qa_id)
            answer = (
                run.context_mode,
                run.context_source,
                run.block,
                run.model,
                result.qa_id,
            )
            # An override stands over the whole panel; failing that, each
            # grader's own freshest verdict stands for that grader.
            stands = overridden.get(answer) or freshest.get(
                (*answer, result.judge_model)
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
                    is_latest=stands == result.id,
                    denial=_denial_of(result.extra),
                    repeats=_repeats_of(result.extra),
                    retrieval_hit=result.retrieval_hit,
                    retrieval_rank=result.retrieval_rank,
                    call=_call_of(result.audit),
                    citations=_citations_of(result.audit),
                    web_search_unused=_unused_search(result.audit),
                    behavior=behavior_of(result.extra),
                    text_metrics=_text_metrics_of(result.extra),
                    context_docs=_params_int(run.params, "context_docs"),
                    fragment_max_chars=_params_int(run.params, "fragment_max_chars"),
                    prompts=_prompts_of(result.audit) if prompts else None,
                    fragments=_fragments_of(result) if prompts else None,
                )
            )
    return views, total
