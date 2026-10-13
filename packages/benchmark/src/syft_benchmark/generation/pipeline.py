"""Stage 1: build items from new chunks and documents.

Incrementally. A run is interruptible and repeatable, and therefore:

  * what has been parsed is marked right away, not at the end — an interrupted
    run does not force you to start over;
  * every item is written in its own transaction — a failed LLM call does not
    take what has already been generated with it;
  * duplicates are cut off by a unique index over the question hash, not by a
    check in the code: the same question out of neighbouring chunks is quite
    possible.

The set comes in three kinds, and that is what sets WHAT generation sees at
all. The incremental one accumulates: new material adds items, the earlier ones
stay in the measurement. The rolling one moves with time — generation only
looks at the documents inside the freshness window. A rebuild takes the same
material and builds a fresh question pool from it, as a separate cohort, to
answer the question "are the questions themselves any good": the material is
one, the metrics diverged — so it is the questions.

Recomputing what takes part in the measurement lives in ``rotation.py``, the
notion of a cohort in ``cohort.py``.

There are two kinds of model call:

  * **a combined call** — the three masking categories. One call for all
    three: there is no point calling the model three times over one chunk.
  * **an ordinary call** — the remaining generators, each with its own prompt.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field, replace
from typing import Any

from loguru import logger
from sqlalchemy import or_, select

from syft_benchmark.config import (
    DatasetMode,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    get_settings,
)
from syft_benchmark.db import ProcessedUnit, QaPair, session_scope
from syft_benchmark.generation import cohort as cohorts
from syft_benchmark.generation import decisions, entities, recorded
from syft_benchmark.generation.article_dates import article_stamp, backfill
from syft_benchmark.generation.control import Retriever
from syft_benchmark.generation.extractive import (
    COMBINED_SYSTEM,
    Masked,
    parse_combined,
)
from syft_benchmark.generation.filter_stage import (
    FilterSummary,
    Screening,
    filter_pending,
)
from syft_benchmark.generation.generators import (
    EXTRACTIVE_CATEGORIES,
    EXTRACTIVE_KEYS,
    GENERATORS,
    MAX_DOCUMENT_CHARS,
    MAX_FRAGMENT_CHARS,
    Generator,
    document_header,
    reasons,
    user_prompt,
)
from syft_benchmark.generation.language import detect_language, written_text
from syft_benchmark.generation.pair import Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.recorded import new_call, writer_meta
from syft_benchmark.generation.rotation import RotationReport, fresh_ids, rotate
from syft_benchmark.generation.slots import Latch, model_slots
from syft_benchmark.generation.web_check import filter_model
from syft_benchmark.llm import (
    LLMError,
    Provider,
    chat,
    cost,
    generator_provider,
    parse_json_list,
    parse_json_object,
)
from syft_benchmark.llm.roles import web_search_for
from syft_benchmark.sources import ChromaClient, Chunk, Document, load_documents

# Headroom on the answer cap over the computed length of the items.
#
# Generous for the same reason the judge's cap is generous: a reasoning model
# spends output tokens on reasoning BEFORE it prints the JSON, and with a tight
# cap the answer breaks off in the middle of an object. Such an answer cannot
# be parsed — the items are lost whole, and they have already been paid for in
# full.
#
# Seen on a live DemoSyft run: Opus cut tiered_explanation off on the very
# first line with a cap of 1100. This adds nothing to the bill: max_tokens
# bounds, it does not order.
#
# A starting point, not the last line of defence: a call that comes back cut off
# is repeated with a doubled budget until it fits or reaches the shared answer
# ceiling (`chat` in llm/ollama.py). Raising this saves a wasted call.
REASONING_HEADROOM = 800

# How often the build's progress line is rewritten, at most.
_PROGRESS_SECONDS = 0.5

# Why a kind stopped writing.
BUDGET_REACHED = "budget reached"
OUT_OF_MATERIAL = "ran out of material"
FAILURE_STREAK = "failure streak"
CANCELLED = "cancelled"
COST_LIMIT = "top-up cost limit"

# Top-up rounds after the build, at most.
TOP_UP_ROUNDS = 2
# A kind's survival rate is read from its newest decided pairs on the target.
SURVIVAL_WINDOW = 200
# The lowest survival rate a top-up sizes its writes by.
MIN_SURVIVAL = 0.1

# Drop reasons the pipeline adds to the generators' own.
DUPLICATE = "duplicate"
OVER_BUDGET = "over budget"
OVER_UNIT_LIMIT = "over the per-passage limit"
WRONG_LANGUAGE = "wrong language"
AMBIGUOUS_ENTITY = entities.AMBIGUOUS_ENTITY


@dataclass(frozen=True, slots=True)
class _Rejected:
    """An item rejected as written: stored rejected, checked no further."""

    pair: Pair
    # The build's drop reason (``KindStats.dropped``).
    drop: str
    reason: StatusReason
    note: str


@dataclass(slots=True)
class KindStats:
    """One kind's build: budget, what it read and wrote, what it dropped, why
    it stopped. Updated only from the build's dispatching thread."""

    kind: str
    unit: str  # "passage" | "article"
    budget: int = 0
    written: int = 0
    # Unread units in the window at the start, and how many were read.
    units_available: int = 0
    units_read: int = 0
    # Units whose model call failed.
    failed_units: int = 0
    # Written by the top-up rounds, on top of the budget.
    topped_up: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    stopped: str = ""

    def drop(self, reason: str, count: int = 1) -> None:
        if count > 0:
            self.dropped[reason] = self.dropped.get(reason, 0) + count

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "unit": self.unit,
            "budget": self.budget,
            "written": self.written,
            "units_available": self.units_available,
            "units_read": self.units_read,
            "failed_units": self.failed_units,
            "topped_up": self.topped_up,
            "dropped": dict(self.dropped),
            "stopped": self.stopped,
        }


@dataclass(slots=True)
class GenerationReport:
    """What came out of one generation run.

    Every pair this run stores lands pending — whether it turns out active or
    rejected is filtering's verdict, not generation's, so there is nothing
    here to split ``pairs_made`` into. See ``filter_stage.FilterSummary``.
    """

    space: str
    units_seen: int = 0
    pairs_made: int = 0
    duplicates: int = 0
    failures: int = 0
    # The text of one failed generator call, whichever came first: the count
    # says generation produced nothing, this says why.
    failure_sample: str = ""
    by_generator: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    # The cohort this run's items landed in.
    cohort: str = ""
    # What the checks during the build decided; None — no checks ran.
    screened: FilterSummary | None = None
    # How recomputing the set ended. In incremental mode there is nothing to
    # recompute, and this stays None — which is not the same as "nothing
    # changed".
    rotation: RotationReport | None = None
    # Per kind, in the order the kinds were asked for.
    kinds: dict[str, KindStats] = field(default_factory=dict)

    def kind_rows(self) -> list[dict[str, Any]]:
        return [stats.as_dict() for stats in self.kinds.values()]


def question_hash(question: str) -> str:
    """A fingerprint of the question, guarding against cross-cycle duplicates."""
    normalized = " ".join(question.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def document_text(doc: Document) -> str:
    """The whole document — the pool the endpoint answers from."""
    return "\n\n".join(chunk.text for chunk in doc.chunks)


def pick_chunks(
    documents: list[Document], processed: set[str], limit: int | None = None
) -> list[tuple[Document, Chunk]]:
    """What to parse in this run, in the order to parse it.

    We walk the documents round-robin rather than in order: a run that stops
    on its question budget then has read every article a little, rather than
    the first articles whole and the last ones not at all.

    Args:
        documents: The documents in play
        processed: Chunks this queue has already parsed
        limit: How many to pick; None — every unparsed chunk
    """
    picked: list[tuple[Document, Chunk]] = []
    depth = 0
    while limit is None or len(picked) < limit:
        added = False
        for doc in documents:
            if depth >= len(doc.chunks):
                continue
            chunk = doc.chunks[depth]
            added = True
            if chunk.chunk_id in processed:
                continue
            picked.append((doc, chunk))
            if limit is not None and len(picked) >= limit:
                break
        if not added:
            break
        depth += 1
    return picked


def _processed_ids(space: str, generator: str, cohort: str) -> set[str]:
    """What THIS cohort has already parsed.

    The marks of earlier builds do not count: a rebuild is a fresh parse of the
    same material, and someone else's mark would stop it.
    """
    with session_scope() as session:
        rows = session.execute(
            select(ProcessedUnit.unit_id).where(
                ProcessedUnit.space == space,
                ProcessedUnit.generator == generator,
                ProcessedUnit.cohort == cohort,
            )
        ).scalars()
        return set(rows)


def _mark_processed(
    space: str, generator: str, unit_id: str, kind: str, made: int, cohort: str
) -> None:
    with session_scope() as session:
        session.merge(
            ProcessedUnit(
                space=space,
                generator=generator,
                unit_id=unit_id,
                cohort=cohort,
                unit_kind=kind,
                pairs_made=made,
            )
        )


def _row(
    space: SpaceConfig,
    doc: Document,
    chunk_id: str,
    fragment: str,
    pair: Pair,
    generator: Generator,
    model: str,
    collection: str,
    *,
    cohort: str,
    job: str,
    writer: dict[str, Any] | None,
    check: dict[str, Any] | None,
    rejected: _Rejected | None = None,
) -> QaPair | None:
    """Write one item; None — a duplicate, not stored.

    ``writer`` and ``check`` are the unit's writer and entity check calls:
    the first row stored from each keeps its texts, the rest its id. A
    ``rejected`` item is stored rejected, with its decision stamped.
    """
    meta: dict[str, Any] = {
        **pair.meta,
        "grading": pair.meta.get("grading", generator.grading),
        **article_stamp(doc),
    }
    if writer is not None:
        meta[recorded.WRITER] = writer_meta(writer, fragment[:8000])
    verdict = pair.meta.get(entities.META)
    if isinstance(verdict, dict):
        meta[entities.META] = recorded.check_meta(check or {}, verdict)
        if verdict.get("outcome") == decisions.FAILED and job:
            meta.update(
                decisions.stamped(
                    meta,
                    decisions.record(
                        job_id=job,
                        stage=decisions.WRITING,
                        outcome=decisions.FAILED,
                        note=f"entity check failed: {verdict.get('error') or ''}",
                    ),
                )
            )
    status = PairStatus.PENDING.value
    reason: str | None = None
    note = ""
    if rejected is not None:
        status = PairStatus.REJECTED.value
        reason = rejected.reason.value
        note = rejected.note
        if job:
            meta.update(
                decisions.stamped(
                    meta,
                    decisions.record(
                        job_id=job,
                        stage=decisions.WRITING,
                        outcome=decisions.REMOVED,
                        note=note,
                        reason=reason,
                    ),
                )
            )
    try:
        with session_scope() as session:
            row = QaPair(
                id=uuid.uuid4().hex,
                space=space.key,
                cohort=cohort,
                # Empty where nothing named the launch — the CLI, a console
                # call. NULL rather than "", so that "this launch's questions"
                # cannot accidentally match them.
                job_id=job or None,
                collection=collection,
                generator=generator.key,
                task_type=generator.task_type,
                doc_id=doc.doc_id,
                chunk_id=chunk_id,
                document_title=doc.title,
                file_name=doc.file_name,
                question=pair.question,
                answer=pair.answer,
                distractors=pair.distractors,
                context=fragment[:8000],
                expected_behavior=generator.expected.value,
                meta=meta,
                status=status,
                status_reason=reason,
                status_note=note,
                model=model,
                question_hash=question_hash(pair.question),
            )
            session.add(row)
            session.flush()
            # Kept usable after the session closes, for the checks.
            session.expunge(row)
    except Exception as exc:  # noqa: BLE001 - duplicates caught after the fact, see the module docstring
        if "qa_pairs_unique" not in str(exc):
            raise
        # Not stored: the calls' texts go on the next row.
        if writer is not None and "system" in meta.get(recorded.WRITER, {}):
            writer["_stored"] = False
        if check is not None and "system" in meta.get(entities.META, {}):
            check["_stored"] = False
        return None
    return row


def _store(
    space: SpaceConfig,
    doc: Document,
    chunk_id: str,
    fragment: str,
    pairs: Sequence[Pair],
    generator: Generator,
    model: str,
    collection: str,
    report: GenerationReport,
    *,
    conf: Settings,
    cohort: str = "",
    job: str = "",
    cap: int | None = None,
    writer: dict[str, Any] | None = None,
    check: dict[str, Any] | None = None,
    rejected: Sequence[_Rejected] = (),
) -> list[QaPair]:
    """Write the items down as pending; returns the rows written.

    ``writer`` is the model call that wrote them (``recorded.new_call``),
    ``check`` the unit's entity check call (``_entity_check``): the first row
    stored from each keeps its texts, the rest its id. ``rejected`` — the
    items rejected as written: stored rejected, outside the kind's budget
    and the returned rows.

    Nothing here decides whether a pending item is fit to measure with — that
    is its own pass, ``filter_stage.filter_pending()``, which reads the
    grounding and the control gate off what is stored here rather than off
    the fresh candidate.
    """
    if cap is not None:
        # The kind's question budget for this run (smaller on a trial run).
        # Counted per generator: a total divided between them would simply
        # drop some skills out of the set.
        room = cap - report.by_generator.get(generator.key, 0)
        stats = report.kinds.get(generator.key)
        if stats is not None:
            stats.drop(OVER_BUDGET, len(pairs) - max(room, 0))
        pairs = pairs[: max(room, 0)]

    def one(pair: Pair, refused: _Rejected | None = None) -> QaPair | None:
        return _row(
            space,
            doc,
            chunk_id,
            fragment,
            pair,
            generator,
            model,
            collection,
            cohort=cohort,
            job=job,
            writer=writer,
            check=check,
            rejected=refused,
        )

    written: list[QaPair] = []
    for pair in pairs:
        row = one(pair)
        if row is None:
            report.duplicates += 1
            if generator.key in report.kinds:
                report.kinds[generator.key].drop(DUPLICATE)
            continue
        written.append(row)
        report.pairs_made += 1
        report.by_generator[generator.key] = (
            report.by_generator.get(generator.key, 0) + 1
        )
        stats = report.kinds.get(generator.key)
        if stats is not None:
            stats.written += 1
    for item in rejected:
        one(item.pair, item)
    return written


def _masked_to_pairs(
    masked: list[Masked], document: str
) -> tuple[list[Pair], list[str]]:
    """Reject the masked sentences that fail and turn the rest into items."""
    good: list[Pair] = []
    rejected: list[str] = []
    for item in masked:
        reason = reject_reason(item.question, document, task_type="extractive")
        if reason:
            rejected.append(reason)
            continue
        good.append(
            Pair(
                question=item.question,
                answer=item.answer,
                distractors=[],
                meta=item.meta,
            )
        )
    return good, rejected


def _drop_wrong_language(
    pairs: list[Pair], document: str
) -> tuple[list[Pair], list[_Rejected]]:
    """Reject the items written in a language other than the document's.

    Every writer prompt asks for the document's language, and still a French or
    Italian question now and then comes out of an English article. Detection is
    unreliable on short texts: when either side gives no verdict (None), the
    item stays.

    Args:
        pairs: Items that passed their generator's own screening
        document: The whole document they were built from
    """
    expected = detect_language(document[:MAX_DOCUMENT_CHARS])
    if expected is None:
        return pairs, []
    good: list[Pair] = []
    rejected: list[_Rejected] = []
    for pair in pairs:
        found = detect_language(written_text(pair))
        if found is not None and found != expected:
            note = f"{WRONG_LANGUAGE}: {found}, the article {expected}"
            rejected.append(
                _Rejected(pair, WRONG_LANGUAGE, StatusReason.WRONG_LANGUAGE, note)
            )
            continue
        good.append(pair)
    return good, rejected


@dataclass(slots=True)
class _EntityCheck:
    """One entity check call: its record, the verdicts by question, or why
    there are none."""

    # {call, model, system, user, reply, cost_usd, latency_s}; empty — the
    # call failed.
    call: dict[str, Any] = field(default_factory=dict)
    verdicts: dict[int, entities.Verdict] = field(default_factory=dict)
    error: str | None = None


def _entity_check(
    texts: list[str],
    conf: Settings,
    provider: Provider,
    hold: Callable[[], AbstractContextManager[None]] = nullcontext,
) -> _EntityCheck:
    """Ask the writer model, with no article, whether each question's
    subjects are identifiable (``entities.SYSTEM``)."""
    user = entities.user_prompt(texts)
    try:
        with hold():
            raw, usage = chat(
                entities.SYSTEM,
                user,
                provider=provider,
                max_tokens=entities.TOKENS_PER_QUESTION * len(texts)
                + REASONING_HEADROOM,
                settings=conf,
                role=cost.WRITER,
            )
    except LLMError as exc:
        return _EntityCheck(error=str(exc))
    call = {
        "call": uuid.uuid4().hex,
        "model": provider.model,
        "system": entities.SYSTEM,
        "user": user,
        "reply": raw,
        **cost.spent(usage),
    }
    try:
        return _EntityCheck(call=call, verdicts=entities.parse(raw, len(texts)))
    except LLMError as exc:
        return _EntityCheck(call=call, error=str(exc))


def _screen_entities(
    made: Mapping[str, list[Pair]],
    conf: Settings,
    provider: Provider,
    hold: Callable[[], AbstractContextManager[None]] = nullcontext,
) -> tuple[dict[str, list[Pair]], dict[str, list[_Rejected]], dict[str, Any]]:
    """The entity check over one unit's questions, in one call.

    Returns:
        Per kind the questions kept, each with its verdict in
        ``meta.entity_check``, and the ones rejected; and the call. A failed
        call or a question the reply leaves out keeps the question, its
        verdict ``failed``
    """
    kept: dict[str, list[Pair]] = {key: [] for key in made}
    rejected: dict[str, list[_Rejected]] = {key: [] for key in made}
    order = [(key, pair) for key, pairs in made.items() for pair in pairs]
    if not conf.entity_check or not order:
        return dict(made), rejected, {}
    check = _entity_check(
        [entities.shown(key, pair) for key, pair in order], conf, provider, hold
    )
    for i, (key, pair) in enumerate(order):
        verdict = check.verdicts.get(i)
        record: dict[str, Any] = (
            {
                "outcome": decisions.FAILED,
                "error": check.error or "the reply has no verdict on it",
            }
            if verdict is None
            else {
                "outcome": decisions.KEPT if verdict.ok else decisions.REMOVED,
                "entities": verdict.entities,
            }
        )
        stamped = replace(pair, meta={**pair.meta, entities.META: record})
        if verdict is not None and not verdict.ok:
            rejected[key].append(
                _Rejected(
                    stamped,
                    AMBIGUOUS_ENTITY,
                    StatusReason.AMBIGUOUS_ENTITY,
                    verdict.note(),
                )
            )
        else:
            kept[key].append(stamped)
    if check.error:
        logger.warning(f"entity check failed, the questions are kept: {check.error}")
    return kept, rejected, check.call


@dataclass(slots=True)
class _Extracted:
    """Masked items of one chunk, per kind, or the error."""

    by_key: dict[str, list[Masked]] = field(default_factory=dict)
    error: str | None = None


def _extractive_for_chunk(
    doc: Document,
    chunk: Chunk,
    keys: tuple[str, ...],
    conf: Settings,
    generator: Provider,
    hold: Callable[[], AbstractContextManager[None]] = nullcontext,
    record: dict[str, Any] | None = None,
) -> _Extracted:
    """Build masked items from a chunk with one model call.

    ``record``, when given, gets the model call (``recorded.new_call``).
    """
    categories = tuple(
        category for category, key in EXTRACTIVE_CATEGORIES.items() if key in keys
    )
    out = _Extracted()
    if not categories:
        return out

    searching, engine = web_search_for(conf, "generator", generator.model)
    system = COMBINED_SYSTEM.format(n=conf.pairs_per_chunk)
    user = user_prompt(doc, chunk, conf.pairs_per_chunk)
    try:
        with hold():
            raw, usage = chat(
                system,
                user,
                provider=generator,
                max_tokens=90 * conf.pairs_per_chunk * len(categories) + 200,
                settings=conf,
                web_search=searching,
                web_search_engine=engine or "auto",
                role=cost.WRITER,
            )
        if record is not None:
            record.update(
                new_call(
                    model=generator.model,
                    system=system,
                    user=user,
                    reply=raw,
                    passage=chunk.text[:MAX_FRAGMENT_CHARS],
                    usage=usage,
                )
            )
        data = parse_json_object(raw)
    except LLMError as exc:
        out.error = str(exc)
        return out

    for category, items in parse_combined(data, categories).items():
        out.by_key[EXTRACTIVE_CATEGORIES[category]] = items
    return out


def _run_llm_generator(
    generator: Generator,
    doc: Document,
    chunk: Chunk | None,
    conf: Settings,
    provider: Provider,
    record: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """A single model call for one particular generator.

    ``record``, when given, gets the call (``recorded.new_call``).
    """
    tasks = 1 if generator.key == "tiered_explanation" else conf.pairs_per_chunk
    if generator.scope == "document":
        text = document_text(doc)[:MAX_DOCUMENT_CHARS]
        header = "\n".join(document_header(doc))
        prompt = f'{header}\n\nText:\n"""\n{text}\n"""\n\nGenerate {tasks}.'
    else:
        assert chunk is not None
        text = chunk.text[:MAX_FRAGMENT_CHARS]
        prompt = user_prompt(doc, chunk, tasks)

    # The starting budget. tiered_explanation is the longest item there is by
    # construction — three explanations of differing levels plus a list of facts
    # in one object — and a reasoning model spends the budget on reasoning
    # before it prints any of that. Starting it from a per-item constant costs
    # two cut-off calls, billed in full and thrown away, before the doubling in
    # the client arrives at a budget that holds. The shared answer ceiling is
    # what every other call in the service already asks for, and max_tokens
    # bounds rather than orders: a shorter item is no dearer for the room.
    budget = generator.tokens_per_pair * tasks + REASONING_HEADROOM
    if generator.key == "tiered_explanation":
        budget = max(budget, conf.answer_max_tokens)

    searching, engine = web_search_for(conf, "generator", provider.model)
    system = generator.system.format(n=tasks)
    try:
        raw, usage = chat(
            system,
            prompt,
            provider=provider,
            max_tokens=budget,
            settings=conf,
            web_search=searching,
            web_search_engine=engine or "auto",
            role=cost.WRITER,
        )
    except LLMError as exc:
        return [], str(exc)
    if record is not None:
        record.update(
            new_call(
                model=provider.model,
                system=system,
                user=prompt,
                reply=raw,
                passage=text,
                usage=usage,
            )
        )

    try:
        # tiered answers with an object, the rest with an array; the object is
        # parsed by a separate call, because looking for an array in such an
        # answer is risky.
        if generator.key == "tiered_explanation":
            return [parse_json_object(raw)], None
        return parse_json_list(raw), None
    except LLMError as exc:
        return [], str(exc)


@dataclass(eq=False, slots=True)
class _Queue:
    """One kind's walk (the three masking kinds share one) over its units."""

    label: str
    keys: tuple[str, ...]
    # The generator key its units are marked processed under.
    marker: str
    scope: str
    units: list[tuple[Document, Chunk | None]]
    # Questions one unit is asked for, per kind.
    per_unit: int
    # None — the extractive group.
    spec: Generator | None = None
    pos: int = 0
    streak: int = 0
    done: bool = False
    gave_up: bool = False


@dataclass(slots=True)
class _Outcome:
    """What one unit gave back: questions per kind, or the error."""

    pairs: dict[str, tuple[list[Pair], list[str]]] = field(default_factory=dict)
    # Per kind, the items rejected as written.
    rejected: dict[str, list[_Rejected]] = field(default_factory=dict)
    model: str = ""
    parsed: int = 0
    error: str | None = None
    # The writer call (``recorded.new_call``).
    call: dict[str, Any] = field(default_factory=dict)
    # The entity check call (``_entity_check``).
    check: dict[str, Any] = field(default_factory=dict)


def _queues(
    space: str,
    specs: Sequence[Generator],
    extractive: tuple[str, ...],
    documents: list[Document],
    cohort: str,
    conf: Settings,
    report: GenerationReport,
) -> list[_Queue]:
    """Each kind's unparsed units, in the order to parse them.

    The extractive ones are built in a single pass: three categories out of
    one parse, which is why they are marked under one key. The rest have a
    queue OF THEIR OWN each: a shared batch would mean that a generator
    plugged in second skips everything the first has already parsed.
    """
    queues: list[_Queue] = []
    if extractive:
        processed = _processed_ids(space, extractive[0], cohort)
        batch = pick_chunks(documents, processed)
        if not batch:
            report.notes.append("masking: there are no new chunks")
        else:
            queues.append(
                _Queue(
                    "masking",
                    extractive,
                    extractive[0],
                    "chunk",
                    [(doc, chunk) for doc, chunk in batch],
                    conf.pairs_per_chunk,
                )
            )
    for spec in specs:
        if spec.key in EXTRACTIVE_KEYS:
            continue
        processed = _processed_ids(space, spec.key, cohort)
        units: list[tuple[Document, Chunk | None]]
        if spec.scope == "document":
            units = [(doc, None) for doc in documents if doc.doc_id not in processed]
            if not units:
                report.notes.append(f"{spec.key}: there are no new documents")
                continue
        else:
            units = [(doc, chunk) for doc, chunk in pick_chunks(documents, processed)]
            if not units:
                report.notes.append(f"{spec.key}: there are no new chunks")
                continue
        per_unit = 1 if spec.key == "tiered_explanation" else conf.pairs_per_chunk
        queues.append(
            _Queue(spec.key, (spec.key,), spec.key, spec.scope, units, per_unit, spec)
        )
    return queues


def _settle_kinds(
    report: GenerationReport,
    queues: Sequence[_Queue],
    caps: Mapping[str, int],
    *,
    cancelled: bool,
    limited: bool = False,
) -> None:
    """Why each kind stopped writing; ``limited`` — the top-up hit its cost limit."""
    queue_of = {key: queue for queue in queues for key in queue.keys}
    for key, stats in report.kinds.items():
        queue = queue_of.get(key)
        left = queue is not None and queue.pos < len(queue.units)
        if stats.written >= caps.get(key, stats.budget):
            stats.stopped = BUDGET_REACHED
        elif queue is not None and queue.gave_up:
            stats.stopped = FAILURE_STREAK
        elif cancelled and left:
            stats.stopped = CANCELLED
        elif limited and left:
            stats.stopped = COST_LIMIT
        else:
            stats.stopped = OUT_OF_MATERIAL


def kind_targets(keys: Sequence[str], cap: int, conf: Settings) -> dict[str, int]:
    """How many of each kind should pass the checks: its write budget, and
    with a set cap (``dataset_max_pairs``) no more than an even share of it."""
    share = cap
    if conf.dataset_max_pairs and keys:
        share = math.ceil(conf.dataset_max_pairs / len(keys))
    return {key: min(cap, share) for key in keys}


def survival_rates(space: str, keys: Sequence[str], conf: Settings) -> dict[str, float]:
    """Each kind's share of decided pairs on this target that passed the checks.

    Read from its newest ``SURVIVAL_WINDOW`` pairs that are active, retired
    or rejected, an owner's rejection left out, as (kept + 1) / (decided + 2):
    a kind with no history reads as one half.
    """
    decided = (
        PairStatus.ACTIVE.value,
        PairStatus.RETIRED.value,
        PairStatus.REJECTED.value,
    )
    rates: dict[str, float] = {}
    with session_scope(conf) as session:
        for key in keys:
            statuses = list(
                session.execute(
                    select(QaPair.status)
                    .where(
                        QaPair.space == space,
                        QaPair.generator == key,
                        QaPair.status.in_(decided),
                        or_(
                            QaPair.status_reason.is_(None),
                            QaPair.status_reason != StatusReason.OWNER.value,
                        ),
                    )
                    .order_by(QaPair.created_at.desc(), QaPair.id.desc())
                    .limit(SURVIVAL_WINDOW)
                ).scalars()
            )
            kept = sum(1 for status in statuses if status != PairStatus.REJECTED.value)
            rates[key] = (kept + 1) / (len(statuses) + 2)
    return rates


def top_up_plan(
    targets: Mapping[str, int],
    survived: Mapping[str, int],
    rates: Mapping[str, float],
    cap: int,
) -> dict[str, int]:
    """How many more of each kind to write: its shortfall over its survival
    rate (at least ``MIN_SURVIVAL``), at most ``cap``. Kinds at their target
    are left out."""
    plan: dict[str, int] = {}
    for key, target in targets.items():
        short = target - survived.get(key, 0)
        if short > 0 and cap > 0:
            rate = max(rates.get(key, 0.5), MIN_SURVIVAL)
            plan[key] = min(cap, math.ceil(short / rate - 1e-9))
    return plan


def _survivors(written: Mapping[str, Sequence[str]], conf: Settings) -> dict[str, int]:
    """Per kind, how many of the pairs written are active or still pending."""
    ids = [pair_id for group in written.values() for pair_id in group]
    if not ids:
        return {}
    with session_scope(conf) as session:
        rows = session.execute(
            select(QaPair.generator, QaPair.status).where(QaPair.id.in_(ids))
        ).all()
    alive = (PairStatus.ACTIVE.value, PairStatus.PENDING.value)
    counts: dict[str, int] = {}
    for generator, status in rows:
        if status in alive:
            counts[generator] = counts.get(generator, 0) + 1
    return counts


def _checked(screening: Screening, row: QaPair) -> None:
    """Screen one written question; a failure leaves it pending."""
    try:
        screening.screen(row)
    except Exception as exc:  # noqa: BLE001 - the next filter pass checks it again
        logger.warning(f"{row.id}: the check failed, left pending: {exc}")


def generate_for_space(
    space: SpaceConfig,
    *,
    generators: Sequence[str] = ("qa",),
    collection: str | None = None,
    limit: int | None = None,
    settings: Settings | None = None,
    new_cohort: bool = False,
    cohort_label: str = "",
    should_stop: Callable[[], bool] | None = None,
    job: str = "",
    per_generator: int | None = None,
    on_unit: Callable[[str, int, int, int], None] | None = None,
    screen: bool = False,
    retrieve: Retriever | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> GenerationReport:
    """Build items from the not-yet-parsed material of one Space.

    Every item lands ``pending``: whether it is fit to measure with — grounded,
    and for a control item not in fact answered by retrieval — is decided by
    its own pass, ``filter_stage.filter_pending()``, not by this one.

    Args:
        space: The node under test
        generators: Generator keys from GENERATORS
        collection: ChromaDB collection name; empty — the node's own name, and
            failing that, the node's key
        limit: The question budget per kind, in units: each kind writes at
            most ``limit * pairs_per_chunk`` questions; defaults to
            ``chunks_per_run``. Every passage in the window is eligible, and a
            kind's walk stops once its budget is spent
        settings: Process settings
        new_cohort: Build the question pool afresh, as a separate cohort, from
            the same material. In rebuild mode this is implied
        cohort_label: The new cohort's name; empty — the date and time of the build
        job: The launch these items belong to; empty — none that can be named
        per_generator: Stop at this many items from each generator — a trial
            run. The walk over the material stops as soon as every generator
            has its fill, so a trial does not mark chunks processed that it
            never really used and leave a later full run nothing to build from
        on_unit: Told before every unit which generator is being built, which
            unit of its batch this is, how big that batch is, and how many
            questions exist so far. A build runs for minutes on a paid model
            and reported nothing while it did; this is what a console draws
            its position from
        should_stop: Asked before every unit whether the owner has called the
            build off. A unit is one generator call on a paid model, so this is
            where stopping is worth something; mid-unit there is nothing left
            to save. Without it the build runs to the end, which is what the
            daily cycle wants
        screen: Check each question as soon as it is written: grounding or
            the control gate, then the web check (``filter_stage.Screening``),
            while generation goes on. The set is then not recomputed here: the
            caller's filter pass checks what is left and recomputes it once
            (``filter_and_rotate(rotate_anyway=True)``). After the build, a
            kind short of its target (``kind_targets``) gets more written and
            checked the same way: up to ``TOP_UP_ROUNDS`` rounds, sized by its
            survival rate on this target, until ``top_up_max_usd`` is spent
        retrieve: What the control gate checks with when screening
        on_progress: Told "written N · checked M · removed R" as the build goes

    Units run ``concurrency`` at a time across kinds and passages; generator
    calls and checks share that limit (``slots.ModelSlots``). A kind's budget
    is exact: units are dispatched only while it has room beyond the units in
    flight, and what one unit writes past it is trimmed.

    Returns:
        A report on the run

    Raises:
        KeyError: unknown generator
        ChromaError: there is no road to the Space's index
    """
    conf = settings or get_settings()
    specs = [GENERATORS[key] for key in generators]

    # The cohort is decided before the first generator call: both what counts
    # as already parsed and where the items land depend on it. A rebuild mints
    # a new label — the earlier pool stays in the database and will leave the
    # measurement at the next recompute; the other modes top up the current one.
    rebuilding = new_cohort or conf.dataset_mode is DatasetMode.REBUILD
    cohort = (
        (cohort_label or cohorts.new_label())
        if rebuilding
        else cohorts.current(space.key, conf)
    )
    report = GenerationReport(space=space.key, cohort=cohort)

    stopped = False
    latch = Latch(should_stop)

    # The question budget per kind: "Write at most" on the page is
    # chunks_per_run * pairs_per_chunk * kinds. Counted in questions written,
    # not passages read, so a passage that yields less does not shrink the set.
    quota = (limit or conf.chunks_per_run) * conf.pairs_per_chunk
    cap = quota if per_generator is None else min(quota, per_generator)
    # Per kind; the top-up raises a short kind's.
    caps = {spec.key: cap for spec in specs}
    for spec in specs:
        report.kinds[spec.key] = KindStats(
            kind=spec.key,
            unit="article" if spec.scope == "document" else "passage",
            budget=cap,
        )
    # Units in a row that wrote nothing: failed calls, or answers all cleaned
    # away. Every passage in the window is eligible, so this is what stops a
    # kind that keeps paying for nothing.
    give_up = conf.max_consecutive_failures

    def gave_up(key: str, streak: int) -> bool:
        if give_up and streak >= give_up:
            report.notes.append(
                f"{key}: {streak} units in a row wrote nothing — stopped before "
                f"its budget was spent"
            )
            return True
        return False

    def called_off() -> bool:
        """Whether to stop before the next unit. Said once, in the report."""
        nonlocal stopped
        if not stopped and latch():
            stopped = True
            report.notes.append("the build was stopped at the owner's request")
            logger.info(f"{space.key}: generation stopped at the owner's request")
        return stopped

    if rebuilding:
        report.notes.append(
            f"set rebuild: cohort {cohort} — the same material, "
            f"the questions are built afresh"
            + (
                f", period {conf.document_window_days} d."
                if conf.document_window_days
                else ", over the whole corpus"
            )
        )
    # The role is resolved once per run: its address and key may differ from
    # the shared ones, and the perimeter check has to pass before the first
    # call.
    provider = generator_provider(conf)

    control = [spec for spec in specs if spec.is_control]
    if control:
        report.notes.append(
            "control generators ("
            + ", ".join(spec.key for spec in control)
            + ") were built as pending — the check against live retrieval "
            "is for filtering to decide, not this pass"
        )

    client = ChromaClient(space, conf)
    name = collection or space.collection or space.key
    collection_id = client.collection_id(name)
    if collection_id is None:
        report.notes.append(f'there is no collection "{name}"')
        _settle_kinds(report, [], caps, cancelled=False)
        return report

    documents = load_documents(client, collection_id)
    try:
        backfill(space.key, documents)
    except Exception:  # noqa: BLE001 - the dates only feed the report
        logger.exception(f"{space.key}: article dates were not stamped")

    # The freshness window cuts off material BEFORE generation, not the set
    # after it: there is no point paying the generator for a document that will
    # not enter the measurement anyway. In incremental mode the window applies
    # too — there it bounds what to build from, but it does not pull what has
    # already been built out of the set.
    dated = {doc.doc_id: doc.dated_at for doc in documents}
    if conf.document_window_days:
        fresh, undated = fresh_ids(dated, conf)
        documents = [doc for doc in documents if doc.doc_id in fresh]
        report.notes.append(
            f"freshness window {conf.document_window_days} d.: "
            f"documents in play {len(documents)}"
        )
        if undated:
            report.notes.append(
                f"{undated} documents have no publication date or add time — "
                f"the window does not apply to them"
            )
        if not documents:
            report.notes.append("there is not a single document in the window")

    extractive = tuple(s.key for s in specs if s.key in EXTRACTIVE_KEYS)
    queues = _queues(space.key, specs, extractive, documents, cohort, conf, report)
    for queue in queues:
        for key in queue.keys:
            if key in report.kinds:
                report.kinds[key].units_available = len(queue.units)

    width = max(1, conf.concurrency)
    slots = model_slots(conf)
    # Checks run as soon as a question is written, sharing the model limit.
    screening = (
        Screening(
            space.key,
            conf,
            retrieve=retrieve,
            should_stop=latch,
            slots=slots,
            on_verdict=lambda: tell(),
            job_id=job,
        )
        if screen
        else None
    )
    tell_lock = threading.Lock()
    told = [0.0]

    def tell(final: bool = False) -> None:
        if on_progress is None:
            return
        with tell_lock:
            now = time.monotonic()
            if not final and now - told[0] < _PROGRESS_SECONDS:
                return
            told[0] = now
            checked = screening.report.checked if screening else 0
            removed = screening.report.rejected if screening else 0
            on_progress(
                f"written {report.pairs_made} · checked {checked} · removed {removed}"
            )

    # Questions per kind already asked for by units in flight: a unit is
    # dispatched only while its kind has room beyond them, so the walk reads
    # no passage it does not need. A unit that writes less frees the room.
    reserved: dict[str, int] = {}
    # The ids of the questions written, per kind.
    built: dict[str, list[str]] = {}

    def wanted(queue: _Queue) -> tuple[str, ...]:
        return tuple(
            key
            for key in queue.keys
            if report.by_generator.get(key, 0) + reserved.get(key, 0) < caps[key]
        )

    def work(
        queue: _Queue, doc: Document, chunk: Chunk | None, keys: tuple[str, ...]
    ) -> _Outcome:
        """One unit on a worker thread: the model calls and the cleaning."""
        whole = document_text(doc)
        call: dict[str, Any] = {}
        # Per kind: what passed the generator's own screening and the
        # language check, why the rest did not, and what is stored rejected.
        made: dict[str, list[Pair]] = {}
        bad: dict[str, list[str]] = {}
        refused: dict[str, list[_Rejected]] = {}
        if queue.spec is None:
            assert chunk is not None
            extracted = _extractive_for_chunk(
                doc, chunk, keys, conf, provider, hold=slots.hold, record=call
            )
            if extracted.error:
                return _Outcome(error=extracted.error)
            parsed = sum(len(v) for v in extracted.by_key.values())
            for key, masked in extracted.by_key.items():
                good, bad[key] = _masked_to_pairs(masked, whole)
                made[key], refused[key] = _drop_wrong_language(good, whole)
        else:
            with slots.hold():
                items, error = _run_llm_generator(
                    queue.spec, doc, chunk, conf, provider, record=call
                )
            if error:
                return _Outcome(error=error)
            key = queue.spec.key
            good, bad[key] = queue.spec.clean(items, conf.pairs_per_chunk, whole)
            made[key], refused[key] = _drop_wrong_language(good, whole)
            parsed = len(made[key])
        made, unclear, check = _screen_entities(made, conf, provider, slots.hold)
        pairs: dict[str, tuple[list[Pair], list[str]]] = {}
        for key, good in made.items():
            refused[key] += unclear[key]
            dropped = bad[key] + [r.drop for r in refused[key]]
            if queue.spec is None:
                # The model may return more than asked, and one dense passage
                # would spend a kind's budget.
                surplus = max(0, len(good) - conf.pairs_per_chunk)
                dropped += [OVER_UNIT_LIMIT] * surplus
                good = good[: conf.pairs_per_chunk]
            pairs[key] = (good, dropped)
        return _Outcome(
            pairs=pairs,
            rejected=refused,
            model=conf.generator_model,
            parsed=parsed,
            call=call,
            check=check,
        )

    def settle(
        queue: _Queue,
        doc: Document,
        chunk: Chunk | None,
        keys: tuple[str, ...],
        outcome: _Outcome,
    ) -> None:
        """Store one unit's questions and hand them to the checks."""
        for key in keys:
            if key in report.kinds:
                stats = report.kinds[key]
                stats.units_read += 1
                stats.failed_units += bool(outcome.error)
        if outcome.error:
            report.failures += 1
            queue.streak += 1
            if queue.spec is not None:
                report.failure_sample = (
                    report.failure_sample or f"{queue.label}: {outcome.error}"
                )
            where = chunk.chunk_id if chunk is not None else queue.label
            logger.warning(f"{space.key}/{where}: {outcome.error}")
            return
        before = report.pairs_made
        fragment = chunk.text if chunk is not None else document_text(doc)
        unit_id = chunk.chunk_id if chunk is not None else doc.doc_id
        shown = chunk.chunk_id[:10] if chunk is not None else doc.title[:24]
        for key, (good, bad) in outcome.pairs.items():
            if bad:
                report.notes.append(f"{key} {shown}: {reasons(bad)}")
                if key in report.kinds:
                    for why in bad:
                        report.kinds[key].drop(why)
            rows = _store(
                space,
                doc,
                unit_id if chunk is not None else f"doc:{doc.doc_id}",
                fragment,
                good,
                GENERATORS[key],
                outcome.model,
                name,
                report,
                conf=conf,
                cohort=cohort,
                job=job,
                cap=caps[key],
                writer=outcome.call or None,
                check=outcome.check or None,
                rejected=outcome.rejected.get(key, ()),
            )
            built.setdefault(key, []).extend(row.id for row in rows)
            if screening is not None and check_pool is not None:
                checks.extend(check_pool.submit(_checked, screening, r) for r in rows)
        _mark_processed(
            space.key, queue.marker, unit_id, queue.scope, outcome.parsed, cohort
        )
        queue.streak = 0 if report.pairs_made > before else queue.streak + 1
        tell()

    checks: list[Future[None]] = []
    check_pool: ThreadPoolExecutor | None = None

    def build(halt: Callable[[], bool] = lambda: False) -> None:
        """Walk the queues until every kind has its cap, the material runs
        out, the owner stops it or ``halt`` says so."""
        nonlocal check_pool
        running: dict[
            Future[_Outcome], tuple[_Queue, Document, Chunk | None, tuple[str, ...]]
        ] = {}
        # The workers charge the meter current here: the top-up's limit reads it.
        check_pool = (
            ThreadPoolExecutor(
                max_workers=width, thread_name_prefix="check", **cost.pool_kwargs()
            )
            if screening is not None
            else None
        )
        try:
            with ThreadPoolExecutor(
                max_workers=width, thread_name_prefix="gen", **cost.pool_kwargs()
            ) as pool:
                while True:
                    # Round-robin over the kinds, one unit each per sweep.
                    dispatched = True
                    while (
                        dispatched
                        and len(running) < width
                        and not called_off()
                        and not halt()
                    ):
                        dispatched = False
                        for queue in queues:
                            if len(running) >= width:
                                break
                            if queue.done or queue.pos >= len(queue.units):
                                continue
                            if gave_up(queue.label, queue.streak):
                                queue.done = True
                                queue.gave_up = True
                                continue
                            keys = wanted(queue)
                            if not keys:
                                continue
                            doc, chunk = queue.units[queue.pos]
                            queue.pos += 1
                            report.units_seen += 1
                            if on_unit is not None:
                                on_unit(
                                    queue.label,
                                    queue.pos,
                                    len(queue.units),
                                    report.pairs_made,
                                )
                            for key in keys:
                                reserved[key] = reserved.get(key, 0) + queue.per_unit
                            future = pool.submit(work, queue, doc, chunk, keys)
                            running[future] = (queue, doc, chunk, keys)
                            dispatched = True
                    if not running:
                        break
                    finished, _ = wait(running, return_when=FIRST_COMPLETED)
                    for future in finished:
                        queue, doc, chunk, keys = running.pop(future)
                        for key in keys:
                            reserved[key] -= queue.per_unit
                        settle(queue, doc, chunk, keys, future.result())
        finally:
            if check_pool is not None:
                # Written questions are checked before the build reports; on a
                # stop the checks not started leave their questions pending.
                check_pool.shutdown(wait=True)

    build()

    # The top-up: more of each kind the checks left short of its target.
    limited = False
    if screening is not None and conf.top_up_max_usd > 0 and not stopped:
        current = cost.current()
        metered: AbstractContextManager[cost.CostMeter] = (
            nullcontext(current) if current is not None else cost.cost_meter()
        )
        with metered as meter:
            start = meter.total_usd

            def over() -> bool:
                return meter.total_usd - start >= conf.top_up_max_usd

            targets = kind_targets(list(report.kinds), cap, conf)
            for turn in range(1, TOP_UP_ROUNDS + 1):
                if called_off() or over():
                    break
                open_keys = {
                    key
                    for queue in queues
                    if not queue.done and queue.pos < len(queue.units)
                    for key in queue.keys
                }
                rates = survival_rates(space.key, list(targets), conf)
                plan = {
                    key: extra
                    for key, extra in top_up_plan(
                        targets, _survivors(built, conf), rates, cap
                    ).items()
                    if key in open_keys
                }
                if not plan:
                    break
                report.notes.append(
                    f"top-up round {turn}: "
                    + ", ".join(
                        f"{key} +{extra} (target {targets[key]}, "
                        f"survival {rates[key]:.0%})"
                        for key, extra in plan.items()
                    )
                )
                before = dict(report.by_generator)
                for key, extra in plan.items():
                    caps[key] = report.by_generator.get(key, 0) + extra
                build(halt=over)
                for key in plan:
                    report.kinds[key].topped_up += report.by_generator.get(
                        key, 0
                    ) - before.get(key, 0)
            limited = over()
        if limited:
            report.notes.append(
                f"top-up stopped at its cost limit, ${conf.top_up_max_usd:g}"
            )
    tell(final=True)
    _settle_kinds(report, queues, caps, cancelled=stopped, limited=limited)
    if screening is not None:
        report.screened = screening.summary()

    # Recomputing the set comes last: generation has added items from the new
    # material, and only now is it visible what of the accumulated pile takes
    # part in today's measurement. In incremental mode the call changes nothing
    # and merely counts the active ones — but it is made anyway, so that the
    # generation report states the size of the set in both modes, not in one.
    # Not after a build that was called off. Recomputing would make a half-built
    # cohort the set today's measurement runs on, and a set missing whatever the
    # stop landed in front of is not a smaller set — it is a set with a hole in
    # a shape nobody chose. Leaving it alone means a cancelled build changes
    # nothing for the measurement, which is what cancelling is for; the items
    # already stored stay in the cohort and the next build tops it up.
    if stopped:
        report.notes.append("the set was left as it was: the build did not finish")
        return report
    if screen:
        # The caller's filter pass checks what is left and recomputes the set
        # once, after it (filter_and_rotate with rotate_anyway).
        return report

    report.rotation = rotate(
        space.key, dated, cohort=cohort, rebuilding=rebuilding, settings=conf
    )
    report.notes += report.rotation.notes
    if conf.dataset_mode is not DatasetMode.INCREMENTAL or rebuilding:
        report.notes.append(f"set: {report.rotation.line()}")

    return report


def filter_and_rotate(
    space: SpaceConfig,
    *,
    generator: str | None = None,
    cohort: str | None = None,
    collection: str | None = None,
    limit: int | None = None,
    settings: Settings | None = None,
    retrieve: Retriever | None = None,
    should_stop: Callable[[], bool] | None = None,
    rotate_anyway: bool = False,
    job_id: str = "",
) -> FilterSummary:
    """Screen pending pairs, then reconcile the window, the cohort and the cap.

    ``filter_stage.filter_pending`` decides grounding and the control gate on
    its own, without ever reading the corpus (invariant 1). What it cannot
    decide the same way is whether a pair it just turned active belongs in
    THIS measurement: that needs the document dates, and reading them is this
    module's business, as for ``generate_for_space``.
    Without this second step a rebuild's new cohort and the one it supersedes
    would sit active side by side until the next generation happened to run.

    Args:
        space: The node under test
        generator: Screen only this generator's pairs; None — every generator
        cohort: Screen only this cohort, and reconcile the set around it; None
            — every cohort, reconciled around whichever is current
        collection: ChromaDB collection to read document dates from; empty —
            the node's own name, and failing that, its key
        limit: How many pending pairs to screen; None — all of them
        settings: The process settings
        retrieve: What to check control questions with; None — the control
            set is rejected outright
        should_stop: Asked before every pair whether the owner has called the
            pass off
        rotate_anyway: Recompute the set even when this pass changed nothing:
            after a build whose questions were checked as they were written
        job_id: The job every filter decision is stamped with; empty — none

    Returns:
        What was screened, and what became of the window/cohort/cap once it
        joined the active pairs. ``rotation`` stays None when nothing was
        screened active: an empty pass has nothing new to reconcile, and
        reading the index for it would be a round trip spent confirming
        nothing changed.
    """
    conf = settings or get_settings()
    web_on = bool(filter_model(conf))
    current = cohort or cohorts.current(space.key, conf)
    dated: dict[str, Any] | None = None

    def read_dates() -> dict[str, Any]:
        client = ChromaClient(space, conf)
        name = collection or space.collection or space.key
        collection_id = client.collection_id(name)
        return (
            {doc.doc_id: doc.dated_at for doc in load_documents(client, collection_id)}
            if collection_id is not None
            else {}
        )

    # With the web check on, the set's unchecked pairs are checked in the same
    # pass; the window keeps that to the pairs that can still be measured.
    in_window: set[str] | None = None
    if web_on:
        dated = read_dates()
        if dated and conf.dataset_mode in (DatasetMode.ROLLING, DatasetMode.REBUILD):
            in_window = fresh_ids(dated, conf)[0]

    report = filter_pending(
        space,
        generator=generator,
        cohort=cohort,
        limit=limit,
        settings=conf,
        retrieve=retrieve,
        should_stop=should_stop,
        recheck_cohort=current if web_on else None,
        recheck_docs=in_window,
        job_id=job_id,
    )
    rechecked = report.web is not None and report.web.rechecked > 0
    if (
        not rotate_anyway
        and not rechecked
        and (not report.checked or not report.active)
    ):
        return report

    report.rotation = rotate(
        space.key,
        dated if dated is not None else read_dates(),
        cohort=current,
        settings=conf,
    )
    report.notes += report.rotation.notes
    return report
