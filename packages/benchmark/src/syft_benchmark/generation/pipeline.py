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
import uuid
from collections.abc import Callable, Sequence
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
from syft_benchmark.generation.filter_stage import FilterSummary, filter_pending
from syft_benchmark.generation.generators import (
    EXTRACTIVE_CATEGORIES,
    EXTRACTIVE_KEYS,
    GENERATORS,
    MAX_DOCUMENT_CHARS,
    Generator,
    reasons,
    user_prompt,
)
from syft_benchmark.generation.language import pick_spacy_model
from syft_benchmark.generation.pair import Pair
from syft_benchmark.generation.quality import reject_reason
from syft_benchmark.generation.rotation import RotationReport, fresh_ids, rotate
from syft_benchmark.llm import (
    LLMError,
    Provider,
    chat,
    generator_provider,
    parse_json_list,
    parse_json_object,
)
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
    # How recomputing the set ended. In incremental mode there is nothing to
    # recompute, and this stays None — which is not the same as "nothing
    # changed".
    rotation: RotationReport | None = None


def question_hash(question: str) -> str:
    """A fingerprint of the question, guarding against cross-cycle duplicates."""
    normalized = " ".join(question.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def document_text(doc: Document) -> str:
    """The whole document — the pool the endpoint answers from."""
    return "\n\n".join(chunk.text for chunk in doc.chunks)


def pick_chunks(
    documents: list[Document], processed: set[str], limit: int
) -> list[tuple[Document, Chunk]]:
    """What to parse in this run.

    We walk the documents round-robin rather than in order: the daily cycle
    takes a little at a time, and walking them in order would give the first
    documents their items in a week and the last ones never.
    """
    picked: list[tuple[Document, Chunk]] = []
    depth = 0
    while len(picked) < limit:
        added = False
        for doc in documents:
            if depth >= len(doc.chunks):
                continue
            chunk = doc.chunks[depth]
            added = True
            if chunk.chunk_id in processed:
                continue
            picked.append((doc, chunk))
            if len(picked) >= limit:
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
) -> None:
    """Write the items down as pending.

    Nothing here decides whether an item is fit to measure with — that moved
    to its own pass, ``filter_stage.filter_pending()``, which reads the
    grounding and the control gate off what is stored here rather than off
    the fresh candidate. So every pair below lands ``pending``, whatever its
    answer or its question turn out to be worth; only the filtering pass
    calls one ``active`` or ``rejected``.
    """
    if cap is not None:
        # A trial run builds a couple of questions per generator and asks those
        # — the same cap on both halves, so a configuration can be tried end to
        # end for the price of a handful of calls. Counted per generator, like
        # the one on asking: a total divided between them would simply drop
        # some skills out of the trial.
        room = cap - report.by_generator.get(generator.key, 0)
        if room <= 0:
            return
        pairs = pairs[:room]

    for pair in pairs:
        try:
            with session_scope() as session:
                session.add(
                    QaPair(
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
                        },
                        status=PairStatus.PENDING.value,
                        status_note="",
                        model=model,
                        question_hash=question_hash(pair.question),
                    )
                )
        except Exception as exc:  # noqa: BLE001 - duplicates caught after the fact, see the module docstring
            if "qa_pairs_unique" in str(exc):
                report.duplicates += 1
                continue
            raise

        report.pairs_made += 1
        report.by_generator[generator.key] = (
            report.by_generator.get(generator.key, 0) + 1
        )


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
) -> tuple[dict[str, list[Masked]], str, str | None]:
    """Build masked items from a chunk.

    Returns:
        The pairs keyed by generator, the path that was used and the error text
    """
    categories = tuple(
        category for category, key in EXTRACTIVE_CATEGORIES.items() if key in keys
    )
    if not categories:
        return {}, "", None

    if conf.extractive_mode != "llm":
        nlp = pick_spacy_model(chunk.text, conf.spacy_models)
        if nlp is not None:
            by_category = mask_with_spacy(chunk.text, nlp, categories)
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

    try:
        raw, _usage = chat(
            COMBINED_SYSTEM.format(n=conf.pairs_per_chunk),
            user_prompt(doc, chunk, conf.pairs_per_chunk),
            provider=generator,
            max_tokens=90 * conf.pairs_per_chunk * len(categories) + 200,
            settings=conf,
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
) -> tuple[list[dict[str, Any]], str | None]:
    """A single model call for one particular generator."""
    tasks = 1 if generator.key == "tiered_explanation" else conf.pairs_per_chunk
    if generator.scope == "document":
        text = document_text(doc)[:MAX_DOCUMENT_CHARS]
        prompt = (
            f'Document: {doc.title}\n\nText:\n"""\n{text}\n"""\n\nGenerate {tasks}.'
        )
    else:
        assert chunk is not None
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

    try:
        raw, _usage = chat(
            generator.system.format(n=tasks),
            prompt,
            provider=provider,
            max_tokens=budget,
            settings=conf,
        )
    except LLMError as exc:
        return [], str(exc)

    try:
        # tiered answers with an object, the rest with an array; the object is
        # parsed by a separate call, because looking for an array in such an
        # answer is risky.
        if generator.key == "tiered_explanation":
            return [parse_json_object(raw)], None
        return parse_json_list(raw), None
    except LLMError as exc:
        return [], str(exc)


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
        limit: How many units to take; defaults to the settings
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

    def filled() -> bool:
        """Whether every generator asked for has reached the cap.

        Checked before each unit rather than after: a trial that has what it
        needs must not parse one more chunk, because parsing marks it processed
        and a later full run would find nothing there to build from.
        """
        if per_generator is None:
            return False
        wanted = [s.key for s in specs]
        return all(report.by_generator.get(key, 0) >= per_generator for key in wanted)

    def called_off() -> bool:
        """Whether to stop before the next unit. Said once, in the report."""
        nonlocal stopped
        if not stopped and should_stop is not None and should_stop():
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
                f"{undated} documents have no date in their header — the window "
                f"does not apply to them"
            )
        if not documents:
            report.notes.append("there is not a single document in the window")

    budget = limit or conf.chunks_per_run

    extractive = tuple(s.key for s in specs if s.key in EXTRACTIVE_KEYS)
    per_chunk = [
        s for s in specs if s.scope == "chunk" and s.key not in EXTRACTIVE_KEYS
    ]
    per_document = [s for s in specs if s.scope == "document"]

    # --- by chunk ---------------------------------------------------------
    # The extractive ones are built in a single pass: three categories out of
    # one parse, which is why they are marked under one key.
    if extractive:
        processed = _processed_ids(space.key, extractive[0], cohort)
        batch = pick_chunks(documents, processed, budget)
        if not batch:
            report.notes.append("masking: there are no new chunks")

        for index, (doc, chunk) in enumerate(batch, start=1):
            if called_off() or filled():
                break
            report.units_seen += 1
            if on_unit is not None:
                on_unit("masking", index, len(batch), report.pairs_made)
            whole = document_text(doc)

            by_key, path, error = _extractive_for_chunk(
                doc, chunk, extractive, conf, provider
            )
            if error:
                report.failures += 1
                logger.warning(f"{space.key}/{chunk.chunk_id}: {error}")
                continue

            for key, masked in by_key.items():
                good, bad = _masked_to_pairs(masked, whole)
                if bad:
                    report.notes.append(f"{key} {chunk.chunk_id[:10]}: {reasons(bad)}")
                _store(
                    space,
                    doc,
                    chunk.chunk_id,
                    chunk.text,
                    good,
                    GENERATORS[key],
                    f"{path}:{conf.generator_model}",
                    name,
                    report,
                    conf=conf,
                    cohort=cohort,
                    job=job,
                    cap=per_generator,
                )
            _mark_processed(
                space.key,
                extractive[0],
                chunk.chunk_id,
                "chunk",
                sum(len(v) for v in by_key.values()),
                cohort,
            )

    # The rest have a queue OF THEIR OWN each. A shared batch would mean that a
    # generator plugged in second skips everything the first has already
    # parsed, and spends model calls on certain duplicates.
    for spec in per_chunk:
        if called_off() or filled():
            break
        processed = _processed_ids(space.key, spec.key, cohort)
        batch = pick_chunks(documents, processed, budget)
        if not batch:
            report.notes.append(f"{spec.key}: there are no new chunks")
            continue

        for index, (doc, chunk) in enumerate(batch, start=1):
            if called_off() or filled():
                break
            report.units_seen += 1
            if on_unit is not None:
                on_unit(spec.key, index, len(batch), report.pairs_made)
            whole = document_text(doc)

            items, error = _run_llm_generator(spec, doc, chunk, conf, provider)
            if error:
                report.failures += 1
                report.failure_sample = report.failure_sample or f"{spec.key}: {error}"
                logger.warning(f"{space.key}/{spec.key}: {error}")
                continue

            good, bad = spec.clean(items, conf.pairs_per_chunk, whole)
            if bad:
                report.notes.append(f"{spec.key} {chunk.chunk_id[:10]}: {reasons(bad)}")
            _store(
                space,
                doc,
                chunk.chunk_id,
                chunk.text,
                good,
                spec,
                conf.generator_model,
                name,
                report,
                conf=conf,
                cohort=cohort,
                job=job,
                cap=per_generator,
            )
            _mark_processed(
                space.key, spec.key, chunk.chunk_id, "chunk", len(good), cohort
            )

    # --- by document ------------------------------------------------------
    for spec in per_document:
        if called_off() or filled():
            break
        processed = _processed_ids(space.key, spec.key, cohort)
        pending = [d for d in documents if d.doc_id not in processed][:budget]
        if not pending:
            report.notes.append(f"{spec.key}: there are no new documents")
            continue

        for index, doc in enumerate(pending, start=1):
            if called_off() or filled():
                break
            report.units_seen += 1
            if on_unit is not None:
                on_unit(spec.key, index, len(pending), report.pairs_made)
            whole = document_text(doc)
            items, error = _run_llm_generator(spec, doc, None, conf, provider)
            if error:
                report.failures += 1
                report.failure_sample = report.failure_sample or f"{spec.key}: {error}"
                logger.warning(f"{space.key}/{spec.key}: {error}")
                continue
            good, bad = spec.clean(items, conf.pairs_per_chunk, whole)
            if bad:
                report.notes.append(f"{spec.key} {doc.title[:24]}: {reasons(bad)}")
            _store(
                space,
                doc,
                f"doc:{doc.doc_id}",
                whole,
                good,
                spec,
                conf.generator_model,
                name,
                report,
                conf=conf,
                cohort=cohort,
                job=job,
                cap=per_generator,
            )
            _mark_processed(
                space.key, spec.key, doc.doc_id, "document", len(good), cohort
            )

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

    Returns:
        What was screened, and what became of the window/cohort/cap once it
        joined the active pairs. ``rotation`` stays None when nothing was
        screened active: an empty pass has nothing new to reconcile, and
        reading the index for it would be a round trip spent confirming
        nothing changed.
    """
    conf = settings or get_settings()
    report = filter_pending(
        space,
        generator=generator,
        cohort=cohort,
        limit=limit,
        settings=conf,
        retrieve=retrieve,
        should_stop=should_stop,
    )
    if not report.checked or not report.active:
        return report

    client = ChromaClient(space, conf)
    name = collection or space.collection or space.key
    collection_id = client.collection_id(name)
    dated = (
        {doc.doc_id: doc.dated_at for doc in load_documents(client, collection_id)}
        if collection_id is not None
        else {}
    )
    report.rotation = rotate(
        space.key,
        dated,
        cohort=cohort or cohorts.current(space.key, conf),
        settings=conf,
    )
    report.notes += report.rotation.notes
    return report
