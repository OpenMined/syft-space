"""One evaluation pass: a Space's questions asked in one arm and graded by the panel.

The arms: docs/04-evaluation.md. Both write into one table, told apart by
``context_mode`` and ``context_source``.

Parallelism and the cache of what was already asked live in ``runs/parallel.py``;
this module decides WHAT is asked and how it is recorded.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from functools import partial
from typing import Any

from loguru import logger
from sqlalchemy import select

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    EvalBlock,
    PairStatus,
    Settings,
    SpaceConfig,
    Verdict,
    get_settings,
)
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.llm import (
    LLMError,
    LLMFatalError,
    Provider,
    chat,
    check_judge_independence,
    cost,
    is_recused,
    judge_providers,
)
from syft_benchmark.llm.roles import web_search_for
from syft_benchmark.llm.web_search import search_unused, unused_reason
from syft_benchmark.runs.blocks import (
    DenialOutcome,
    MonteCarloOutcome,
    monte_carlo_plan,
    monte_carlo_skip_note,
    monte_carlo_trial,
    run_denial_loop,
    skips_monte_carlo,
    tally_monte_carlo,
)
from syft_benchmark.runs.endpoint import check_retrieval, endpoint_mode
from syft_benchmark.runs.gate import evaluable, nothing_passed
from syft_benchmark.runs.judge import (
    ERROR_PREFIX,
    Gradable,
    Grade,
    VerdictCounts,
    answer_citations,
    check_grounded,
    grade_item,
    holds,
    is_error,
    judge_trail,
)
from syft_benchmark.runs.parallel import Launch, Pool, Progress, RunCache
from syft_benchmark.runs.questionset import apply as apply_slice
from syft_benchmark.runs.questionset import load as load_slice
from syft_benchmark.runs.resume import done_units, window_start
from syft_benchmark.runs.textmetrics import applies_to, score_text
from syft_benchmark.runs.timing import ANSWER, JUDGE

# The arms for which the endpoint has to be called.
ENDPOINT_ARMS = (ContextMode.MODEL_WITH_CONTEXT,)

# The context sources that need the chunks found. An endpoint in summary mode
# cuts the references out of its answer, so such an arm is refused before the
# run rather than reported as zeros.
_NEEDS_FRAGMENTS = (
    ContextSource.ENDPOINT_FRAGMENTS,
    ContextSource.ENDPOINT_BOTH,
)

# The context sources that need the endpoint PROSE, not only its retrieval.
_NEEDS_ANSWER = (
    ContextSource.ENDPOINT_ANSWER,
    ContextSource.ENDPOINT_BOTH,
)

CLOSED_BOOK_SYSTEM = """\
Answer the question from your own knowledge.

If the question assumes something that isn't true, say so and give the correct \
fact instead of answering as asked.

Otherwise, if you are not sure, respond with ONLY: I don't know

Do not guess. An honest "I don't know" is better than a confident answer that \
might be wrong.
"""

# Deliberately the same form as the arm A instruction — the same false-premise
# line first, the same abstention formula, the same ban on guessing — so the
# difference between the arms measures the context and not the wording. A
# premise the material contradicts is a correction to give, not a gap to admit.
_WITH_CONTEXT_SYSTEM = """\
Answer the question using the material provided below the question.

If the question assumes something the material contradicts, say so and state \
what the material says.

Otherwise, if the material does not contain the answer, respond with ONLY: I don't know

Do not guess and do not fill gaps from your own knowledge. An honest "I don't \
know" is better than a confident answer that might be wrong. Material that \
looks related but does not state the answer is not an answer.
"""


@dataclass(slots=True, kw_only=True)
class RunReport(VerdictCounts):
    """The outcome of one pass for one judge."""

    run_id: str
    context_mode: ContextMode
    block: EvalBlock = EvalBlock.DIRECT
    model: str = ""
    judge: str = ""
    asked: int = 0
    # Verdicts taken from a previous attempt: without this a resumed run reads
    # as a run over the few questions it still had to ask.
    resumed: int = 0
    # Answers recorded without a verdict, to be judged separately.
    deferred: int = 0
    # The name the provider refused outright during this pass, when it did.
    # Every later pass with the same name would come back with the same refusal.
    refused: str = ""
    # The text of one failed call. A spent key, a wrong model name, a dropped
    # network and a node that is down all end with zero verdicts; this line is
    # what tells them apart.
    failure_sample: str = ""
    notes: list[str] = field(default_factory=list)
    # Why the pass ended before its last question; empty — it did not.
    stopped: str = ""


@dataclass(frozen=True, slots=True)
class Asked:
    """The answer to one question along with the trace of how it was obtained.

    The prompt is kept beside the answer: it depends on the settings of the
    moment (retrieval threshold, number of chunks), and an auditor has to see
    the text that actually went to the model.
    """

    answer: str
    latency: float
    system: str
    user: str
    retrieval: dict[str, Any]
    context_source: ContextSource
    context: str = ""
    # What the provider said about the call: finish_reason, truncation at the
    # token ceiling, attempts.
    usage: dict[str, Any] = field(default_factory=dict)
    # There is no answer because the call failed, not because there was nothing
    # to answer from: a state of the rig, which the failure streak counts.
    call_failed: bool = False
    # The answerer's name when the provider refused it outright (name, key,
    # money): asking the rest of the set buys the same refusal per item.
    refused: str = ""


def _empty_retrieval() -> dict[str, Any]:
    return {"retrieval_hit": None, "retrieval_rank": None, "retrieved": []}


def pick_pairs(rows: list[QaPair], limit: int | None) -> list[QaPair]:
    """Select ``limit`` items PER GENERATOR, in the order given.

    Each generator measures a distinct skill, so the limit applies to each one
    rather than to the total: a total split across generators drops some of
    them entirely at small values. Each generator produces items of exactly one
    half (answerable, unanswerable, false premise), so the halves are covered
    too. Which generators take part is decided by the set's composition, not by
    the limit. With a limit larger than the set, the whole set is returned.
    """
    if limit is None:
        return rows

    taken: dict[str, int] = {}
    picked: list[QaPair] = []
    for row in rows:
        key = getattr(row, "generator", "") or ""
        if taken.get(key, 0) >= limit:
            continue
        taken[key] = taken.get(key, 0) + 1
        picked.append(row)
    return picked


def active_pairs(space: str, settings: Settings | None = None) -> list[QaPair]:
    """All the active items of a Space, newest first.

    Only ``active``: a screened-out pair would measure our own generator. The
    order is total (time, then id) so every run of a limited set takes the same
    questions; newest first so a limited run measures what this launch generated.
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        stmt = (
            select(QaPair)
            .where(QaPair.space == space, QaPair.status == PairStatus.ACTIVE.value)
            .order_by(QaPair.created_at.desc(), QaPair.id.desc())
        )
        rows = list(session.execute(stmt).scalars())
        for row in rows:
            session.expunge(row)
        return rows


def _active_pairs(
    space: str, limit: int | None, settings: Settings | None = None
) -> list[QaPair]:
    """The pairs that go into the test.

    Only active pairs that pass the web check gate (``runs.gate``). A frozen
    slice, when set, is the whole selection and ``limit`` does not apply to it:
    limiting it would bring back the drift the slice exists to prevent.
    """
    conf = settings or get_settings()
    rows = evaluable(active_pairs(space, conf), conf)
    if conf.question_set is not None:
        return apply_slice(
            load_slice(conf.question_set),
            rows,
            space=space,
            strict=conf.strict_question_set,
        )
    return pick_pairs(rows, limit)


def evaluation_gate(space: str, settings: Settings | None = None) -> str:
    """Why nothing can be asked on this Space; empty — something can.

    Non-empty when active questions exist and none passes the web check gate.
    An empty set is not this case: that is "nothing to ask" of its own.
    """
    conf = settings or get_settings()
    rows = active_pairs(space, conf)
    if not rows or evaluable(rows, conf):
        return ""
    return nothing_passed(len(rows), conf)


def build_context(
    fragments: list[dict[str, Any]],
    endpoint_answer: str,
    *,
    source: ContextSource,
    limit: int,
    oracle: str = "",
) -> str:
    """Assemble what is mixed in with the question in arm C.

    The chunks are numbered and labelled with the file name, so the answer shows
    which of them it relied on and an auditor can check that against the prompt.

    Args:
        fragments: What the endpoint found, in the order returned
        endpoint_answer: The endpoint's finished answer, if it gave one
        source: What exactly to mix in
        limit: How many top chunks to take
        oracle: The pair's source chunk — the ceiling, retrieval takes no part

    Returns:
        The context text; empty if there is nothing to mix in
    """
    if source is ContextSource.ORACLE_CHUNK:
        return f"[1] source fragment\n{oracle}".strip() if oracle else ""

    parts: list[str] = []
    if source in _NEEDS_FRAGMENTS:
        for number, doc in enumerate(fragments[:limit], start=1):
            text = str(doc.get("content") or "").strip()
            if not text:
                continue
            name = str(doc.get("file_name") or "").strip()
            head = f"[{number}] {name}" if name else f"[{number}]"
            parts.append(f"{head}\n{text}")

    if (
        source in _NEEDS_ANSWER
        and endpoint_answer
        and not endpoint_answer.startswith(ERROR_PREFIX)
    ):
        parts.append(f"[endpoint answer]\n{endpoint_answer.strip()}")

    return "\n\n".join(parts)


def with_context_prompt(question: str, context: str) -> str:
    """The question and the material, as one prompt.

    The question comes first, so the model reads it before the material.
    """
    return f"Question:\n{question}\n\nMaterial:\n{context}\n\nAnswer the question."


def arm_web_search(
    mode: ContextMode, subject: Provider, settings: Settings
) -> tuple[bool, str]:
    """Whether the tested model searches the web in this arm, and how."""
    role = "closed_book" if mode is ContextMode.CLOSED_BOOK else "with_context"
    return web_search_for(settings, role, subject.model)


def _ask_model(
    question: str,
    temperature: float,
    *,
    provider: Provider,
    settings: Settings,
) -> tuple[str, dict[str, Any]]:
    """Ask the model directly, without a single corpus chunk."""
    searching, engine = arm_web_search(ContextMode.CLOSED_BOOK, provider, settings)
    return chat(
        CLOSED_BOOK_SYSTEM,
        question,
        provider=provider,
        temperature=temperature,
        max_tokens=settings.answer_max_tokens,
        settings=settings,
        web_search=searching,
        web_search_engine=engine or "auto",
        role=cost.SUBJECTS,
    )


def _ask_model_with_context(
    question: str,
    temperature: float,
    *,
    provider: Provider,
    settings: Settings,
    context: str,
) -> tuple[str, dict[str, Any]]:
    """Ask the model with the context already assembled.

    The context is fixed rather than retrieved afresh per trial: monte_carlo
    measures the spread of the model's answers, not of the retrieval.
    """
    searching, engine = arm_web_search(
        ContextMode.MODEL_WITH_CONTEXT, provider, settings
    )
    return chat(
        _WITH_CONTEXT_SYSTEM,
        with_context_prompt(question, context),
        provider=provider,
        temperature=temperature,
        max_tokens=settings.answer_max_tokens,
        settings=settings,
        web_search=searching,
        web_search_engine=engine or "auto",
        role=cost.SUBJECTS,
    )


# Why an arm can be unmeasurable, as codes: a code goes out to a UI that words
# it in its reader's language. The prose below is for the console and the log.
NO_FRAGMENTS_TO_MIX = "summary_hides_fragments"
NO_ANSWER_TO_MIX = "raw_has_no_answer_to_mix"

_BLOCKER_PROSE: dict[str, str] = {
    NO_FRAGMENTS_TO_MIX: (
        "an endpoint in summary mode cuts the chunks found out of the answer — there "
        "is nothing to mix in in arm C; raw or both mode is needed, or "
        "BENCH_CONTEXT_SOURCE=endpoint_answer"
    ),
    NO_ANSWER_TO_MIX: (
        "an endpoint in raw mode does not formulate an answer — there is nothing to "
        "mix in in arm C; summary or both mode is needed, or "
        "BENCH_CONTEXT_SOURCE=endpoint_fragments"
    ),
}


def blocker_code(mode: ContextMode, endpoint_mode: str, source: ContextSource) -> str:
    """The code of the reason this arm is not measurable on this endpoint.

    The owner sets the endpoint mode: ``raw`` returns only chunks, ``summary``
    only prose (and CUTS the references out), ``both`` returns both. An unknown
    mode (it could not be read) is no reason to refuse the run.

    Returns:
        The reason code, or an empty string if the arm is measurable
    """
    if not endpoint_mode:
        return ""

    if mode is ContextMode.MODEL_WITH_CONTEXT:
        if source in _NEEDS_FRAGMENTS and endpoint_mode == "summary":
            return NO_FRAGMENTS_TO_MIX
        if source is ContextSource.ENDPOINT_ANSWER and endpoint_mode == "raw":
            return NO_ANSWER_TO_MIX
    return ""


def arm_blocker(mode: ContextMode, endpoint_mode: str, source: ContextSource) -> str:
    """The same decision, but in words — for the console and for a run note."""
    return _BLOCKER_PROSE.get(blocker_code(mode, endpoint_mode, source), "")


def _retrieval_needs_prose(source: ContextSource) -> bool:
    """Whether arm C reads the endpoint's prose; otherwise one token is asked for."""
    return source in _NEEDS_ANSWER


def _elapsed(usage: dict[str, Any], started: float) -> float:
    """What the answer cost: a reused answer carries the time of its own call."""
    recorded = usage.get("elapsed")
    if isinstance(recorded, int | float):
        return float(recorded)
    return time.time() - started


def _refused_by(exc: LLMError, subject: Provider) -> str:
    """The answerer's name when the provider refused it, empty when it merely failed.

    A hard refusal (wrong name, spent key) is a rig-wide problem, not one
    question's result.
    """
    return subject.model if isinstance(exc, LLMFatalError) else ""


def _closed_book_asked(
    pair: QaPair,
    answer: str,
    usage: dict[str, Any],
    started: float,
    refused: str = "",
) -> Asked:
    """Arm A: the model answer, with nothing mixed in."""
    return Asked(
        answer=answer,
        usage=usage,
        latency=_elapsed(usage, started),
        system=CLOSED_BOOK_SYSTEM,
        user=pair.question,
        retrieval=_empty_retrieval(),
        context_source=ContextSource.NONE,
        call_failed=is_error(answer),
        refused=refused,
    )


def _material_for(
    pair: QaPair,
    outcome: dict[str, Any] | None,
    *,
    source: ContextSource,
    settings: Settings,
) -> tuple[dict[str, Any], str]:
    """The retrieval and the arm C context assembled from it.

    ``outcome`` is None for the oracle source, which does not call the endpoint.
    """
    if outcome is None:
        retrieval = _empty_retrieval()
        endpoint_answer = ""
    else:
        retrieval = check_retrieval(
            outcome["documents"], pair, max_chars=settings.fragment_max_chars
        )
        endpoint_answer = str(outcome["answer"])

    context = build_context(
        retrieval["retrieved"],
        endpoint_answer,
        source=source,
        limit=settings.context_docs,
        oracle=pair.context,
    )
    return retrieval, context


def _no_material_asked(
    pair: QaPair, retrieval: dict[str, Any], source: ContextSource, started: float
) -> Asked:
    """Retrieval returned nothing to ask the model about.

    Recorded as a failure, so it stays out of the denominator of the shares.
    """
    return Asked(
        answer=f"{ERROR_PREFIX} the context is empty: the endpoint returned "
        f"no material",
        latency=time.time() - started,
        system=_WITH_CONTEXT_SYSTEM,
        user=pair.question,
        retrieval=retrieval,
        context_source=source,
    )


def _with_context_asked(
    *,
    answer: str,
    usage: dict[str, Any],
    user: str,
    retrieval: dict[str, Any],
    source: ContextSource,
    context: str,
    started: float,
    refused: str = "",
) -> Asked:
    """Arm C: the model answer together with the material it is built on."""
    return Asked(
        answer=answer,
        usage=usage,
        latency=_elapsed(usage, started),
        system=_WITH_CONTEXT_SYSTEM,
        user=user,
        retrieval=retrieval,
        context_source=source,
        context=context,
        call_failed=is_error(answer),
        refused=refused,
    )


async def aask_once(
    pair: QaPair,
    mode: ContextMode,
    *,
    space: SpaceConfig,
    settings: Settings,
    subject: Provider,
    source: ContextSource,
    pool: Pool,
    cache: RunCache,
) -> Asked:
    """Ask one question the way the arm prescribes, over the pool's lanes and
    through the cache.

    The calls go off to worker threads, and the endpoint and the model are
    called only for what was not asked yet in this launch: the retrieval for a
    question is shared by every model and block, and an answer at zero
    temperature is the same for the same prompt.
    """
    searching, engine = arm_web_search(mode, subject, settings)
    started = time.time()
    usage: dict[str, Any] = {}
    refused = ""
    if mode is ContextMode.CLOSED_BOOK:
        try:
            answer, usage = await cache.answer(
                subject,
                CLOSED_BOOK_SYSTEM,
                pair.question,
                pool=pool,
                settings=settings,
                web_search=searching,
                web_search_engine=engine or "auto",
            )
        except LLMError as exc:
            answer = f"{ERROR_PREFIX} {exc}"
            refused = _refused_by(exc, subject)
        return _closed_book_asked(pair, answer, usage, started, refused)

    fetched: dict[str, Any] | None = None
    if source is not ContextSource.ORACLE_CHUNK:
        fetched = await cache.endpoint(
            space,
            pair.question,
            need_prose=_retrieval_needs_prose(source),
            pool=pool,
            settings=settings,
        )
    retrieval, context = _material_for(pair, fetched, source=source, settings=settings)
    if not context:
        return _no_material_asked(pair, retrieval, source, started)

    user = with_context_prompt(pair.question, context)
    try:
        answer, usage = await cache.answer(
            subject,
            _WITH_CONTEXT_SYSTEM,
            user,
            pool=pool,
            settings=settings,
            web_search=searching,
            web_search_engine=engine or "auto",
        )
    except LLMError as exc:
        answer = f"{ERROR_PREFIX} {exc}"
        refused = _refused_by(exc, subject)

    return _with_context_asked(
        answer=answer,
        usage=usage,
        user=user,
        retrieval=retrieval,
        source=source,
        context=context,
        started=started,
        refused=refused,
    )


# The ``usage`` fields copied into the audit record's ``call``.
_AUDITED_CALL_FIELDS = (
    "finish_reason",
    "truncated",
    "length_retry",
    # How far the budget climbed: a cut-off is retried with a doubled cap, and
    # ``max_tokens`` is the budget the call ended on.
    "length_retries",
    "max_tokens",
    "attempts",
    # Taken from an identical call earlier in the launch; the call the other
    # fields describe did not happen here.
    "reused",
    # The engine searched with (or False), how search was given (tool or
    # plugin), whether the tool was forced, the searches the provider reports,
    # and why the call was retried with the Exa plugin.
    "web_search",
    "web_search_via",
    "web_search_forced",
    "web_search_requests",
    "web_search_retry",
    # USD of the call (None: not priced).
    "cost_usd",
)


def audit_record(asked: Asked, verdict: Grade, settings: Settings) -> dict[str, Any]:
    """The trail by which a verdict can be rechecked.

    What the answerer was asked (in arm C with the material mixed in), what the
    judge was asked, and the judge's raw reply. It cannot be rebuilt later: the
    prompts depend on the settings of the moment.
    """
    if not settings.audit_log:
        return {}
    # Prompts and replies whole (the export shows them); ``context`` repeats
    # what the prompt carries, so it alone is cut.
    cut = settings.audit_max_chars
    record: dict[str, Any] = {
        "responder_system": asked.system,
        "responder_prompt": asked.user,
        "context_source": asked.context_source.value,
    }
    if asked.usage:
        # A truncated answer is judged like any other; the record says so.
        record["call"] = {
            key: asked.usage[key] for key in _AUDITED_CALL_FIELDS if key in asked.usage
        }
        if asked.usage.get("web_search"):
            citations = list(asked.usage.get("citations") or [])
            record["citations"] = citations
            # Search was offered, nothing searched and nothing cited.
            record["web_search_unused"] = search_unused(asked.usage)
            if record["web_search_unused"]:
                record["web_search_unused_reason"] = unused_reason(
                    record["call"], asked.answer
                )
    if asked.context:
        record["context"] = asked.context[:cut]
    return record | judge_trail(verdict)


@dataclass(slots=True)
class _Pass:
    """What every question of one pass shares, handed to its coroutines."""

    space: SpaceConfig
    mode: ContextMode
    block: EvalBlock
    source: ContextSource
    settings: Settings
    subject: Provider
    response_type: str
    per_judge: dict[str, tuple[Provider, str, RunReport]]
    pool: Pool
    cache: RunCache
    progress: Progress
    # Shared by the passes running at once. ``launch.units`` bounds the
    # questions in work (the pool lanes count calls): the stop check has to
    # happen when a question is dispatched, and every question's coroutine is
    # created up front.
    launch: Launch
    # Per judge, the questions it already has a usable verdict for: a run can
    # be interrupted in the middle of a panel.
    done: dict[str, set[str]] = field(default_factory=dict)
    # Record answers now and leave the verdicts for later.
    defer: bool = False


async def _verdict_for(pair: QaPair, asked: Asked, seat: Provider, ctx: _Pass) -> Grade:
    """Grade one answer with one judge, by the item's kind (``grade_item``)."""
    return await ctx.pool.to_model(
        grade_item,
        Gradable.of(pair),
        asked.answer,
        citations=answer_citations(asked.usage),
        settings=ctx.settings,
        judge=seat,
        defer=ctx.defer,
        wrap=partial(_timed_judge, ctx, seat),
    )


def _called_judge(verdict: Grade) -> bool:
    """A judge model was called (not a letter or span match, not deferred)."""
    return bool(verdict.judge_user) and verdict.verdict is not Verdict.PENDING


def _timed_judge(
    ctx: _Pass, seat: Provider, fn: Callable[..., Grade]
) -> Callable[..., Grade]:
    return ctx.pool.clock.timed(
        seat.model,
        JUDGE,
        fn,
        failed=lambda verdict: verdict.failed,
        counted=_called_judge,
    )


async def _under_pressure(
    pair: QaPair, asked: Asked, seat: Provider, ctx: _Pass
) -> DenialOutcome:
    """Push at a correct answer in the same dialogue it was obtained in.

    The rounds are sequential, so the whole exchange takes one model lane.
    """
    searching, engine = arm_web_search(ctx.mode, ctx.subject, ctx.settings)
    return await ctx.pool.to_model(
        run_denial_loop,
        Gradable.of(pair),
        asked.answer,
        subject=ctx.subject,
        settings=ctx.settings,
        judge=seat,
        system=asked.system,
        first_prompt=asked.user,
        web_search=searching,
        web_search_engine=engine or "auto",
        record=ctx.pool.clock.record,
    )


async def _repeated(
    pair: QaPair, asked: Asked, seat: Provider, ctx: _Pass
) -> MonteCarloOutcome:
    """Ask the same question many times at different temperatures.

    The repeats go the way the first answer went (alone in arm A, with the same
    context in arm C), past the cache since their temperature is not zero. They
    are independent and run side by side; the outcome keeps the plan order.
    """
    asker: Callable[[str, float], tuple[str, dict[str, Any]]]
    if ctx.mode is ContextMode.MODEL_WITH_CONTEXT:
        asker = partial(
            _ask_model_with_context,
            provider=ctx.subject,
            settings=ctx.settings,
            context=asked.context,
        )
    else:
        asker = partial(_ask_model, provider=ctx.subject, settings=ctx.settings)

    clock = ctx.pool.clock
    item = Gradable.of(pair)
    trials = await asyncio.gather(
        *(
            ctx.pool.to_model(
                monte_carlo_trial,
                item,
                temperature,
                ask=clock.timed(ctx.subject.model, ANSWER, asker),
                settings=ctx.settings,
                judge=seat,
                wrap=partial(_timed_judge, ctx, seat),
            )
            for temperature in monte_carlo_plan(ctx.settings)
        )
    )
    return tally_monte_carlo(trials)


async def _judge_one(pair: QaPair, asked: Asked, seat_key: str, ctx: _Pass) -> None:
    """Take one answer through to a database record in the eyes of one judge."""
    seat, run_id, entry = ctx.per_judge[seat_key]
    if seat.model in ctx.launch.refused:
        # Refused outright in this pass or another: stood down for the rest.
        return
    if pair.id in ctx.done.get(seat.model, ()):
        # This judge already has a usable verdict for this question.
        return
    entry.asked += 1

    verdict = await _verdict_for(pair, asked, seat, ctx)
    save = partial(
        _save_result,
        pair=pair,
        asked=asked,
        run_id=run_id,
        seat=seat,
        responder=entry.model,
        ctx=ctx,
    )

    if verdict.verdict is Verdict.PENDING:
        # No verdict yet, so no blocks or grounding: pressure applies only to
        # an answer known to be correct.
        await ctx.pool.to_storage(
            save, verdict=verdict, extra={}, grounded=None, grounded_note=""
        )
        entry.deferred += 1
        return

    extra: dict[str, Any] = {}
    if verdict.behavior:
        extra["behavior"] = verdict.behavior

    item = Gradable.of(pair)
    if ctx.block is EvalBlock.DENIAL_LOOP and not item.control and holds(item, verdict):
        # Pressure goes only at a right answer to an ordinary item.
        denial = await _under_pressure(pair, asked, seat, ctx)
        extra["denial"] = {
            "rounds": denial.rounds,
            "flipped": denial.flipped,
            "flip_round": denial.flip_round,
            "note": denial.note,
            "limit": denial.limit,
            "log": denial.log,
            "judge_system": denial.judge_system,
        }
        if denial.flipped:
            # An answer given up under pressure is not counted as right.
            verdict = replace(
                verdict,
                verdict=Verdict.HALLUCINATE,
                reasoning=f"gave in at round {denial.flip_round}: {denial.note}",
            )

    if ctx.block is EvalBlock.MONTE_CARLO:
        trials = await _repeated(pair, asked, seat, ctx)
        extra["monte_carlo"] = {
            "trials": trials.trials,
            "accuracy": round(trials.accuracy, 4),
            "consistency": trials.consistency,
            "by_temperature": trials.by_temperature,
            "note": trials.note,
            "log": trials.log,
            "judge_system": trials.judge_system,
        }

    # Mechanical resemblance to the gold answer, independent of the judge; only
    # for prose answers, and never for a failure.
    if ctx.settings.text_metrics and not verdict.failed and applies_to(pair.generator):
        # In a worker thread: BERTScore is a model run.
        scores = await ctx.pool.to_model(
            score_text, asked.answer, pair.answer, ctx.settings
        )
        if scores:
            extra["text_metrics"] = scores

    grounded: bool | None = None
    grounded_note = ""
    if ctx.mode in ENDPOINT_ARMS and not verdict.failed:
        fragments = [
            str(doc.get("content", ""))
            for doc in asked.retrieval["retrieved"]
            if doc.get("content")
        ]
        grounded, grounded_note = await ctx.pool.to_model(
            (
                ctx.pool.clock.timed(seat.model, JUDGE, check_grounded)
                if fragments
                else check_grounded
            ),
            asked.answer,
            fragments,
            judge=seat,
            settings=ctx.settings,
        )

    await ctx.pool.to_storage(
        save,
        verdict=verdict,
        extra=extra,
        grounded=grounded,
        grounded_note=grounded_note,
    )

    if verdict.fatal:
        # The judge was refused, not the answerer: it stands down in every pass
        # of the launch while the rest of the panel carries on.
        _stand_down(seat, entry, ctx)

    entry.count(verdict)
    # Only a failed call: a failed grade also covers an item with no key facts.
    if verdict.failed and not entry.failure_sample and is_error(asked.answer):
        entry.failure_sample = asked.answer


def _save_result(
    *,
    pair: QaPair,
    asked: Asked,
    verdict: Grade,
    extra: dict[str, Any],
    grounded: bool | None,
    grounded_note: str,
    run_id: str,
    seat: Provider,
    responder: str,
    ctx: _Pass,
) -> None:
    """Write one verdict at once: a run can be interrupted at any point."""
    with session_scope(ctx.settings) as session:
        session.add(
            Result(
                id=uuid.uuid4().hex,
                run_id=run_id,
                qa_id=pair.id,
                space=ctx.space.key,
                endpoint=(ctx.space.endpoint if ctx.mode in ENDPOINT_ARMS else ""),
                endpoint_response_type=ctx.response_type,
                answer=asked.answer,
                verdict=verdict.verdict.value,
                reasoning=verdict.reasoning,
                expected_behavior=pair.expected_behavior,
                grounded=grounded,
                grounded_note=grounded_note,
                retrieval_hit=asked.retrieval["retrieval_hit"],
                retrieval_rank=asked.retrieval["retrieval_rank"],
                retrieved=asked.retrieval["retrieved"],
                extra=extra,
                audit=audit_record(asked, verdict, ctx.settings),
                latency_s=round(asked.latency, 2),
                model=responder,
                # Empty for a local model.
                served_by=str(asked.usage.get("served_by") or ""),
                judge_model=seat.model,
                judge_served_by=verdict.served_by,
            )
        )


def _stand_down(seat: Provider, entry: RunReport, ctx: _Pass) -> None:
    """A judge the provider refused outright grades nothing more in this launch.

    ``max_consecutive_failures`` of zero turns this off, as it does for a
    refused answerer.
    """
    if not ctx.settings.max_consecutive_failures or seat.model in ctx.launch.refused:
        return
    ctx.launch.refused.add(seat.model)
    entry.refused = seat.model
    entry.notes.append(f"judge {seat.model} was refused outright and stood down")
    logger.warning(f"{ctx.progress.label}: judge {seat.model} refused outright")
    if all(model in ctx.launch.refused for model in ctx.per_judge):
        ctx.progress.stop(f"the provider refused {seat.model} outright")


def _halted(ctx: _Pass) -> bool:
    """Whether this pass asks no further question: stopped, cancelled, refused."""
    if ctx.progress.stopped:
        return True
    if ctx.launch.halted():
        ctx.progress.stop("stopped by the owner")
        return True
    if ctx.subject.model in ctx.launch.refused:
        # Refused in another pass of the launch.
        ctx.progress.refuse(ctx.subject.model)
        return ctx.progress.stopped
    if ctx.per_judge and all(model in ctx.launch.refused for model in ctx.per_judge):
        ctx.progress.stop("the provider refused every judge of this pass")
        return True
    return False


async def _ask_and_judge(pair: QaPair, ctx: _Pass) -> None:
    """One question: asked once, shown to the whole panel.

    One answer for all the judges, so their divergence is not blended with the
    spread of the answers themselves.
    """
    async with ctx.launch.units:
        if _halted(ctx):
            return

        asked = await aask_once(
            pair,
            ctx.mode,
            space=ctx.space,
            settings=ctx.settings,
            subject=ctx.subject,
            source=ctx.source,
            pool=ctx.pool,
            cache=ctx.cache,
        )

        await asyncio.gather(
            *(_judge_one(pair, asked, key, ctx) for key in ctx.per_judge)
        )
        ctx.progress.step(failed=asked.call_failed, refused=asked.refused)
        if ctx.progress.refused:
            ctx.launch.refused.add(ctx.progress.refused)


def _open_runs(
    space: SpaceConfig,
    mode: ContextMode,
    *,
    block: EvalBlock,
    source: ContextSource,
    responder: str,
    vendor: str,
    seated: list[Provider],
    params: dict[str, Any],
    settings: Settings,
    subject: Provider,
    job_id: str | None = None,
) -> tuple[dict[str, tuple[Provider, str, RunReport]], list[RunReport]]:
    """Create one run per judge, so each judge's verdicts stay apart.

    ``params`` is the settings snapshot resumption selected by, passed in so
    both use the same one. What was actually served (``model_sent_as``,
    provider, build) is evidence about this run and goes beside the snapshot.
    """
    per_judge: dict[str, tuple[Provider, str, RunReport]] = {}
    reports: list[RunReport] = []
    for seat in seated:
        run_id = uuid.uuid4().hex
        with session_scope(settings) as session:
            session.add(
                Run(
                    id=run_id,
                    space=space.key,
                    endpoint=space.endpoint if mode in ENDPOINT_ARMS else "",
                    context_mode=mode.value,
                    context_source=source.value,
                    profile=settings.methodology_profile,
                    params=params,
                    block=block.value,
                    model=responder,
                    model_vendor=vendor,
                    model_sent_as=subject.wire_model,
                    model_provider=subject.kind.value,
                    model_build=subject.build,
                    judge_model=seat.model,
                    job_id=job_id,
                )
            )
        entry = RunReport(
            run_id=run_id,
            context_mode=mode,
            block=block,
            model=responder,
            judge=seat.model,
        )
        per_judge[seat.model] = (seat, run_id, entry)
        reports.append(entry)
    return per_judge, reports


async def arun_pass(
    space: SpaceConfig,
    mode: ContextMode,
    *,
    pool: Pool,
    cache: RunCache,
    limit: int | None = None,
    settings: Settings | None = None,
    subject: Provider,
    block: EvalBlock = EvalBlock.DIRECT,
    judges: Sequence[Provider] | None = None,
    context_source: ContextSource | None = None,
    resume: bool = False,
    defer_judging: bool = False,
    watch: Callable[[Progress], None] | None = None,
    job_id: str | None = None,
    launch: Launch | None = None,
) -> list[RunReport]:
    """Run a Space's questions through one arm with the whole panel of judges.

    The questions run concurrently; within a question the judges are
    independent; only the rounds of one pressure dialogue are sequential. The
    pool (bound to the launch's event loop) and the cache (shared by every pass
    of the launch) come from the caller.

    Args:
        space: The node under test
        mode: The measurement arm
        pool: The lanes and worker threads of the launch
        cache: What has already been asked and is therefore not asked again
        limit: How many questions to ask per generator; None — all the active ones
        settings: The process settings
        subject: The model under test
        block: The test block
        judges: The panel; None — from the settings
        context_source: What to mix in in arm C; None — from the settings
        resume: Do not re-ask what the judge already has a usable verdict for
        defer_judging: Collect the answers without calling a judge; the
            verdicts come later from the judging commands
        watch: Called after every answered question; it sees the progress and
            can stop the pass
        job_id: The launch these runs belong to
        launch: What the passes running at the same time share (question
            slots, refused names, the answerer's failure streak); None — this
            pass alone

    Returns:
        One report per judge, including those that recused themselves
    """
    conf = settings or get_settings()
    launch = launch if launch is not None else Launch(conf)
    pairs = _active_pairs(space.key, limit, conf)
    if mode is ContextMode.CLOSED_BOOK:
        source = ContextSource.NONE
    else:
        source = context_source or conf.context_source

    panel = list(judges) if judges else judge_providers(conf)
    # Refused outright in another pass of the launch: stood down.
    refused = [seat for seat in panel if seat.model in launch.refused]
    standing = [seat for seat in panel if seat.model not in launch.refused]
    if block is not EvalBlock.DIRECT:
        # Pressure and repeats measure the answerer, not the spread of
        # assessments, and cost several times as much: the first standing
        # judge alone.
        standing = standing[:1]

    responder = subject.model

    def unopened(judge: str, **fields: Any) -> RunReport:
        """A report for a pass that opened no run: an empty Run would read as work."""
        return RunReport(
            run_id="",
            context_mode=mode,
            block=block,
            model=responder,
            judge=judge,
            **fields,
        )

    if skips_monte_carlo(block, subject, conf):
        return [
            unopened(seat.model, notes=[monte_carlo_skip_note(responder)])
            for seat in standing
        ]

    reports = [
        unopened(
            seat.model,
            refused=seat.model,
            notes=[f"judge {seat.model} was refused outright"],
        )
        for seat in refused
    ]
    seated: list[Provider] = []
    for candidate in standing:
        if is_recused(candidate, subject, conf):
            # A recusal, not a refusal: the rest of the panel carries on.
            reports.append(
                unopened(
                    candidate.model,
                    notes=[
                        f"judge {candidate.model} recused itself: {responder} "
                        f"is from the same provider"
                    ],
                )
            )
            continue
        check_judge_independence(candidate, subject, conf)
        seated.append(candidate)

    if not seated:
        return reports

    response_type = (
        await pool.to_endpoint(endpoint_mode, space) if mode in ENDPOINT_ARMS else ""
    )

    blocker = arm_blocker(mode, response_type, source)
    if blocker:
        return [unopened(seat.model, notes=[blocker]) for seat in seated]

    if not pairs:
        held = evaluation_gate(space.key, conf)
        if held:
            # Active questions exist, none passed the web check.
            logger.warning(f"{space.key}: {held}")
            return reports + [unopened(seat.model, notes=[held]) for seat in seated]

    params = conf.measurement_params()
    done: dict[str, set[str]] = {}
    if resume:
        done = done_units(
            space.key,
            mode,
            source=source,
            block=block,
            model=responder,
            settings=conf,
            params=params,
            since=window_start(conf),
            need_verdict=not defer_judging,
        )

    # A question is asked when at least one judge still needs it: the answer is
    # one for the whole panel.
    pending = [
        pair
        for pair in pairs
        if any(pair.id not in done.get(seat.model, ()) for seat in seated)
    ]
    skipped = len(pairs) - len(pending)

    if pairs and not pending:
        # Nothing to do; the report finds the earlier verdicts by question.
        return reports + [
            unopened(
                seat.model,
                resumed=len(pairs),
                notes=[f"already done in full: {len(pairs)} items"],
            )
            for seat in seated
        ]

    per_judge, opened = _open_runs(
        space,
        mode,
        block=block,
        source=source,
        responder=responder,
        vendor=subject.vendor,
        seated=seated,
        params=params,
        settings=conf,
        subject=subject,
        job_id=job_id,
    )
    reports += opened

    if not pairs:
        for entry in opened:
            entry.notes.append("there are no active pairs — run generate first")
        return reports

    if done:
        # Per judge: a run can be interrupted in the middle of a panel.
        known = {pair.id for pair in pairs}
        for seat, _run_id, entry in per_judge.values():
            entry.resumed = len(done.get(seat.model, set()) & known)
    if skipped:
        for entry in opened:
            entry.notes.append(
                f"resumed: {skipped} items already done, asking {len(pending)}"
            )

    # The failure streak belongs to the answerer, over all its passes.
    streak = launch.streak(responder)
    progress = Progress(
        total=len(pending),
        label=f"{space.key}/{mode.value}/{block.value} [{responder}]",
        give_up_after=conf.max_consecutive_failures,
        watch=watch,
        shared=streak,
    )
    streak.members.append(progress)
    ctx = _Pass(
        space=space,
        mode=mode,
        block=block,
        source=source,
        settings=conf,
        subject=subject,
        response_type=response_type,
        per_judge=per_judge,
        pool=pool,
        cache=cache,
        progress=progress,
        launch=launch,
        done=done,
        defer=defer_judging,
    )
    try:
        await asyncio.gather(*(_ask_and_judge(pair, ctx) for pair in pending))
    finally:
        streak.members.remove(progress)

    if ctx.progress.stopped:
        for entry in opened:
            entry.notes.append(f"the run was stopped: {ctx.progress.fatal}")
            entry.stopped = ctx.progress.fatal
            if ctx.progress.refused:
                entry.refused = ctx.progress.refused
    return reports


def run_pass(
    space: SpaceConfig,
    mode: ContextMode,
    *,
    limit: int | None = None,
    settings: Settings | None = None,
    subject: Provider,
    block: EvalBlock = EvalBlock.DIRECT,
    judges: Sequence[Provider] | None = None,
    context_source: ContextSource | None = None,
    cache: RunCache | None = None,
    resume: bool = False,
    defer_judging: bool = False,
    watch: Callable[[Progress], None] | None = None,
    job_id: str | None = None,
) -> list[RunReport]:
    """``arun_pass`` from synchronous code, on an event loop of its own.

    Args:
        cache: The cache shared across the launch; None — its own, for this pass only
        resume: Do not re-ask what the judge already has a usable verdict for
        defer_judging: Collect the answers without calling a judge
        watch: The progress observer; it can also stop the pass
        job_id: The launch these runs belong to; None — started from the console

    Returns:
        One report per judge, including those that recused themselves
    """
    conf = settings or get_settings()
    shared = cache if cache is not None else RunCache(enabled=conf.reuse_answers)

    async def go() -> list[RunReport]:
        pool = Pool(conf)
        try:
            return await arun_pass(
                space,
                mode,
                pool=pool,
                cache=shared,
                limit=limit,
                settings=conf,
                subject=subject,
                block=block,
                judges=judges,
                context_source=context_source,
                resume=resume,
                defer_judging=defer_judging,
                watch=watch,
                job_id=job_id,
            )
        finally:
            pool.close()

    return asyncio.run(go())
