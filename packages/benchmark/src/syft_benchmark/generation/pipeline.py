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

There are three paths of construction, and the choice between them is
automatic:

  * **spaCy** — the extractive categories, if there is a model for the
    document's language. Not a single call to an LLM, and the reference answer
    is cut out of the text rather than invented.
  * **a combined LLM call** — the same three categories when there is no model.
    One call for all three: there is no point calling the model three times
    over one chunk.
  * **an ordinary LLM call** — the remaining generators, each with its own
    prompt.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from sqlalchemy import select

from syft_benchmark.config import (
    DatasetMode,
    PairStatus,
    Settings,
    SpaceConfig,
    get_settings,
)
from syft_benchmark.db import ProcessedUnit, QaPair, session_scope
from syft_benchmark.generation import cohort as cohorts
from syft_benchmark.generation.control import Retriever
from syft_benchmark.generation.extractive import (
    COMBINED_SYSTEM,
    Masked,
    mask_with_spacy,
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
    reasons,
    user_prompt,
)
from syft_benchmark.generation.language import pick_spacy_model
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

_SPACY_LOCK = threading.Lock()

# Why a kind stopped writing.
BUDGET_REACHED = "budget reached"
OUT_OF_MATERIAL = "ran out of material"
FAILURE_STREAK = "failure streak"
CANCELLED = "cancelled"

# Drop reasons the pipeline adds to the generators' own.
DUPLICATE = "duplicate"
OVER_BUDGET = "over budget"
OVER_UNIT_LIMIT = "over the per-passage limit"


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
) -> list[QaPair]:
    """Write the items down as pending; returns the rows written.

    ``writer`` is the model call that wrote them (``recorded.new_call``):
    the first row stored from it keeps its texts in ``meta.writer``, the
    rest its id.

    Nothing here decides whether an item is fit to measure with — that moved
    to its own pass, ``filter_stage.filter_pending()``, which reads the
    grounding and the control gate off what is stored here rather than off
    the fresh candidate. So every pair below lands ``pending``, whatever its
    answer or its question turn out to be worth; only the filtering pass
    calls one ``active`` or ``rejected``.
    """
    if cap is not None:
        # The kind's question budget for this run (smaller on a trial run).
        # Counted per generator: a total divided between them would simply
        # drop some skills out of the set.
        room = cap - report.by_generator.get(generator.key, 0)
        stats = report.kinds.get(generator.key)
        if stats is not None:
            stats.drop(OVER_BUDGET, len(pairs) - max(room, 0))
        if room <= 0:
            return []
        pairs = pairs[:room]

    written: list[QaPair] = []
    for pair in pairs:
        stamp = (
            {"writer": writer_meta(writer, fragment[:8000])}
            if writer is not None
            else {}
        )
        try:
            with session_scope() as session:
                row = QaPair(
                    id=uuid.uuid4().hex,
                    space=space.key,
                    cohort=cohort,
                    # Empty where nothing named the launch — the CLI, a
                    # console call. NULL rather than "", so that "this
                    # launch's questions" cannot accidentally match them.
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
                    meta={
                        **pair.meta,
                        "grading": pair.meta.get("grading", generator.grading),
                        **stamp,
                    },
                    status=PairStatus.PENDING.value,
                    status_note="",
                    model=model,
                    question_hash=question_hash(pair.question),
                )
                session.add(row)
                session.flush()
                # Kept usable after the session closes, for the checks.
                session.expunge(row)
        except Exception as exc:  # noqa: BLE001 - duplicates caught after the fact, see the module docstring
            if "qa_pairs_unique" in str(exc):
                if writer is not None and "system" in stamp["writer"]:
                    # Not stored: the call's texts go on the next row.
                    writer["_stored"] = False
                report.duplicates += 1
                if generator.key in report.kinds:
                    report.kinds[generator.key].drop(DUPLICATE)
                continue
            raise

        written.append(row)
        report.pairs_made += 1
        report.by_generator[generator.key] = (
            report.by_generator.get(generator.key, 0) + 1
        )
        if generator.key in report.kinds:
            report.kinds[generator.key].written += 1
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


def _extractive_for_chunk(
    doc: Document,
    chunk: Chunk,
    keys: tuple[str, ...],
    conf: Settings,
    generator: Provider,
    hold: Callable[[], AbstractContextManager[None]] = nullcontext,
    record: dict[str, Any] | None = None,
) -> tuple[dict[str, list[Masked]], str, str | None]:
    """Build masked items from a chunk.

    ``record``, when given, gets the model call (``recorded.new_call``).

    Returns:
        The pairs keyed by generator, the path that was used and the error text
    """
    categories = tuple(
        category for category, key in EXTRACTIVE_CATEGORIES.items() if key in keys
    )
    if not categories:
        return {}, "", None

    if conf.extractive_mode != "llm":
        # One thread at a time: a spaCy pipeline is not made for sharing.
        with _SPACY_LOCK:
            nlp = pick_spacy_model(chunk.text, conf.spacy_models)
            by_category = (
                mask_with_spacy(chunk.text, nlp, categories) if nlp is not None else {}
            )
        if nlp is not None:
            return (
                {EXTRACTIVE_CATEGORIES[c]: v for c, v in by_category.items()},
                "spacy",
                None,
            )
        if conf.extractive_mode == "spacy":
            # The mode was chosen explicitly: falling back to the LLM silently
            # is not allowed, otherwise the reproducibility it was chosen for
            # is lost.
            return {}, "", "there is no spaCy model for the document's language"

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
        return {}, "", str(exc)

    by_category = parse_combined(data, categories)
    return {EXTRACTIVE_CATEGORIES[c]: v for c, v in by_category.items()}, "llm", None


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
        prompt = (
            f'Document: {doc.title}\n\nText:\n"""\n{text}\n"""\n\nGenerate {tasks}.'
        )
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
    model: str = ""
    parsed: int = 0
    error: str | None = None
    # The writer call (``recorded.new_call``); empty — no model call (spaCy).
    call: dict[str, Any] = field(default_factory=dict)


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
    report: GenerationReport, queues: Sequence[_Queue], cap: int, *, cancelled: bool
) -> None:
    """Why each kind stopped writing."""
    queue_of = {key: queue for queue in queues for key in queue.keys}
    for key, stats in report.kinds.items():
        queue = queue_of.get(key)
        left = queue is not None and queue.pos < len(queue.units)
        if stats.written >= cap:
            stats.stopped = BUDGET_REACHED
        elif queue is not None and queue.gave_up:
            stats.stopped = FAILURE_STREAK
        elif cancelled and left:
            stats.stopped = CANCELLED
        else:
            stats.stopped = OUT_OF_MATERIAL


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
            (``filter_and_rotate(rotate_anyway=True)``)
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
            + ") were built as pending — whether retrieval in fact answers "
            "one of them is for filtering to decide, not this pass"
        )

    client = ChromaClient(space, conf)
    name = collection or space.collection or space.key
    collection_id = client.collection_id(name)
    if collection_id is None:
        report.notes.append(f'there is no collection "{name}"')
        _settle_kinds(report, [], cap, cancelled=False)
        return report

    documents = load_documents(client, collection_id)

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

    def wanted(queue: _Queue) -> tuple[str, ...]:
        return tuple(
            key
            for key in queue.keys
            if report.by_generator.get(key, 0) + reserved.get(key, 0) < cap
        )

    def work(
        queue: _Queue, doc: Document, chunk: Chunk | None, keys: tuple[str, ...]
    ) -> _Outcome:
        """One unit on a worker thread: the model call and the cleaning."""
        whole = document_text(doc)
        call: dict[str, Any] = {}
        if queue.spec is None:
            assert chunk is not None
            by_key, path, error = _extractive_for_chunk(
                doc, chunk, keys, conf, provider, hold=slots.hold, record=call
            )
            if error:
                return _Outcome(error=error)
            made: dict[str, tuple[list[Pair], list[str]]] = {}
            for key, masked in by_key.items():
                good, bad = _masked_to_pairs(masked, whole)
                # pairs_per_chunk on both paths: spaCy masks every entity it
                # finds, and one dense passage would spend a kind's budget.
                surplus = max(0, len(good) - conf.pairs_per_chunk)
                made[key] = (
                    good[: conf.pairs_per_chunk],
                    bad + [OVER_UNIT_LIMIT] * surplus,
                )
            return _Outcome(
                pairs=made,
                model=f"{path}:{conf.generator_model}",
                parsed=sum(len(v) for v in by_key.values()),
                call=call,
            )
        with slots.hold():
            items, error = _run_llm_generator(
                queue.spec, doc, chunk, conf, provider, record=call
            )
        if error:
            return _Outcome(error=error)
        good, bad = queue.spec.clean(items, conf.pairs_per_chunk, whole)
        return _Outcome(
            pairs={queue.spec.key: (good, bad)},
            model=conf.generator_model,
            parsed=len(good),
            call=call,
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
                report.kinds[key].units_read += 1
                report.kinds[key].failed_units += bool(outcome.error)
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
                cap=cap,
                writer=outcome.call or None,
            )
            if screening is not None and check_pool is not None:
                checks.extend(check_pool.submit(_checked, screening, r) for r in rows)
        _mark_processed(
            space.key, queue.marker, unit_id, queue.scope, outcome.parsed, cohort
        )
        queue.streak = 0 if report.pairs_made > before else queue.streak + 1
        tell()

    checks: list[Future[None]] = []
    running: dict[
        Future[_Outcome], tuple[_Queue, Document, Chunk | None, tuple[str, ...]]
    ] = {}
    check_pool = (
        ThreadPoolExecutor(max_workers=width, thread_name_prefix="check")
        if screening is not None
        else None
    )
    try:
        with ThreadPoolExecutor(max_workers=width, thread_name_prefix="gen") as pool:
            while True:
                # Round-robin over the kinds, one unit each per sweep.
                dispatched = True
                while dispatched and len(running) < width and not called_off():
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
            # Written questions are checked before the build reports; on a stop
            # the checks not started leave their questions pending.
            check_pool.shutdown(wait=True)
    tell(final=True)
    _settle_kinds(report, queues, cap, cancelled=stopped)
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
    module's business, the same as it always has been for ``generate_for_space``.
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
