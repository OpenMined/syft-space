"""The storage schema of the benchmark.

Two columns carry the construction: ``runs.context_mode`` — without it the arms
are indistinguishable, and the whole construction rests on comparing them; and
``qa_pairs.status`` — the result of gold-answer screening.

Time is ``timestamptz``, structures are ``jsonb``.

The database holds corpus text and is protected like the corpus: see
docs/privacy.md, section 3.
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

    # One pool of questions built in a single pass, so a set can be rebuilt over
    # the same material and compared (``DatasetMode.REBUILD``). Empty — the
    # default pool.
    cohort: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True
    )

    # Which launch built this pair. `cohort` cannot say: an incremental launch
    # adds to the pool that is already there. NULL — written by the CLI, or by
    # no launch anyone can name.
    job_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        default=None,
        comment="The launch that generated this pair; NULL — none it can name",
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

    # What counts as the correct behaviour on this question (``ExpectedBehavior``).
    expected_behavior: Mapped[str] = mapped_column(
        String(20), nullable=False, default="answer", index=True
    )

    # Screening. A pair takes part in runs only with the active status: a bad gold
    # answer understates a good endpoint score, and the metrics do not show it.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    status_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Machine code of why the pair is not active (``StatusReason``); NULL while
    # it is pending or active.
    status_reason: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )

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
        # Every read of a launch's questions carries the status band too.
        Index("qa_pairs_job", "space", "job_id", "status"),
    )


class ProcessedUnit(Base):
    """What has already been processed — so the daily cycle does not start from zero.

    The key includes the generator: generators read the same text differently,
    and a chunk one has processed must still reach the others.

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

    # Which launch this run belongs to; NULL — started from the console. No
    # foreign key, for the reason ``jobs`` has none on ``targets``: a cascade
    # must not carry off the history of what was measured.
    job_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None, index=True
    )

    # The measurement arm (``ContextMode``). Only identical arms can be compared
    # with one another.
    context_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # What exactly was mixed in with the question: the chunks, the endpoint finished
    # answer, the source chunk (the ceiling). Without this field arm C is
    # uninterpretable — "a model on raw data" and "a model handed someone else
    # conclusion" measure different things and give different numbers.
    context_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none"
    )

    # The methodology profile and the settings snapshot the run was obtained with:
    # the thresholds, prompts and retrieval parameters are configurable, and the
    # report must not add runs with different similarity thresholds into one share.
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
    # rather than read from the endpoint later, because the mode can be switched
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

    # Whether the answer follows from the retrieval it was given; NULL in the
    # arms that are given none.
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

    Targets are edited from the UI, so they live in a table: a file has nobody
    to re-read it in a running process, no history, and two simultaneous saves
    wipe each other out.

    ``config/spaces.json`` is a seed: a target that is not in the table is
    taken from it, so an installation configured by the file works knowing
    nothing about any UI.

    ``instrument`` and ``probe`` are **overrides**, not a full set of settings: only
    what the owner actually set. The defaults stay with the installation, and an
    updated default reaches every target by itself.
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

    # A schedule of the form 24h/90m, and for a daily one the hour it lands on,
    # read by the ticker inside the service. The hour is UTC: a container does
    # not know the owner's time zone.
    schedule: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    schedule_at: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="",
        comment="The launch time HH:MM in UTC, if set",
    )

    # When the ticker will next look at this target. Stored rather than recomputed
    # each tick: a computed moment has no memory of having fired, and a schedule
    # saved for the first time would fire at once.
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
    from the press of a button to its last verdict.

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

    # What operation this job is (``JobKind``).
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pipeline",
        index=True,
        comment="What operation this job is: pipeline (measure(), any "
        "combination of generate/filter/evaluate), filter, or judge",
    )

    # The progress of the measurement. The full volume is not known at once — it comes
    # to light after the items are selected — so a zero in total means "we do not know
    # yet" rather than "there is nothing to do", and until then there is nothing to
    # draw a bar with.
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # The pass running now, as fields so the UI can render them in its own
    # language. step_done/step_total count questions within the pass;
    # done/total count passes.
    arm: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    block: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    step_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # The snapshot of the settings the job was launched with. The configuration gets
    # changed between launches, and without a snapshot there is nothing to explain
    # yesterday figures with. Besides the request it holds what ``job_params``
    # records: the judging the job ran with (``judge_panel``, ``judge_policy``),
    # the article window and, once fixed, ``primary_judge`` — see
    # ``counted.primary_judge``.
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

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


class RunAggregate(Base):
    """The cached figures of one run; no row means they are to be recomputed."""

    __tablename__ = "run_aggregates"

    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WriterCall(Base):
    """A writer call of a job that threw drafts away or failed: one row per call.

    Pairs keep the calls that wrote them (``meta.writer``); what a call wrote
    and the build dropped has no pair to sit on. No foreign key, as for
    ``qa_pairs.job_id``; ``discard_run`` deletes the rows with their job.

    ``system`` is stored on the first row of a build with that prompt and is
    empty on the rest; ``system_digest`` finds it.
    """

    __tablename__ = "writer_calls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    call: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    document_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    passage: Mapped[str] = mapped_column(Text, nullable=False, default="")
    system: Mapped[str] = mapped_column(Text, nullable=False, default="")
    system_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # The passage replaced by ``recorded.PASSAGE_MARK``.
    user: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reply: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {kind: [{question, answer, reason}]}, the reason as in the kind's
    # ``dropped``: every kind the call dropped from, or was asked for when it
    # failed (with no drafts).
    dropped: Mapped[dict[str, list[dict[str, Any]]]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("writer_calls_job", "job_id", "created_at"),
        Index("writer_calls_system", "job_id", "system_digest"),
        Index("writer_calls_call", "job_id", "call", unique=True),
    )


class InstallationSettings(Base):
    """The installation's own settings — the bottom of the three layers.

    **A sparse set of overrides, exactly like ``instrument`` and ``probe``**,
    rather than a column per field. An unset field means "take the built-in
    default", and for several fields the empty value is itself a decision —
    ``disabled_generators: []`` means "disable none", which nullable columns
    cannot tell from never having been touched. A new setting costs no
    migration.

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
    source: Mapped[str] = mapped_column(
        String(40),
        primary_key=True,
        comment="The provider this catalogue came from. There is exactly one "
        "current catalogue per provider, and a refresh replaces it",
    )

    document: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="The catalogue itself: the entries and the pins that resolve "
        "moving names such as a vendor's -latest",
    )

    # Out of the document, so its age and size are answerable without loading
    # two hundred kilobytes of JSON.
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When it was last fetched. Shown beside the picker: a "
        "catalogue whose age is invisible is one nobody thinks to refresh",
    )
    model_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Denormalised out of the document so that how old this is and "
        "how much is in it can be answered without loading all of it",
    )
