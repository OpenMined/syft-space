"""Stage 2: build items from new chunks and documents, then recompute the set.

A run is interruptible and repeatable: each parsed unit is marked as soon as
it is stored, every item is written in its own transaction, and duplicates are
cut off by a unique index over the question hash (the same question can come
out of neighbouring chunks).

The dataset mode sets what generation sees. Incremental accumulates; rolling
builds only from documents inside the freshness window; a rebuild builds a
fresh question pool from the same material as a separate cohort, so that
diverging metrics point at the questions rather than the material. What takes
part in the measurement is recomputed in ``rotation.py``; cohorts are in
``cohort.py``; the top-up after a build is sized in ``top_up.py``.

The three masking kinds share one combined model call per chunk; every other
generator has its own call and prompt.
"""

from __future__ import annotations

import hashlib
import random
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field, replace
from typing import Any

from loguru import logger
from sqlalchemy import select

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
from syft_benchmark.generation import decisions, entities, recorded, writer_log
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
    Generator,
    Scope,
    document_prompt,
    document_text,
    reasons,
    user_prompt,
    writer_passage,
)
from syft_benchmark.generation.language import detect_language, written_text
from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.recorded import new_call, writer_meta
from syft_benchmark.generation.rotation import RotationReport, fresh_ids, rotate
from syft_benchmark.generation.slots import Latch, model_slots
from syft_benchmark.generation.top_up import (
    TOP_UP_ROUNDS,
    kind_targets,
    survival_rates,
    survivors,
    top_up_plan,
)
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

# Headroom on the answer cap over the computed length of the items. A reasoning
# model spends output tokens before it prints the JSON, and a reply cut off
# mid-object is lost though paid for. max_tokens bounds rather than bills; a
# cut-off call is also retried with a doubled budget up to the shared answer
# ceiling (``chat`` in llm/client.py), so this only saves a wasted call.
REASONING_HEADROOM = 800

# How often the build's progress line is rewritten, at most.
_PROGRESS_SECONDS = 0.5

# Why a kind stopped writing.
BUDGET_REACHED = "budget reached"
OUT_OF_MATERIAL = "ran out of material"
FAILURE_STREAK = "failure streak"
CANCELLED = "cancelled"
COST_LIMIT = "top-up cost limit"

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


def pick_chunks(
    documents: list[Document],
    processed: set[str],
    limit: int | None = None,
    seed: str = "",
) -> list[tuple[Document, Chunk]]:
    """What to parse in this run, in the order to parse it.

    We walk the documents round-robin rather than in order: a run that stops
    on its question budget then has read every article a little, rather than
    the first articles whole and the last ones not at all.

    Args:
        documents: The documents in play
        processed: Chunks this queue has already parsed
        limit: How many to pick; None — every unparsed chunk
        seed: Shuffle each document's passages with this seed, so a walk
            stopped early does not read only the opening ones; empty — in order
    """
    order = {
        doc.doc_id: (
            random.Random(f"{seed}:{doc.doc_id}").sample(doc.chunks, len(doc.chunks))
            if seed
            else doc.chunks
        )
        for doc in documents
    }
    picked: list[tuple[Document, Chunk]] = []
    depth = 0
    while limit is None or len(picked) < limit:
        added = False
        for doc in documents:
            chunks = order[doc.doc_id]
            if depth >= len(chunks):
                continue
            chunk = chunks[depth]
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


def _processed_ids(space: str, generator: str, cohort: str, conf: Settings) -> set[str]:
    """What THIS cohort has already parsed.

    The marks of earlier builds do not count: a rebuild is a fresh parse of the
    same material, and someone else's mark would stop it.
    """
    with session_scope(conf) as session:
        rows = session.execute(
            select(ProcessedUnit.unit_id).where(
                ProcessedUnit.space == space,
                ProcessedUnit.generator == generator,
                ProcessedUnit.cohort == cohort,
            )
        ).scalars()
        return set(rows)


def _mark_processed(
    space: str,
    generator: str,
    unit_id: str,
    kind: str,
    made: int,
    cohort: str,
    conf: Settings,
) -> None:
    with session_scope(conf) as session:
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
    context: str,
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
    conf: Settings,
) -> QaPair | None:
    """Write one item; None — a duplicate, not stored.

    ``context`` is the text the writer was given (``writer_passage``), which
    the grounding check reads back. ``writer`` and ``check`` are the unit's
    writer and entity check calls: the first row stored from each keeps its
    texts, the rest its id. A ``rejected`` item is stored rejected, with its
    decision stamped.
    """
    meta: dict[str, Any] = {
        **pair.meta,
        "grading": pair.meta.get("grading", generator.grading),
        **article_stamp(doc),
    }
    if writer is not None:
        meta[recorded.WRITER] = writer_meta(writer, context)
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
        with session_scope(conf) as session:
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
                context=context,
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
    context: str,
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
    lost: list[Dropped] | None = None,
) -> list[QaPair]:
    """Write the items down as pending; returns the rows written.

    ``context`` is the text the writer was given. ``writer`` is the model
    call that wrote them (``recorded.new_call``), ``check`` the unit's entity
    check call (``_entity_check``): the first row stored from each keeps its
    texts, the rest its id. ``rejected`` — the items rejected as written:
    stored rejected, outside the kind's budget and the returned rows. ``lost``
    gets the items not stored: over the budget, or duplicates.

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
        if lost is not None:
            lost += [
                Dropped(OVER_BUDGET, p.question, p.answer)
                for p in pairs[max(room, 0) :]
            ]
        pairs = pairs[: max(room, 0)]

    def one(pair: Pair, refused: _Rejected | None = None) -> QaPair | None:
        return _row(
            space,
            doc,
            chunk_id,
            context,
            pair,
            generator,
            model,
            collection,
            cohort=cohort,
            job=job,
            writer=writer,
            check=check,
            rejected=refused,
            conf=conf,
        )

    written: list[QaPair] = []
    for pair in pairs:
        row = one(pair)
        if row is None:
            report.duplicates += 1
            if generator.key in report.kinds:
                report.kinds[generator.key].drop(DUPLICATE)
            if lost is not None:
                lost.append(Dropped(DUPLICATE, pair.question, pair.answer))
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
) -> tuple[list[Pair], list[Dropped]]:
    """Reject the masked sentences that fail and turn the rest into items."""
    good: list[Pair] = []
    rejected: list[Dropped] = []
    for item in masked:
        reason = reject_reason(item.question, document, task_type="extractive")
        if reason:
            rejected.append(Dropped(reason, item.question, item.answer))
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

    ``record``, when given, gets the model call (``recorded.new_call``), a
    failed one with an empty reply.
    """
    categories = tuple(
        category for category, key in EXTRACTIVE_CATEGORIES.items() if key in keys
    )
    out = _Extracted()
    if not categories:
        return out

    searching, engine = web_search_for(conf, "generator", generator.model)
    system = COMBINED_SYSTEM.format(n=conf.pairs_per_chunk)
    passage = writer_passage(doc, chunk)
    user = user_prompt(doc, chunk, conf.pairs_per_chunk)
    raw = ""
    usage: dict[str, Any] = {}
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
    except LLMError as exc:
        out.error = str(exc)
    if record is not None:
        record.update(
            new_call(
                model=generator.model,
                system=system,
                user=user,
                reply=raw,
                passage=passage,
                usage=usage,
            )
        )
    if out.error:
        return out
    try:
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

    ``record``, when given, gets the call (``recorded.new_call``), a failed
    one with an empty reply.
    """
    tasks = 1 if generator.single_item else conf.pairs_per_chunk
    if generator.scope is Scope.DOCUMENT:
        prompt = document_prompt(doc, tasks)
    else:
        assert chunk is not None
        prompt = user_prompt(doc, chunk, tasks)
    passage = writer_passage(doc, chunk)

    # A single long item starts from the shared answer ceiling: from a
    # per-item estimate a reasoning model cuts it off, and the cut-off calls
    # are billed before the client's doubling reaches a budget that holds.
    budget = generator.tokens_per_pair * tasks + REASONING_HEADROOM
    if generator.single_item:
        budget = max(budget, conf.answer_max_tokens)

    searching, engine = web_search_for(conf, "generator", provider.model)
    system = generator.system.format(n=tasks)
    raw = ""
    usage: dict[str, Any] = {}
    failed: str | None = None
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
        failed = str(exc)
    if record is not None:
        record.update(
            new_call(
                model=provider.model,
                system=system,
                user=prompt,
                reply=raw,
                passage=passage,
                usage=usage,
            )
        )
    if failed is not None:
        return [], failed

    try:
        # Looking for an array inside a single-object reply is unreliable.
        if generator.single_item:
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
    scope: Scope
    units: Sequence[tuple[Document, Chunk | None]]
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

    # Per kind, the questions to store and the reasons the rest were dropped.
    pairs: dict[str, tuple[list[Pair], list[str]]] = field(default_factory=dict)
    # Per kind, the items rejected as written.
    rejected: dict[str, list[_Rejected]] = field(default_factory=dict)
    # Per kind, the drafts thrown away as written.
    drafts: dict[str, list[Dropped]] = field(default_factory=dict)
    model: str = ""
    # Items the unit gave, after cleaning and the language check, every kind
    # together; what the unit is marked processed with.
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

    The extractive kinds are built in one pass and marked under one key. Every
    other kind has its own queue: with a shared one, a kind added later would
    skip everything an earlier kind has parsed.

    The documents are shuffled once per cohort and each queue starts at its own
    point of that order, so kinds that stop on their budget together cover the
    whole window. Each queue also takes every article's passages in its own
    shuffled order.
    """
    keys = ([extractive[0]] if extractive else []) + [
        spec.key for spec in specs if spec.key not in EXTRACTIVE_KEYS
    ]
    shuffled = random.Random(cohort).sample(documents, len(documents))
    report.notes.append(
        f"articles shuffled (seed: cohort {cohort}), each kind starting at its "
        f"own point"
    )

    def start(key: str) -> list[Document]:
        """The shuffled documents, rotated to this queue's starting point."""
        at = keys.index(key) * len(shuffled) // max(1, len(keys))
        return shuffled[at:] + shuffled[:at]

    queues: list[_Queue] = []
    if extractive:
        processed = _processed_ids(space, extractive[0], cohort, conf)
        batch = pick_chunks(
            start(extractive[0]), processed, seed=f"{cohort}:{extractive[0]}"
        )
        if not batch:
            report.notes.append("masking: there are no new chunks")
        else:
            queues.append(
                _Queue(
                    "masking",
                    extractive,
                    extractive[0],
                    Scope.CHUNK,
                    batch,
                    conf.pairs_per_chunk,
                )
            )
    for spec in specs:
        if spec.key in EXTRACTIVE_KEYS:
            continue
        processed = _processed_ids(space, spec.key, cohort, conf)
        units: Sequence[tuple[Document, Chunk | None]]
        mine = start(spec.key)
        if spec.scope is Scope.DOCUMENT:
            units = [(doc, None) for doc in mine if doc.doc_id not in processed]
            if not units:
                report.notes.append(f"{spec.key}: there are no new documents")
                continue
        else:
            units = pick_chunks(mine, processed, seed=f"{cohort}:{spec.key}")
            if not units:
                report.notes.append(f"{spec.key}: there are no new chunks")
                continue
        per_unit = 1 if spec.single_item else conf.pairs_per_chunk
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


def _checked(screening: Screening, row: QaPair) -> None:
    """Screen one written question; a failure leaves it pending."""
    try:
        screening.screen(row)
    except Exception as exc:  # noqa: BLE001 - the next filter pass checks it again
        logger.warning(f"{row.id}: the check failed, left pending: {exc}")


type _Unit = tuple[_Queue, Document, Chunk | None, tuple[str, ...]]


class _Build:
    """One build's walk over its queues: dispatching units to the model,
    storing what they write, and handing it to the checks.

    Every mutable counter (``report``, ``caps``, the queues) is touched only
    from the dispatching thread; workers run ``_work`` and return an
    ``_Outcome``.
    """

    def __init__(
        self,
        space: SpaceConfig,
        conf: Settings,
        *,
        report: GenerationReport,
        queues: list[_Queue],
        caps: dict[str, int],
        provider: Provider,
        collection: str,
        cohort: str,
        job: str,
        latch: Latch,
        screen: bool,
        retrieve: Retriever | None,
        on_unit: Callable[[str, int, int, int], None] | None,
        on_progress: Callable[[str], None] | None,
    ) -> None:
        self.space = space
        self.conf = conf
        self.report = report
        self.queues = queues
        self.caps = caps
        self.provider = provider
        self.collection = collection
        self.cohort = cohort
        self.job = job
        self.writing = writer_log.WriterLog(job, conf)
        self.latch = latch
        self.on_unit = on_unit
        self.on_progress = on_progress
        self.width = max(1, conf.concurrency)
        self.slots = model_slots(conf)
        self._tell_lock = threading.Lock()
        self._told = 0.0
        # Checks run as soon as a question is written, sharing the model limit.
        self.screening = (
            Screening(
                space.key,
                conf,
                retrieve=retrieve,
                should_stop=latch,
                slots=self.slots,
                on_verdict=self.tell,
                job_id=job,
            )
            if screen
            else None
        )
        self.stopped = False
        # Questions per kind already asked for by units in flight: a unit is
        # dispatched only while its kind has room beyond them, so the walk
        # reads no passage it does not need.
        self.reserved: dict[str, int] = {}
        # The ids of the questions written, per kind.
        self.built: dict[str, list[str]] = {}
        self._check_pool: ThreadPoolExecutor | None = None

    def called_off(self) -> bool:
        """Whether to stop before the next unit. Said once, in the report."""
        if not self.stopped and self.latch():
            self.stopped = True
            self.report.notes.append("the build was stopped at the owner's request")
            logger.info(f"{self.space.key}: generation stopped at the owner's request")
        return self.stopped

    def _gave_up(self, queue: _Queue) -> bool:
        """Units in a row that wrote nothing (failed calls, or replies all
        cleaned away) stop a kind that keeps paying for nothing."""
        give_up = self.conf.max_consecutive_failures
        if give_up and queue.streak >= give_up:
            self.report.notes.append(
                f"{queue.label}: {queue.streak} units in a row wrote nothing — "
                f"stopped before its budget was spent"
            )
            return True
        return False

    def tell(self, final: bool = False) -> None:
        """Report "written N · checked M · removed R", at most every
        ``_PROGRESS_SECONDS`` unless ``final``."""
        if self.on_progress is None:
            return
        with self._tell_lock:
            now = time.monotonic()
            if not final and now - self._told < _PROGRESS_SECONDS:
                return
            self._told = now
            checked = self.screening.report.checked if self.screening else 0
            removed = self.screening.report.rejected if self.screening else 0
            self.on_progress(
                f"written {self.report.pairs_made} · checked {checked} · "
                f"removed {removed}"
            )

    def _wanted(self, queue: _Queue) -> tuple[str, ...]:
        """The queue's kinds that still have room beyond the units in flight."""
        return tuple(
            key
            for key in queue.keys
            if self.report.by_generator.get(key, 0) + self.reserved.get(key, 0)
            < self.caps[key]
        )

    def _work(
        self, queue: _Queue, doc: Document, chunk: Chunk | None, keys: tuple[str, ...]
    ) -> _Outcome:
        """One unit on a worker thread: the model calls and the cleaning."""
        conf = self.conf
        whole = document_text(doc)
        call: dict[str, Any] = {}
        # Per kind: what passed the generator's own screening and the language
        # check, the drafts dropped, and what is stored rejected.
        made: dict[str, list[Pair]] = {}
        bad: dict[str, list[Dropped]] = {}
        refused: dict[str, list[_Rejected]] = {}
        if queue.spec is None:
            assert chunk is not None
            extracted = _extractive_for_chunk(
                doc, chunk, keys, conf, self.provider, hold=self.slots.hold, record=call
            )
            if extracted.error:
                return _Outcome(error=extracted.error, call=call)
            for key, masked in extracted.by_key.items():
                good, bad[key] = _masked_to_pairs(masked, whole)
                made[key], refused[key] = _drop_wrong_language(good, whole)
        else:
            with self.slots.hold():
                items, error = _run_llm_generator(
                    queue.spec, doc, chunk, conf, self.provider, record=call
                )
            if error:
                return _Outcome(error=error, call=call)
            key = queue.spec.key
            good, bad[key] = queue.spec.clean(items, conf.pairs_per_chunk, whole)
            made[key], refused[key] = _drop_wrong_language(good, whole)
        parsed = sum(len(items) for items in made.values())
        made, unclear, check = _screen_entities(
            made, conf, self.provider, self.slots.hold
        )
        pairs: dict[str, tuple[list[Pair], list[str]]] = {}
        for key, good in made.items():
            refused[key] += unclear[key]
            dropped = [d.reason for d in bad[key]] + [r.drop for r in refused[key]]
            if queue.spec is None:
                # The model may return more than asked, and one dense passage
                # would spend a kind's budget.
                surplus = [
                    Dropped(OVER_UNIT_LIMIT, p.question, p.answer)
                    for p in good[conf.pairs_per_chunk :]
                ]
                bad[key] += surplus
                dropped += [d.reason for d in surplus]
                good = good[: conf.pairs_per_chunk]
            pairs[key] = (good, dropped)
        return _Outcome(
            pairs=pairs,
            rejected=refused,
            drafts=bad,
            model=self.provider.model,
            parsed=parsed,
            call=call,
            check=check,
        )

    def _settle(self, unit: _Unit, outcome: _Outcome) -> None:
        """Store one unit's questions and hand them to the checks."""
        queue, doc, chunk, keys = unit
        report = self.report
        context = writer_passage(doc, chunk)

        def keep(dropped: dict[str, list[Dropped]], error: str | None = None) -> None:
            self.writing.keep(
                outcome.call,
                dropped,
                document_title=doc.title,
                file_name=doc.file_name,
                passage=context,
                error=error,
            )

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
            logger.warning(f"{self.space.key}/{where}: {outcome.error}")
            keep({key: [] for key in keys}, error=outcome.error)
            return
        before = report.pairs_made
        unit_id = chunk.chunk_id if chunk is not None else doc.doc_id
        shown = chunk.chunk_id[:10] if chunk is not None else doc.title[:24]
        lost: dict[str, list[Dropped]] = {}
        for key, (good, bad) in outcome.pairs.items():
            lost[key] = list(outcome.drafts.get(key, ()))
            if bad:
                report.notes.append(f"{key} {shown}: {reasons(bad)}")
                if key in report.kinds:
                    for why in bad:
                        report.kinds[key].drop(why)
            rows = _store(
                self.space,
                doc,
                unit_id if chunk is not None else f"doc:{doc.doc_id}",
                context,
                good,
                GENERATORS[key],
                outcome.model,
                self.collection,
                report,
                conf=self.conf,
                cohort=self.cohort,
                job=self.job,
                cap=self.caps[key],
                writer=outcome.call or None,
                check=outcome.check or None,
                rejected=outcome.rejected.get(key, ()),
                lost=lost[key],
            )
            self.built.setdefault(key, []).extend(row.id for row in rows)
            if self.screening is not None and self._check_pool is not None:
                for row in rows:
                    self._check_pool.submit(_checked, self.screening, row)
        keep({key: drafts for key, drafts in lost.items() if drafts})
        _mark_processed(
            self.space.key,
            queue.marker,
            unit_id,
            queue.scope.value,
            outcome.parsed,
            self.cohort,
            self.conf,
        )
        queue.streak = 0 if report.pairs_made > before else queue.streak + 1
        self.tell()

    def _next_unit(self, queue: _Queue) -> _Unit | None:
        """The queue's next unit to dispatch, with the kinds it is for; None —
        the queue has nothing to dispatch now."""
        if queue.done or queue.pos >= len(queue.units):
            return None
        if self._gave_up(queue):
            queue.done = True
            queue.gave_up = True
            return None
        keys = self._wanted(queue)
        if not keys:
            return None
        doc, chunk = queue.units[queue.pos]
        queue.pos += 1
        self.report.units_seen += 1
        if self.on_unit is not None:
            self.on_unit(
                queue.label, queue.pos, len(queue.units), self.report.pairs_made
            )
        for key in keys:
            self.reserved[key] = self.reserved.get(key, 0) + queue.per_unit
        return queue, doc, chunk, keys

    def walk(self, halt: Callable[[], bool] = lambda: False) -> None:
        """Walk the queues until every kind has its cap, the material runs
        out, the owner stops it or ``halt`` says so."""
        running: dict[Future[_Outcome], _Unit] = {}
        # The workers charge the current cost meter: the top-up's limit reads it.
        self._check_pool = (
            ThreadPoolExecutor(
                max_workers=self.width, thread_name_prefix="check", **cost.pool_kwargs()
            )
            if self.screening is not None
            else None
        )
        try:
            with ThreadPoolExecutor(
                max_workers=self.width, thread_name_prefix="gen", **cost.pool_kwargs()
            ) as pool:
                while True:
                    # Round-robin over the kinds, one unit each per sweep.
                    dispatched = True
                    while (
                        dispatched
                        and len(running) < self.width
                        and not self.called_off()
                        and not halt()
                    ):
                        dispatched = False
                        for queue in self.queues:
                            if len(running) >= self.width:
                                break
                            unit = self._next_unit(queue)
                            if unit is None:
                                continue
                            running[pool.submit(self._work, *unit)] = unit
                            dispatched = True
                    if not running:
                        break
                    finished, _ = wait(running, return_when=FIRST_COMPLETED)
                    for future in finished:
                        unit = running.pop(future)
                        queue, _, _, keys = unit
                        for key in keys:
                            self.reserved[key] -= queue.per_unit
                        self._settle(unit, future.result())
        finally:
            if self._check_pool is not None:
                # Written questions are checked before the build reports; on a
                # stop the checks not started leave their questions pending.
                self._check_pool.shutdown(wait=True)

    def top_up(self, cap: int) -> bool:
        """More of each kind the checks left short of its target, within
        ``top_up_max_usd``; returns whether that cost limit was hit."""
        conf = self.conf
        report = self.report
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
                if self.called_off() or over():
                    break
                open_keys = {
                    key
                    for queue in self.queues
                    if not queue.done and queue.pos < len(queue.units)
                    for key in queue.keys
                }
                rates = survival_rates(self.space.key, list(targets), conf)
                plan = {
                    key: extra
                    for key, extra in top_up_plan(
                        targets, survivors(self.built, conf), rates, cap
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
                    self.caps[key] = report.by_generator.get(key, 0) + extra
                self.walk(halt=over)
                for key in plan:
                    report.kinds[key].topped_up += report.by_generator.get(
                        key, 0
                    ) - before.get(key, 0)
            return over()


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
            run. The walk stops as soon as every generator has its fill, so a
            trial does not mark processed chunks it never used
        on_unit: Told before every unit which generator is being built, which
            unit of its batch this is, how big that batch is, and how many
            questions exist so far
        should_stop: Asked before every unit (one paid generator call) whether
            the owner has called the build off; None — the build runs to the end
        screen: Check each question as soon as it is written: grounding or
            the control gate, then the web check (``filter_stage.Screening``),
            while generation goes on. The set is then not recomputed here: the
            caller's filter pass checks what is left and recomputes it once
            (``filter_and_rotate(rotate_anyway=True)``). After the build, a
            kind short of its target (``top_up.kind_targets``) gets more
            written and checked the same way: up to ``TOP_UP_ROUNDS`` rounds,
            sized by its survival rate on this target, until
            ``top_up_max_usd`` is spent
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
    # a new label; the other modes top up the current cohort.
    rebuilding = new_cohort or conf.dataset_mode is DatasetMode.REBUILD
    cohort = (
        (cohort_label or cohorts.new_label())
        if rebuilding
        else cohorts.current(space.key, conf)
    )
    report = GenerationReport(space=space.key, cohort=cohort)

    # The question budget per kind ("Write at most" on the page is
    # chunks_per_run * pairs_per_chunk * kinds), counted in questions written,
    # so a passage that yields less does not shrink the set.
    quota = (limit or conf.chunks_per_run) * conf.pairs_per_chunk
    cap = quota if per_generator is None else min(quota, per_generator)
    # Per kind; the top-up raises a short kind's.
    caps = {spec.key: cap for spec in specs}
    for spec in specs:
        report.kinds[spec.key] = KindStats(
            kind=spec.key,
            unit="article" if spec.scope is Scope.DOCUMENT else "passage",
            budget=cap,
        )

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
    # Resolved once per run: the role's address and key may differ from the
    # shared ones, and the perimeter check has to pass before the first call.
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
        backfill(space.key, documents, conf)
    except Exception:  # noqa: BLE001 - the dates only feed the report
        logger.exception(f"{space.key}: article dates were not stamped")

    # The freshness window cuts material off BEFORE generation, so no document
    # outside the measurement is paid for. In incremental mode it bounds what
    # to build from but does not pull built items out of the set.
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

    build = _Build(
        space,
        conf,
        report=report,
        queues=queues,
        caps=caps,
        provider=provider,
        collection=name,
        cohort=cohort,
        job=job,
        latch=Latch(should_stop),
        screen=screen,
        retrieve=retrieve,
        on_unit=on_unit,
        on_progress=on_progress,
    )
    build.walk()

    limited = False
    if build.screening is not None and conf.top_up_max_usd > 0 and not build.stopped:
        limited = build.top_up(cap)
        if limited:
            report.notes.append(
                f"top-up stopped at its cost limit, ${conf.top_up_max_usd:g}"
            )
    build.tell(final=True)
    _settle_kinds(report, queues, caps, cancelled=build.stopped, limited=limited)
    if build.screening is not None:
        report.screened = build.screening.summary()

    # Recomputing the set comes last, and runs in incremental mode too so the
    # report states the set's size in every mode. Not after a cancelled
    # build: that would make a half-built cohort the measured set. The items
    # already stored stay in the cohort and the next build tops it up.
    if build.stopped:
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
    web_on = bool(conf.filter_model)
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
