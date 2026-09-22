"""The storage schema of the benchmark.

A port of the SQLite prototype (`OMSyft/scripts/qa_store.py`) to Postgres with two
substantial additions: ``runs.context_mode`` — without it runs A and B are
indistinguishable, and the whole construction rests on comparing them; and
``qa_pairs.status`` — the result of gold-answer screening.

The types are brought to native ones: time as ``timestamptz``, structures as
``jsonb``. In SQLite both had to be kept as strings.

An important point about sensitivity: ``qa_pairs.answer`` not infrequently quotes
the source verbatim, ``results.retrieved`` stores the chunks that were found, and
``results.audit`` whole prompts, including the context mixed in in arm C. This
database is a third copy of the corpus after the Space files and ChromaDB, and it
has to be protected the same way.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """The common ancestor of the tables."""


class QaPair(Base):
    """A (question, gold answer) pair generated from one chunk.

    It lives longer than any run: the question is asked many times, of different
    models and in different modes, while the results accumulate separately.
    """

    __tablename__ = "qa_pairs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    space: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    collection: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # A cohort is one pool of questions built in a single pass. It is needed so that
    # a set can be built afresh over ONE AND THE SAME material — with a different
    # model, a different prompt — and compared. If the material is the same and the
    # metrics diverged, it is not about the model under test but about the quality of
    # the questions and the gold answers: without a cohort that question cannot even
    # be asked.
    #
    # An empty string — a set built before cohorts existed.
    cohort: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True
    )

    generator: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Item type: masking, MCQ and so on"
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    # Provenance. Needed both for incrementality and for screening: a gold answer can
    # only be checked against the chunk it was taken from.
    doc_id: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    chunk_id: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    document_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_name: Mapped[str] = mapped_column(Text, nullable=False, default="")

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    distractors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # What counts as the correct behaviour on this question: to answer, to abstain
    # (there is no answer in the corpus) or to refute a false premise. The field sits
    # on the pair, not on the run: there is one set and three arms, and the correct
    # behaviour is determined by the question, not by who answers it.
    expected_behavior: Mapped[str] = mapped_column(
        String(20), nullable=False, default="answer", index=True
    )

    # Screening. A pair takes part in runs only with the active status: a bad gold
    # answer understates a good endpoint score, and the metrics do not show it.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    status_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    model: Mapped[str] = mapped_column(String(120), nullable=False)
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    results: Mapped[list[Result]] = relationship(back_populates="pair")

    __table_args__ = (
        # Protection from duplicates between daily cycles: one and the same question
        # from one generator over one Space is created once — WITHIN A COHORT.
        # Between cohorts a repeat is legitimate and meaningful: it means the
        # generator produced the same question from the same material, that is, it is
        # stable. Forbidding such a repeat would make rebuilding the set impossible —
        # the second pass would be rejected wholesale.
        UniqueConstraint(
            "space", "generator", "question_hash", "cohort", name="qa_pairs_unique"
        ),
        Index("qa_pairs_chunk", "space", "chunk_id"),
        Index("qa_pairs_cohort", "space", "cohort", "status"),
    )


class ProcessedUnit(Base):
    """What has already been processed — so the daily cycle does not start from zero.

    The key includes the generator, and that is mandatory: there are eight
    generators, they see one and the same text differently, and a chunk processed by
    masking is obliged to reach MCQ as well. Without the generator in the key the
    second generator would silently skip everything the first got through.

    The unit of processing depends on the generator scope: for most it is a chunk,
    for multihop and tiered the whole document, because you cannot connect two facts
    or lay out the core of a topic from a single paragraph.

    The cohort is in the key for the same reason as the generator: rebuilding the set
    is a fresh pass over THE SAME material, and the previous cohort mark must not
    stop it. Clearing the table is not needed for that: the new cohort simply has no
    marks.
    """

    __tablename__ = "processed_units"

    space: Mapped[str] = mapped_column(String(64), primary_key=True)
    generator: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    cohort: Mapped[str] = mapped_column(String(32), primary_key=True, default="")

    unit_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="chunk", comment="chunk | document"
    )
    pairs_made: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Run(Base):
    """One run: what was asked with, what was tested and in which mode."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    space: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    # Which launch this run was born of — what makes the report and the audit of
    # ONE measurement possible; without it a job and its runs share only a target
    # and a span of time.
    #
    # NULL is not a gap: a run started from the console belongs to no job and
    # never will. No foreign key, for the reason ``jobs`` has none on ``targets``
    # — a cascade must not carry off the history of what was measured.
    job_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None, index=True
    )

    # The main field of the table — the measurement arm. closed_book (A) — the
    # question went to the model without a single corpus chunk; open_book (B) — the
    # whole endpoint answered; model_with_context (C) — the same model as in A
    # answered, but with the endpoint retrieval in the prompt. Only identical arms
    # can be compared with one another.
    context_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # What exactly was mixed in with the question: the chunks, the endpoint finished
    # answer, the source chunk (the ceiling). Without this field arm C is
    # uninterpretable — "a model on raw data" and "a model handed someone else
    # conclusion" measure different things and give different numbers.
    context_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none"
    )

    # The methodology profile and the settings snapshot the run was obtained with. As
    # soon as the thresholds, prompts and retrieval parameters became configurable,
    # the report became obliged to know how a row was obtained: otherwise it will
    # silently add runs with different similarity thresholds into one share.
    profile: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default", index=True
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # The test block: direct, denial_loop, monte_carlo. In the report the figures of
    # different blocks are not mixed — they answer different questions, and a Monte
    # Carlo "accuracy" is an average over the repeats, not the same number as direct.
    block: Mapped[str] = mapped_column(
        String(20), nullable=False, default="direct", index=True
    )

    model: Mapped[str] = mapped_column(String(120), nullable=False)
    model_vendor: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="",
        comment="The provider of the model under test",
    )

    # What was actually served, as against what was asked for. Not part of
    # ``params``: that snapshot is compared for exact equality to decide whether
    # yesterday's answers may be reused, and a build moves on its own.
    model_sent_as: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="",
        comment="The name the provider was actually given, when it differs from "
        "the identifier this service uses",
    )
    model_provider: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="",
        comment="Whose API answered: openrouter, anthropic, ollama",
    )
    model_build: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="",
        comment="The dated build behind the name on the day of the run. A vendor "
        "refreshes what a name serves; without this, two runs under one name "
        "look comparable when they are not",
    )

    judge_model: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    results: Mapped[list[Result]] = relationship(back_populates="run")


class Result(Base):
    """The verdict on one question in one run."""

    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    qa_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("qa_pairs.id", ondelete="CASCADE"), nullable=False
    )

    space: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    # The endpoint mode at run time: raw / summary / both. Written beside the answer
    # rather than taken from the card when reading, because the mode can be switched
    # and an old verdict relates to the previous one.
    endpoint_response_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=""
    )

    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # The judge sentence: correct / abstain / hallucinate. This is the BEHAVIOUR of
    # the answerer rather than an assessment of its correctness: on a question whose
    # answer is not in the corpus, an abstention is recorded as abstain, and it is the
    # metrics that know it is the correct behaviour here. That way a change of
    # methodology does not require a re-run: the interpretation lives in the report,
    # not in the stored verdict.
    verdict: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # What counted as the correct behaviour on this question at run time. A copy of
    # the pair field rather than a read through the reference: the control set
    # labelling gets refined, and an old verdict relates to the previous one.
    expected_behavior: Mapped[str] = mapped_column(
        String(20), nullable=False, default="answer", index=True
    )

    # Grounding — only for open_book: does the answer follow from what was found, or
    # did the model add something of its own. For closed_book it is meaningless and
    # stays NULL.
    grounded: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    grounded_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # The retrieval metrics. For raw mode they are the measurement itself: no model
    # takes part, and "the accuracy of the answer" means whether the gold answer
    # landed in the retrieval and in which position.
    retrieval_hit: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=None
    )
    retrieval_rank: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    retrieved: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # The block result: the round number at which the model gave in, the consistency
    # across temperatures and whatever else each block has of its own. As separate
    # columns this would give a table where every row has a different third filled in.
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # The audit trail: what exactly was asked and how the judge justified the verdict.
    #
    # The benchmark number is a judge model verdict, and it cannot be checked by
    # anything except the raw records. Here lie the answerer system and user prompts
    # (for arm C together with the chunks mixed in), the judge prompt and its raw
    # answer. Assembling this after the fact is impossible: a prompt depends on the
    # settings of the moment, and those change.
    #
    # SENSITIVE: the arm C prompt contains the text of the chunks that were found.
    audit: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    latency_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    # Who served this one answer and this one verdict. Per answer, because a
    # router picks an upstream per request: correlating a verdict with an
    # upstream needs them on one row. Empty where nothing was routed — a local
    # model, the endpoint arms, a verdict reached without calling a judge.
    served_by: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="The upstream that served the answer, when the provider is a "
        "router rather than the model's owner",
    )
    judge_model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    judge_served_by: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="The upstream that served the verdict. Kept apart from the "
        "answer's: when a number moves, it is the first thing to rule out",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[Run] = relationship(back_populates="results")
    pair: Mapped[QaPair] = relationship(back_populates="results")

    __table_args__ = (
        # The metrics are computed over the latest verdict per question, so the
        # selection always goes "by question, by descending time".
        Index("results_qa_recent", "space", "qa_id", "created_at"),
        Index("results_run", "run_id"),
    )


class Target(Base):
    """A node under test: where to go and with what settings to measure.

    Before the UI existed the list of nodes lived in ``config/spaces.json``, and that
    was enough while it was edited by the same person who launched the run. As soon
    as targets are created by an owner from a UI, the file stops being fit: there is
    nobody to re-read it in a running process, it has no history, and two
    simultaneous saves wipe each other out.

    The file has not gone anywhere and remains a seed: a target that is not in the
    table is taken from it. That way an installation configured by the file keeps
    working, knowing nothing about any UI.

    ``instrument`` and ``probe`` are **overrides**, not a full set of settings: only
    what the owner actually set. The defaults stay with the installation, and an
    updated default reaches every target by itself. Keeping a full snapshot here
    would mean freezing it forever on the day the target was created.
    """

    __tablename__ = "targets"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # Where to go. The Space address and the endpoint slug together, because one Space
    # serves many endpoints and it is always a specific one that gets measured.
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    # The Space's token is NOT here: it speaks for the owner, and a plain text
    # column is in every dump and backup. It is sealed in ``credentials``, under
    # ``target:<key>``.

    # Access to the index. The questions are built from the corpus, and without it a
    # target is fit only for the control half of the set.
    container: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    chroma_host: Mapped[str] = mapped_column(
        String(200), nullable=False, default="localhost"
    )
    chroma_port: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collection: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
        comment="The collection name in the index; empty — the target key is used",
    )

    instrument: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Override for the what-we-measure-with layer",
    )
    probe: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Override for the how-we-ask layer",
    )

    # A disabled target keeps all its configuration and history: the owner pauses a
    # measurement rather than creating it again a week later.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # A schedule of the form 24h/90m, and for a daily one the hour of the night it
    # should land on. Read by the ticker inside the service: setting it here is
    # what makes a measurement happen without anybody pressing anything.
    #
    # The hour is UTC, and that is deliberate rather than a leftover. A container
    # has no idea what the owner's night is, and a service that guessed at it from
    # its own clock would shift every schedule the day the host was moved.
    schedule: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    schedule_at: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="",
        comment="The launch time HH:MM in UTC, if set",
    )

    # When the ticker will next look at this target. Stored rather than recomputed
    # each tick, for two reasons that both showed up on the rig: a computed moment
    # has no memory of having fired, so a 24h schedule would start a measurement
    # on every tick of the hour it was due in; and a schedule saved for the first
    # time would fire at once, though "every 24h at 03:00" means tonight.
    #
    # NULL — the moment is not worked out yet, and the ticker plans without
    # measuring. A moment in the past — the service was down over the window.
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Job(Base):
    """One launch of a measurement as it is seen from outside: state and progress.

    The ``runs`` table is not fit for this and must not be: its row is "arm x block x
    model", there are dozens of them per measurement, and not one of them answers the
    owner question "is my launch still going?". A job stands a layer above and lives
    from the press of a button to the last published card.

    There is deliberately no reference to ``targets``: a target gets deleted, the
    history of measurements does not. A cascade would carry off the answer to "what
    was ever done with this endpoint".
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", index=True
    )
    phase: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # The progress of the measurement. The full volume is not known at once — it comes
    # to light after the items are selected — so a zero in total means "we do not know
    # yet" rather than "there is nothing to do", and until then there is nothing to
    # draw a bar with.
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # What is going on right now, as fields rather than as a string. A string of the
    # form "space/closed_book/direct [model] — 43/120" is read only by someone who
    # knows how it is built, and in another language it is not displayed at all;
    # besides, "43 of 120" is questions within a run, while done/total is runs, and
    # two different counts merged into one phrase get confused with each other.
    arm: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    block: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    step_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # The snapshot of the settings the job was launched with. The configuration gets
    # changed between launches, and without a snapshot there is nothing to explain
    # yesterday figures with.
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    # The card assembled right after measuring, in the shape the Space accepts
    # it in — set regardless of whether ``request.publish`` was ticked or the
    # Space took it: "how did this run go" is answered from here, not from
    # whether the card ever left the perimeter.
    card: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )

    # Stopping is a request, not a kill: the run finishes writing the current question
    # and exits by itself, leaving the database intact.
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class InstallationSettings(Base):
    """The installation's own settings — the layer under the instrument.

    The bottom of the three settings layers. The other two are rows here
    already; this one sat in the environment, which meant a settings file of
    three hundred lines on the host and no way to change a default without
    going to that host.

    **A sparse set of overrides, exactly like ``instrument`` and ``probe``**,
    rather than sixty-five columns. An unset field means "take the built-in
    default", and for several fields the empty value is itself a decision —
    ``disabled_generators: []`` means "disable none", which nullable columns
    cannot tell from never having been touched. And ``/schema`` exists so that
    a new field costs no migration in the Space; one that cost a migration here
    would give half of that back.

    What is NOT here is in ``BOOTSTRAP_FIELDS``: what the process must read
    before it can read this row, and the perimeter.

    One row, and the constraint says so rather than the convention.
    """

    __tablename__ = "installation_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="installation_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Credential(Base):
    """One secret, sealed.

    Deliberately not a field in the settings JSONB: those are read on every
    launch, copied into a job's snapshot and every run's params, handed out by
    ``/defaults`` and written to the log, and a provider key would travel to all
    of those places.

    The value is never handed out again. What can be asked is whether there is
    one and when it was set. See ``db/crypto.py`` for what sealing protects.
    """

    __tablename__ = "credentials"

    # The slot, not a surrogate id. It is also the associated data the ciphertext
    # is bound to, so a row cannot be moved from one slot to another — renaming a
    # credential is therefore setting a new one.
    name: Mapped[str] = mapped_column(String(120), primary_key=True)

    secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # The key that sealed this row. Without it, rotation would be guesswork about
    # which rows had already been done.
    key_id: Mapped[str] = mapped_column(String(32), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelCatalog(Base):
    """One provider's model list, as a refresh last saw it.

    A whole document per source: the list is read whole and written whole, so
    rows per model would buy joins nobody performs and cost a migration every
    time the provider adds a field.

    The shipped snapshot in ``syft_benchmark/data`` sits underneath this table,
    which is what lets a rig with no way out of the perimeter still draw a form
    with models in it.
    """

    __tablename__ = "model_catalog"

    # The source, not a surrogate id: one current catalogue per provider.
    source: Mapped[str] = mapped_column(String(40), primary_key=True)

    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Out of the document, so its age and size are answerable without loading
    # two hundred kilobytes of JSON.
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    model_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
