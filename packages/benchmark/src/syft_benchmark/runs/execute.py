"""Two arms over one dataset.

One and the same question is asked two ways, and each measures its own thing:

  * **A** (``closed_book``) — the model alone, without a single corpus chunk but
    with its web search on. A correct answer means the question is answerable
    without the publisher's data.
  * **C** (``model_with_context``) — the same model as in arm A, but what the
    endpoint returned is mixed in with the question. That is the model interaction
    with RAG.

Comparability rests on A and C differing by the publisher's context: one model,
one style of instruction, one judge. Arm B (``open_book``, the endpoint answering
by itself) is no longer measured; its results stay readable.

Both write into one table, differing in the ``context_mode`` and
``context_source`` fields, and are judged by one panel.

The questions go in a batch rather than one at a time: a run is busy waiting on a
socket, and waiting on them in turn is the very day within which a live set does
not get through even fifteen percent. The design of the parallelism and the cache
of what has already been asked live in ``runs/parallel.py``; what stays here is
WHAT exactly is asked.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
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
    subject_providers,
)
from syft_benchmark.llm.ollama import search_unused
from syft_benchmark.llm.roles import web_search_for
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
from syft_benchmark.runs.endpoint import (
    RETRIEVAL_ONLY_TOKENS,
    ask_endpoint,
    check_retrieval,
    endpoint_mode,
)
from syft_benchmark.runs.gate import evaluable, nothing_passed
from syft_benchmark.runs.judge import (
    ERROR_PREFIX,
    Grade,
    check_grounded,
    control_case,
    grade,
    grade_control,
    grade_key_facts,
    is_control,
    is_error,
)
from syft_benchmark.runs.parallel import Launch, Pool, Progress, RunCache
from syft_benchmark.runs.questionset import apply as apply_slice
from syft_benchmark.runs.questionset import load as load_slice
from syft_benchmark.runs.resume import done_units, window_start
from syft_benchmark.runs.textmetrics import applies_to, score_text
from syft_benchmark.runs.timing import ANSWER, JUDGE

# The arms in which a model under test answers. Every measured arm does.
MODEL_ARMS = (ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT)

# The arms for which the endpoint has to be called.
ENDPOINT_ARMS = (ContextMode.MODEL_WITH_CONTEXT,)

# The context sources that need the chunks that were found. An endpoint in summary
# mode cuts the references out of the answer — such an arm is not measurable with
# it, and that has to be said before the run rather than shown as zeros in the report.
_NEEDS_FRAGMENTS = (
    ContextSource.ENDPOINT_FRAGMENTS,
    ContextSource.ENDPOINT_BOTH,
)

# The context sources that need the endpoint PROSE, not only its retrieval.
_NEEDS_ANSWER = (
    ContextSource.ENDPOINT_ANSWER,
    ContextSource.ENDPOINT_BOTH,
)

_CLOSED_BOOK_SYSTEM = """\
Answer the question from your own knowledge.

If you are not sure, respond with ONLY: I don't know

Do not guess. An honest "I don't know" is better than a confident answer that \
might be wrong.
"""

# The arm C instruction deliberately repeats the form of the arm A instruction: the
# same abstention formula, the same ban on guessing. Should they diverge in style,
# the difference between the arms would also be measuring the wording of the prompt,
# whereas it must measure exactly the presence of context.
_WITH_CONTEXT_SYSTEM = """\
Answer the question using the material provided below the question.

If the material does not contain the answer, respond with ONLY: I don't know

Do not guess and do not fill gaps from your own knowledge. An honest "I don't \
know" is better than a confident answer that might be wrong. Material that \
looks related but does not state the answer is not an answer.
"""


@dataclass(slots=True)
class RunReport:
    """The result of one run."""

    run_id: str
    space: str
    context_mode: ContextMode
    block: EvalBlock = EvalBlock.DIRECT
    model: str = ""
    judge: str = ""
    context_source: ContextSource = ContextSource.NONE
    asked: int = 0
    correct: int = 0
    abstain: int = 0
    hallucinate: int = 0
    failed: int = 0
    # Control answers its web search supports: graded, not a hallucination.
    web_sourced: int = 0
    # How many verdicts were taken from a previous attempt rather than obtained now.
    # Without this number a resumed run would look like a run over three questions:
    # "asked 3" on a set of fifty is not a report but a riddle.
    resumed: int = 0
    # Answers recorded without a verdict: they will be judged separately.
    deferred: int = 0
    # The name the provider refused outright during this pass, when it did.
    # Read by the measurement: every later pass with the same name would be
    # bought at the price of a whole set and come back with the same refusal.
    refused: str = ""
    # The text of one failed call, kept so the reason can be told without
    # opening the database. A spent key, a wrong model name, a network that
    # dropped and a node that is down all end the run the same way — with zero
    # verdicts — and this line is the only thing that tells them apart. One is
    # enough: when nothing was graded at all, they are all the same failure.
    failure_sample: str = ""
    notes: list[str] = field(default_factory=list)
    # Why the pass ended before its last question; empty — it did not.
    stopped: str = ""

    @property
    def graded(self) -> int:
        """The assessed answers — the denominator of every share."""
        return self.correct + self.abstain + self.hallucinate + self.web_sourced


@dataclass(frozen=True, slots=True)
class Asked:
    """The answer to one question along with the trace of how it was obtained.

    The prompt is kept beside the answer rather than reassembled afterwards: it
    depends on the settings of the moment — the retrieval threshold, the number of
    chunks mixed in — and those change. An auditor arriving six months later has to
    see the text that actually went to the model.
    """

    answer: str
    latency: float
    system: str
    user: str
    retrieval: dict[str, Any]
    context_source: ContextSource
    context: str = ""
    # What the provider said about the call itself: finish_reason, whether the answer
    # was truncated at the token ceiling, how many attempts were needed. A port of P11
    # from LiveTruth: a truncation used to come to light after the fact, from strange
    # figures in a finished report, whereas it should be visible in the record.
    usage: dict[str, Any] = field(default_factory=dict)
    # There is no answer because the call did not happen — not because there was
    # nothing to answer about. The difference matters: an empty context at a high
    # retrieval threshold is a legitimate outcome of the measurement, whereas a node
    # that has gone down or a wrong key is a state of the rig, and there is no reason
    # to put up with it for hundreds of questions in a row.
    call_failed: bool = False
    # The answerer's name, when the provider refused it outright rather than
    # failing to answer. A refusal is a statement about the name, the key or the
    # money: asking the rest of the set buys the same sentence once per item.
    refused: str = ""


def _empty_retrieval() -> dict[str, Any]:
    return {"retrieval_hit": None, "retrieval_rank": None, "retrieved": []}


def pick_pairs(rows: list[QaPair], limit: int | None) -> list[QaPair]:
    """Select ``limit`` items PER GENERATOR.

    A port of the phase-3 limit from LiveTruth, where it is also applied to each set
    separately. The point is that a generator is a distinct skill rather than a share
    of the sample: number masking measures precision about a figure, multihop the
    ability to connect two facts, tiered an extended explanation, the control ones
    the ability to stay silent. The answer "the model is correct 71% of the time"
    means something only when all the skills stand behind it, rather than those that
    happened to land in the sample.

    Hence the rejection of a total limit divided among the generators. It looked
    sensible, but at a small value it simply threw some generators out: ten items
    across ten generators — and half were not tested at all, while the report called
    the result the model accuracy.

    The halves of the set survive on their own: each generator produces items of
    EXACTLY one half — answerable, unanswerable or false-premise — and having the
    generators represented entails having the halves represented. A separate
    round-robin over halves is unnecessary and harmful: there are two control
    generators against eight ordinary ones, and such a round would give them two
    thirds of the sample.

    Which generators take part at all is decided by the composition of the set, and
    that by ``BENCH_DISABLED_GENERATORS`` at the generation stage. The limit does not
    make that choice and must not: selection by a silent decision is the worst kind
    of configuration.

    The order within a generator is the order given — newest first, as
    ``active_pairs`` returns them; with a limit larger than the set the whole set
    is returned.
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

    Only ``active``: a screened-out gold answer understates a good endpoint score,
    and letting it into the measurement means measuring our own generator.

    The order is total — time plus identifier. The limit is applied anew for every
    run, so on equal timestamps the database would be free to hand different
    queries different items and the models would be compared on different
    questions.

    TEMPORARY: descending, so a limited run measures what this launch generated.
    The selection is to be reworked; the answer is a question set
    (``question_set``) or a sampling rule, not a direction.
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

    Only active pairs that pass the web check gate (``runs.gate``). The frozen
    slice, if one is set, is the whole selection: ``limit`` is not applied
    with it at all. The limit would select from what has already been selected and
    would bring back exactly the drift of the set the slice exists to prevent.
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

    The chunks are numbered and labelled with the file name: that way the model
    answer shows which of them it relied on, and an auditor can check that against
    the saved prompt.

    Args:
        fragments: What the endpoint found, in the order returned
        endpoint_answer: The endpoint finished answer, if it gave one
        source: What exactly to mix in
        limit: How many top chunks to take
        oracle: The pair source chunk — the ceiling, retrieval takes no part

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

    wants_answer = source in _NEEDS_ANSWER
    if (
        wants_answer
        and endpoint_answer
        and not endpoint_answer.startswith(ERROR_PREFIX)
    ):
        parts.append(f"[endpoint answer]\n{endpoint_answer.strip()}")

    return "\n\n".join(parts)


def with_context_prompt(question: str, context: str) -> str:
    """The question and the material given, as one prompt.

    The question comes first: that way the model reads it before the material and
    does not adjust it to what was found.
    """
    return f"Question:\n{question}\n\nMaterial:\n{context}\n\nAnswer the question."


def arm_web_search(
    mode: ContextMode, subject: Provider | None, settings: Settings
) -> tuple[bool, str]:
    """Whether the tested model searches the web in this arm, and how."""
    role = "closed_book" if mode is ContextMode.CLOSED_BOOK else "with_context"
    model = subject.model if subject is not None else settings.generator_model
    return web_search_for(settings, role, model)


def _ask_model(
    question: str,
    temperature: float,
    *,
    provider: Provider,
    settings: Settings,
) -> tuple[str, dict[str, Any]]:
    """Ask the model directly, without a single corpus chunk."""
    searching, engine = arm_web_search(ContextMode.CLOSED_BOOK, provider, settings)
    answer, _usage = chat(
        _CLOSED_BOOK_SYSTEM,
        question,
        provider=provider,
        temperature=temperature,
        max_tokens=settings.answer_max_tokens,
        settings=settings,
        web_search=searching,
        web_search_engine=engine or "auto",
        role=cost.SUBJECTS,
    )
    return answer, _usage


def _ask_model_with_context(
    question: str,
    temperature: float,
    *,
    provider: Provider,
    settings: Settings,
    context: str,
) -> tuple[str, dict[str, Any]]:
    """Ask the model with the context already assembled.

    The context is fixed rather than searched afresh on every trial: monte_carlo
    measures the spread of the model answers, and re-asking retrieval would mean
    blending that with the spread of the retrieval.
    """
    searching, engine = arm_web_search(
        ContextMode.MODEL_WITH_CONTEXT, provider, settings
    )
    answer, _usage = chat(
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
    return answer, _usage


# Why an arm can be unmeasurable — as codes. A code goes out, not a sentence: the
# reason is displayed by a foreign UI, in the language of its own reader — the same
# rule under which the card hands over trust.flags. The prose below is ours, for the
# console and the log.
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

    The endpoint mode is set by the owner, and it decides what is available at all:
    ``raw`` returns only chunks, ``summary`` only prose and CUTS the references out
    of the answer, ``both`` returns both. The incompatibility has to be named before
    the run: otherwise arm C on a summary endpoint will run without a single chunk
    and show reassuring zeros.

    Returns:
        The reason code, or an empty string if the arm is measurable
    """
    if not endpoint_mode:
        # The card was not read — that is no reason to refuse the run: a diagnostic
        # failure is not the same as a known incompatibility.
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
    """Whether arm C needs the endpoint prose and not only its retrieval.

    Over chunks it is not read at all, and on a ``both`` endpoint the request starts
    generation anyway. It cannot be cancelled, but it can be asked for a single
    token: there is no reason to wait for text that is thrown away at once.
    """
    return source in _NEEDS_ANSWER


def _elapsed(usage: dict[str, Any], started: float) -> float:
    """What the answer cost.

    A reused answer carries the time of ITS OWN call rather than of a dictionary
    lookup: otherwise the log would hold a model answering in zero seconds — a number
    an auditor must not and cannot believe.
    """
    recorded = usage.get("elapsed")
    if isinstance(recorded, int | float):
        return float(recorded)
    return time.time() - started


def _refused_by(exc: LLMError, subject: Provider | None) -> str:
    """The answerer's name when the provider refused it, empty when it merely failed.

    Distinguishes a hard refusal (wrong name, spent key) from a plain failure,
    so callers don't fold a rig-wide problem into a single question's result.
    """
    return _subject_of(subject).model if isinstance(exc, LLMFatalError) else ""


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
        system=_CLOSED_BOOK_SYSTEM,
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

    The oracle source does not call the endpoint at all — it is the ceiling, where
    the context certainly contains the answer, and it separates a retrieval miss from
    the model inability. So ``outcome`` is optional here.
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
    """An empty context is not a model answer but a state of the rig.

    Retrieval returned nothing, and there is nothing to ask the model about. Recorded
    as a failure, so as not to land in the denominator of the shares.
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


def _subject_of(subject: Provider | None) -> Provider:
    """The model under test in the arms where it answers.

    In arms A and C it is assigned before the first question, and cannot be empty
    here. Asserting that explicitly is better than building a cache key out of
    ``None``.
    """
    if subject is None:
        raise ValueError("the arm answers with a model, but no model is assigned")
    return subject


def ask_once(
    pair: QaPair,
    mode: ContextMode,
    *,
    space: SpaceConfig,
    settings: Settings,
    subject: Provider | None,
    source: ContextSource,
) -> Asked:
    """Ask one question the way the arm prescribes.

    The direct road: every call goes out at once and is awaited right here. The run
    goes past it — through ``aask_once``, where the same steps are laid out over the
    lanes and the cache — and this function stays what it was: one question without
    any wrapping. Both roads are assembled from the same parts, and that is the only
    way to keep them in agreement.
    """
    searching, engine = arm_web_search(mode, subject, settings)
    if mode is ContextMode.CLOSED_BOOK:
        started = time.time()
        usage: dict[str, Any] = {}
        refused = ""
        try:
            answer, usage = chat(
                _CLOSED_BOOK_SYSTEM,
                pair.question,
                provider=subject,
                temperature=0.0,
                max_tokens=settings.answer_max_tokens,
                settings=settings,
                web_search=searching,
                web_search_engine=engine or "auto",
                role=cost.SUBJECTS,
            )
        except LLMError as exc:
            answer = f"{ERROR_PREFIX} {exc}"
            refused = _refused_by(exc, subject)
        return _closed_book_asked(pair, answer, usage, started, refused)

    started = time.time()
    outcome: dict[str, Any] | None = None
    if source is not ContextSource.ORACLE_CHUNK:
        outcome = ask_endpoint(
            space,
            pair.question,
            settings=settings,
            max_tokens=(
                None if _retrieval_needs_prose(source) else RETRIEVAL_ONLY_TOKENS
            ),
        )
    retrieval, context = _material_for(pair, outcome, source=source, settings=settings)
    if not context:
        return _no_material_asked(pair, retrieval, source, started)

    user = with_context_prompt(pair.question, context)
    usage = {}
    refused = ""
    try:
        answer, usage = chat(
            _WITH_CONTEXT_SYSTEM,
            user,
            provider=subject,
            temperature=0.0,
            max_tokens=settings.answer_max_tokens,
            settings=settings,
            web_search=searching,
            web_search_engine=engine or "auto",
            role=cost.SUBJECTS,
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


async def aask_once(
    pair: QaPair,
    mode: ContextMode,
    *,
    space: SpaceConfig,
    settings: Settings,
    subject: Provider | None,
    source: ContextSource,
    pool: Pool,
    cache: RunCache,
) -> Asked:
    """The same thing, but over the lanes and through the cache.

    There are exactly two differences from ``ask_once``, and neither is about the
    arithmetic of the measurement:

      * the call goes off to a thread, and the event loop gets on with the next
        question instead of sitting on a socket;
      * the endpoint and the model are called only for what has not been asked yet.
        The retrieval for a question is one for all the models under test and all
        the blocks, and an answer at zero temperature is the same for the same prompt.

    What goes to the model and what is written into ``Asked`` does not change —
    otherwise the figures of a parallel run could not be compared with the earlier ones.
    """
    searching, engine = arm_web_search(mode, subject, settings)
    if mode is ContextMode.CLOSED_BOOK:
        started = time.time()
        usage: dict[str, Any] = {}
        refused = ""
        try:
            answer, usage = await cache.answer(
                _subject_of(subject),
                _CLOSED_BOOK_SYSTEM,
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

    started = time.time()
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
    usage = {}
    refused = ""
    try:
        answer, usage = await cache.answer(
            _subject_of(subject),
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


def audit_record(asked: Asked, verdict: Grade, settings: Settings) -> dict[str, Any]:
    """The trail by which a verdict can be rechecked.

    The benchmark number is a judge model opinion about text that is not in the
    report. The auditor needs both: what the answerer was asked with (in arm C,
    together with the material mixed in) and what the judge was asked with, plus the
    judge raw answer before parsing. This cannot be assembled after the fact: the
    prompt depends on the settings of the moment.
    """
    if not settings.audit_log:
        return {}
    # Prompts and replies whole (the export shows them); ``context`` repeats
    # what the prompt carries, so it alone stays cut.
    cut = settings.audit_max_chars
    record: dict[str, Any] = {
        "responder_system": asked.system,
        "responder_prompt": asked.user,
        "context_source": asked.context_source.value,
    }
    if asked.usage:
        # A truncation at the token ceiling must be visible in the record rather than
        # come to light after the fact from strange figures in the report: a truncated
        # answer is judged like an ordinary one, and the auditor needs to know the
        # model was not allowed to finish.
        record["call"] = {
            key: asked.usage[key]
            for key in (
                "finish_reason",
                "truncated",
                "length_retry",
                # How far the budget had to climb: a cut-off is retried with a
                # doubled cap until it fits, so the count is what says how near
                # the answer came to being impossible.
                "length_retries",
                "attempts",
                # The answer is taken from one already obtained in this launch: the
                # same prompt at zero temperature. For an auditor this is no trifle —
                # the call described by the neighbouring fields did not happen here.
                "reused",
                # The engine the answer searched with, or False; how search was
                # given (tool or plugin), whether the tool was forced, and how
                # many searches the provider reports.
                "web_search",
                "web_search_via",
                "web_search_forced",
                "web_search_requests",
                # USD of the call (None: not priced); with ``reused`` the call
                # was made earlier in the launch.
                "cost_usd",
            )
            if key in asked.usage
        }
        if asked.usage.get("web_search"):
            citations = list(asked.usage.get("citations") or [])
            record["citations"] = citations
            # Search was offered, nothing searched and nothing cited.
            record["web_search_unused"] = search_unused(asked.usage)
    if asked.context:
        record["context"] = asked.context[:cut]
    if verdict.judge_user:
        record["judge_system"] = verdict.judge_system
        record["judge_prompt"] = verdict.judge_user
        record["judge_raw"] = verdict.judge_raw
        if verdict.latency_s is not None:
            record["judge_call"] = {
                "cost_usd": verdict.cost_usd,
                "latency_s": verdict.latency_s,
            }
    else:
        # The judge was not called: the option letter was matched arithmetically, the
        # abstention recognised by regexes. That too is a fact for the audit — the
        # verdict did not cost a call.
        record["judged_without_model"] = True
    return record


@dataclass(slots=True)
class _Pass:
    """The circumstances of one run — everything that is the same for all its questions.

    Created not for elegance: the question, the judge and the block went off into
    separate coroutines, and dragging a dozen arguments between them would mean
    changing eight signatures every time the run learns something new about itself.
    """

    space: SpaceConfig
    mode: ContextMode
    block: EvalBlock
    source: ContextSource
    settings: Settings
    subject: Provider | None
    response_type: str
    per_judge: dict[str, tuple[Provider, str, RunReport]]
    pool: Pool
    cache: RunCache
    progress: Progress
    # What the passes running at the same time share: ``launch.units`` is how many
    # questions to keep in work at once over all of them. Separate from the pool
    # lanes: the lanes count calls, and this one counts questions, and "is it time
    # to stop" can only be checked here. The coroutines of all the questions are
    # created at once, and a check before the queue would pass for all of them
    # before the first failure.
    launch: Launch
    # Per judge — the questions it already has a usable verdict for. The cut by judge
    # is mandatory: a run gets interrupted in the middle of a panel, and "the question
    # is done" would take away from the second judge work it never did.
    done: dict[str, set[str]] = field(default_factory=dict)
    # The answers are collected now, the verdicts issued later. Created for the sake
    # of console judging — a subscription instead of an API — and so that the
    # expensive half of the measurement can be separated from the cheap one.
    defer: bool = False

    @property
    def answers_by_model(self) -> bool:
        """A model under test answers, not the endpoint."""
        return self.mode in MODEL_ARMS


def answer_citations(usage: dict[str, Any]) -> list[dict[str, Any]]:
    """The web sources an answer cited; empty — it did not search."""
    if not usage.get("web_search"):
        return []
    return [c for c in usage.get("citations") or [] if isinstance(c, dict)]


async def _verdict_for(pair: QaPair, asked: Asked, seat: Provider, ctx: _Pass) -> Grade:
    """Assess one answer with one judge.

    The judging method is set by the generator: options are matched by letter,
    explanations by a list of facts, control questions by their behaviour,
    everything else against the gold answer.
    """
    grading = str((pair.meta or {}).get("grading") or "judge")
    if is_control(pair.generator, pair.meta):
        # A control question: the judge reads the behaviour, seeing what the
        # answer cited when it searched the web.
        return await ctx.pool.to_model(
            _timed_judge(ctx, seat, grade_control),
            control_case(pair.generator, pair.question, pair.answer, pair.meta),
            asked.answer,
            citations=answer_citations(asked.usage),
            settings=ctx.settings,
            judge=seat,
            defer=ctx.defer,
        )
    if grading == "key_facts":
        facts = [str(f) for f in (pair.meta or {}).get("key_facts", [])]
        return await ctx.pool.to_model(
            _timed_judge(ctx, seat, grade_key_facts),
            asked.answer,
            facts,
            settings=ctx.settings,
            judge=seat,
            defer=ctx.defer,
        )
    return await ctx.pool.to_model(
        _timed_judge(ctx, seat, grade),
        pair.question,
        pair.answer,
        asked.answer,
        is_mcq=pair.task_type == "choice",
        settings=ctx.settings,
        judge=seat,
        defer=ctx.defer,
    )


def _called_judge(verdict: Grade) -> bool:
    """A judge model was called for this verdict (not a letter match, not deferred)."""
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

    The conversation goes by rounds and cannot be parallelised — that is the whole
    block. So it goes off to a thread as a whole and occupies one lane for the entire
    exchange: the parallelism here is between questions, not within one.
    """
    searching, engine = arm_web_search(ctx.mode, ctx.subject, ctx.settings)
    return await ctx.pool.to_model(
        run_denial_loop,
        pair.question,
        pair.answer,
        asked.answer,
        subject=_subject_of(ctx.subject),
        settings=ctx.settings,
        is_mcq=pair.task_type == "choice",
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

    We ask by the same road the first answer went: the model alone in arm A, the
    model with the same context in arm C. Otherwise the consistency would be
    measured for someone other than the subject of the report.

    Past the cache deliberately: the repeats exist for the spread, and their
    temperature is not zero — the answers are not obliged to match.

    The repeats are independent and go side by side, each taking a model lane
    for its answer and its grade; the outcome keeps the plan order.
    """
    asker: Callable[[str, float], tuple[str, dict[str, Any]]]
    subject = _subject_of(ctx.subject)
    if ctx.mode is ContextMode.MODEL_WITH_CONTEXT:
        asker = partial(
            _ask_model_with_context,
            provider=subject,
            settings=ctx.settings,
            context=asked.context,
        )
    else:
        asker = partial(_ask_model, provider=subject, settings=ctx.settings)

    clock = ctx.pool.clock
    trials = await asyncio.gather(
        *(
            ctx.pool.to_model(
                monte_carlo_trial,
                pair.question,
                pair.answer,
                temperature,
                ask=clock.timed(subject.model, ANSWER, asker),
                settings=ctx.settings,
                is_mcq=pair.task_type == "choice",
                judge=seat,
                grade_with=_timed_judge(ctx, seat, grade),
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
        # This judge already has a verdict for this question, and it is a usable one.
        # Re-asking means paying for the same thing twice. Counting skips here is not
        # allowed: only asked questions reach this point, and the skipped ones are
        # precisely those that were not asked.
        return
    entry.asked += 1

    verdict = await _verdict_for(pair, asked, seat, ctx)

    # --- the blocks on top of the direct test ------------------------------
    extra: dict[str, Any] = {}
    if verdict.behavior:
        extra["behavior"] = verdict.behavior

    if verdict.verdict is Verdict.PENDING:
        # There is an answer, there is no verdict. The blocks and the grounding are
        # judge calls again, and making them over an unjudged answer is pointless:
        # pressure is applied only to a CORRECT answer, and nobody has yet said
        # whether it is correct.
        await ctx.pool.to_storage(
            _save_result,
            pair=pair,
            asked=asked,
            verdict=verdict,
            extra={},
            grounded=None,
            grounded_note="",
            run_id=run_id,
            seat=seat,
            responder=entry.model,
            ctx=ctx,
        )
        entry.deferred += 1
        return

    if (
        ctx.block is EvalBlock.DENIAL_LOOP
        and ctx.subject is not None
        and verdict.verdict is Verdict.CORRECT
        and not verdict.failed
    ):
        # There is a point in pushing only at a correct answer: there is nothing to
        # take away from a wrong one or from an abstention. In arm C the pressure
        # makes most sense: will the model give up an answer that is right now
        # confirmed by material in front of its eyes.
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
            # An answer given up is not counted as correct: in a conversation with an
            # insistent user it is already gone.
            verdict = Grade(
                Verdict.HALLUCINATE,
                f"gave in at round {denial.flip_round}: {denial.note}",
                judge_system=verdict.judge_system,
                judge_user=verdict.judge_user,
                judge_raw=verdict.judge_raw,
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

    # The mechanical resemblance to the gold answer — a second view of the same answer,
    # independent of the judge. Computed only for prose: masking has a one-word gold
    # answer, and word overlap there degenerates into "matched or not", which the
    # judge has already measured. A failure is not counted at all — comparing an error
    # message with a gold answer is meaningless.
    if ctx.settings.text_metrics and not verdict.failed and applies_to(pair.generator):
        # Into a thread: BLEU and ROUGE are cheap, whereas BERTScore is a model run,
        # and the loop must not be held on it.
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
            ctx.settings,
            seat,
        )

    await ctx.pool.to_storage(
        _save_result,
        pair=pair,
        asked=asked,
        verdict=verdict,
        extra=extra,
        grounded=grounded,
        grounded_note=grounded_note,
        run_id=run_id,
        seat=seat,
        responder=entry.model,
        ctx=ctx,
    )

    if verdict.fatal:
        # The judge, not the answerer: the answer arrived and this judge cannot
        # grade it. It stands down in every pass of the launch; the rest of the
        # panel carries on. With no judge left, nothing is worth asking.
        _stand_down(seat, entry, ctx)

    if verdict.failed:
        entry.failed += 1
        # Only a call that failed: `failed` also covers an item with no key
        # facts to check against, and that says nothing about the rig.
        if not entry.failure_sample and is_error(asked.answer):
            entry.failure_sample = asked.answer
    elif verdict.verdict is Verdict.CORRECT:
        entry.correct += 1
    elif verdict.verdict is Verdict.ABSTAIN:
        entry.abstain += 1
    elif verdict.verdict is Verdict.WEB_SOURCED:
        entry.web_sourced += 1
    else:
        entry.hallucinate += 1


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
    """Write one verdict. A run is interruptible, so it is written at once."""
    with session_scope() as session:
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
                # Empty for a local model and for the endpoint arms.
                served_by=str(asked.usage.get("served_by") or ""),
                judge_model=seat.model,
                judge_served_by=verdict.served_by,
            )
        )


def _stand_down(seat: Provider, entry: RunReport, ctx: _Pass) -> None:
    """A judge the provider refused outright grades nothing more in this launch.

    ``max_consecutive_failures`` of zero turns this off, as it does a refused
    answerer: the owner chose not to abandon anything early.
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
    if ctx.subject is not None and ctx.subject.model in ctx.launch.refused:
        # Refused in another pass of the launch.
        ctx.progress.refuse(ctx.subject.model)
        return ctx.progress.stopped
    if ctx.per_judge and all(model in ctx.launch.refused for model in ctx.per_judge):
        ctx.progress.stop("the provider refused every judge of this pass")
        return True
    return False


async def _ask_and_judge(pair: QaPair, ctx: _Pass) -> None:
    """One question: asked once, shown to the whole panel.

    The answerer is asked ONCE, and assessed by all the judges in turn. Otherwise
    each judge would see its own answer, the divergence between judges would blend
    with the spread of the answers themselves, and the model under test would be
    counted as many times as there are judges.
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

        # The judges are independent of one another and assess one and the same text
        # — which means there is no reason for them to wait for each other.
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
    subject: Provider | None = None,
    job_id: str | None = None,
) -> tuple[dict[str, tuple[Provider, str, RunReport]], list[RunReport]]:
    """Create one run per judge.

    The verdicts of different judges must not be piled together: the "latest" for a
    question would turn out to be the opinion of whoever finished last.

    The settings snapshot arrives ready rather than being reassembled here: what is
    already done is selected by the same snapshot, and two assemblies would diverge
    exactly when it is most expensive — on resuming.

    What was actually served is written beside that snapshot rather than into
    it: it is evidence about one run, not a condition for comparing two. The
    arms that question the endpoint have no model under test, and say so by
    leaving these empty.
    """
    per_judge: dict[str, tuple[Provider, str, RunReport]] = {}
    reports: list[RunReport] = []
    for seat in seated:
        run_id = uuid.uuid4().hex
        with session_scope() as session:
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
                    model_sent_as=subject.wire_model if subject is not None else "",
                    model_provider=subject.kind.value if subject is not None else "",
                    model_build=subject.build if subject is not None else "",
                    judge_model=seat.model,
                    job_id=job_id,
                )
            )
        entry = RunReport(
            run_id=run_id,
            space=space.key,
            context_mode=mode,
            block=block,
            model=responder,
            judge=seat.model,
            context_source=source,
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
    subject: Provider | None = None,
    block: EvalBlock = EvalBlock.DIRECT,
    judges: Sequence[Provider] | None = None,
    context_source: ContextSource | None = None,
    resume: bool = False,
    defer_judging: bool = False,
    watch: Callable[[Progress], None] | None = None,
    job_id: str | None = None,
    launch: Launch | None = None,
) -> list[RunReport]:
    """Run a Space dataset through one arm with the whole panel of judges.

    The questions go not one at a time but in a batch: a run is busy waiting on a
    socket, and waiting on them in turn is the very day within which the set does not
    get through even fifteen percent. The unit of parallelism is the question; within
    a question the judges are independent; what stays sequential is only what is
    sequential in meaning: the rounds of pressure in one dialogue.

    The pool and the cache come from outside rather than being created here. The
    cache because its whole point is to outlive the boundary of a run: the endpoint
    retrieval obtained by arm B is reused by arm C, and by all nine models under test
    within it. The pool because it is bound to the event loop, and there is one loop
    for the whole launch.

    Args:
        space: The node under test
        mode: The measurement arm
        pool: The lanes and worker threads of the launch
        cache: What has already been asked and is therefore not asked again
        limit: How many questions to ask; None — all the active ones
        settings: The process settings
        subject: The model under test; needed in arms A and C
        block: The test block
        judges: The panel; None — from the settings
        context_source: What to mix in in arm C; None — from the settings
        resume: Do not re-ask what the judge already has a usable verdict for
        defer_judging: Collect the answers without calling a judge. The verdicts are
            issued later — by the export-judging and import-judging commands
        watch: Called after every answered question. Through it a launch from outside
            both sees the progress and stops the run
        launch: What the passes running at the same time share (the question
            slots, refused names, the answerer's failure streak); None — this
            pass alone

    Returns:
        One report per judge, including those that recused themselves
    """
    if mode not in MODEL_ARMS:
        raise ValueError(f"arm {mode.value} is no longer measured")
    conf = settings or get_settings()
    launch = launch if launch is not None else Launch(conf)
    pairs = _active_pairs(space.key, limit, conf)
    if mode is ContextMode.CLOSED_BOOK:
        source = ContextSource.NONE
    else:
        source = context_source or conf.context_source

    panel = list(judges) if judges else judge_providers(conf)
    panel = [seat for seat in panel if seat.model not in launch.refused] or panel
    if block is not EvalBlock.DIRECT:
        # Pressure and repeats measure the answerer behaviour, not the spread of
        # assessments, and cost several times as much. The first judge computes them.
        panel = panel[:1]

    reports: list[RunReport] = []
    seated: list[Provider] = []

    if mode in MODEL_ARMS:
        # A model under test answers in arms A and C. In arm C it receives the
        # endpoint retrieval — and it is the same model as in A: otherwise the
        # difference between the arms would be measuring a change of model rather
        # than the appearance of context.
        subject = subject or subject_providers(conf)[0]
        responder = subject.model
        vendor = subject.vendor
        if skips_monte_carlo(block, subject, conf):
            # No run is created: nothing is asked, and an empty Run would look
            # like completed work.
            return [
                RunReport(
                    run_id="",
                    space=space.key,
                    context_mode=mode,
                    block=block,
                    model=responder,
                    judge=seat.model,
                    context_source=source,
                    notes=[monte_carlo_skip_note(responder)],
                )
                for seat in panel
            ]
        for candidate in panel:
            if is_recused(candidate, subject, conf):
                # A recusal, not a refusal: these answers stay without an assessment
                # from this judge, and the rest of the panel carries on working.
                recused = RunReport(
                    run_id="",
                    space=space.key,
                    context_mode=mode,
                    block=block,
                    model=responder,
                    judge=candidate.model,
                    context_source=source,
                )
                recused.notes.append(
                    f"judge {candidate.model} recused itself: {responder} "
                    f"is from the same provider"
                )
                reports.append(recused)
                continue
            check_judge_independence(candidate, subject, conf)
            seated.append(candidate)
    else:
        subject = None
        responder = "endpoint"
        vendor = ""
        seated = panel

    if not seated:
        return reports

    response_type = (
        await pool.to_endpoint(endpoint_mode, space) if mode in ENDPOINT_ARMS else ""
    )

    blocker = arm_blocker(mode, response_type, source)
    if blocker:
        # The arm is not measurable on this endpoint. No run is created at all: an
        # empty Run in the database would look like completed work, and zero metrics
        # like a result.
        return [
            RunReport(
                run_id="",
                space=space.key,
                context_mode=mode,
                block=block,
                model=responder,
                judge=seat.model,
                context_source=source,
                notes=[blocker],
            )
            for seat in seated
        ]

    if not pairs:
        held = evaluation_gate(space.key, conf)
        if held:
            # Active questions exist, none passed the web check: no run is
            # opened, the note says why nothing was asked.
            logger.warning(f"{space.key}: {held}")
            return reports + [
                RunReport(
                    run_id="",
                    space=space.key,
                    context_mode=mode,
                    block=block,
                    model=responder,
                    judge=seat.model,
                    context_source=source,
                    notes=[held],
                )
                for seat in seated
            ]

    params = conf.measurement_params(space)
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

    # A question is asked if at least one judge still needs it: the answerer answer
    # is one for the whole panel, and for the sake of a single judge out of three it
    # will have to be obtained anyway.
    pending = [
        pair
        for pair in pairs
        if any(pair.id not in done.get(seat.model, ()) for seat in seated)
    ]
    skipped = len(pairs) - len(pending)

    if pairs and not pending:
        # There is no work at all. No run is created: an empty Run in the database
        # would look like completed work, and the report will find the previous
        # verdicts without it — it counts by the latest verdict per question, not by
        # the last run.
        return reports + [
            RunReport(
                run_id="",
                space=space.key,
                context_mode=mode,
                block=block,
                model=responder,
                judge=seat.model,
                context_source=source,
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
        vendor=vendor,
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
        # Skips are counted here rather than along the way: only asked questions reach
        # the polling, and the skipped ones simply do not occur there. Each judge has
        # its own number — a run gets interrupted in the middle of a panel.
        known = {pair.id for pair in pairs}
        for seat, _run_id, entry in per_judge.values():
            entry.resumed = len(done.get(seat.model, set()) & known)
    if skipped:
        for entry in opened:
            entry.notes.append(
                f"resumed: {skipped} items already done, " f"asking {len(pending)}"
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
    subject: Provider | None = None,
    block: EvalBlock = EvalBlock.DIRECT,
    judges: Sequence[Provider] | None = None,
    context_source: ContextSource | None = None,
    cache: RunCache | None = None,
    resume: bool = False,
    defer_judging: bool = False,
    watch: Callable[[Progress], None] | None = None,
    job_id: str | None = None,
) -> list[RunReport]:
    """The same run, called from ordinary code.

    The event loop is created here and closed here. The cache can be passed from
    outside — and it is: a launch consists of dozens of runs, and the endpoint
    retrieval for a question is shared between them. Without it every run would start
    from a clean slate and go to RAG again for what it already knows.

    Args:
        cache: The cache shared across the launch; None — its own, for this run only
        resume: Do not re-ask what the judge already has a usable verdict for
        defer_judging: Collect the answers without calling a judge
        watch: The progress observer; it also stops the run
        job_id: The launch these runs belong to; None — started from the console,
            and then the runs belong to no job

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
