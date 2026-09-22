"""The benchmark settings.

Two sources: environment variables (addresses, models, secrets) and a file with
the list of Spaces. The split is not cosmetic — there can be many Spaces and they
are described by a structure, and passing a structure through flat environment
variables is inconvenient; everything else, on the contrary, naturally lives in
the environment and in .env.

The ban on external calls (invariant 2 of the spec) lives here too. It is
implemented as a check rather than an agreement: the questions are generated from
private documents, and the only reliable way not to send them outside is to have
no code that can do it, except through an explicitly allowed list of hosts.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ContextMode(StrEnum):
    """The measurement arm: who answers and what they have in front of them.

    Without this field the arms are indistinguishable in the database, and the
    whole construction rests on comparing them with one another.

    The three arms measure three different things, and they must not be added up:

      * **A** — the model alone. The model honesty; a correct answer means not
        quality but that the corpus is already known to it (or that it guessed).
      * **B** — the whole endpoint: its retrieval, its model, its system prompt.
        This is an assessment of the owner product.
      * **C** — the same model as in A, plus what the endpoint returned. This is
        the model interaction with RAG: A and C differ by exactly the presence of
        context, so their difference is interpretable.

    The value ``open_book`` is historical: that is what arm B was called when
    there were two arms. It must not be renamed — results already collected are
    marked with it.
    """

    CLOSED_BOOK = "closed_book"  # arm A: the question without a single corpus chunk
    OPEN_BOOK = "open_book"  # arm B: the question to the endpoint, it answers
    MODEL_WITH_CONTEXT = "model_with_context"  # arm C: the same model + the retrieval


# The arm letter for reports. Reading "closed_book vs model_with_context" in a
# table is hard, while "A vs C" is exactly the language the methodology is
# described in.
ARM_LETTER: dict[str, str] = {
    ContextMode.CLOSED_BOOK.value: "A",
    ContextMode.OPEN_BOOK.value: "B",
    ContextMode.MODEL_WITH_CONTEXT.value: "C",
}


class ContextSource(StrEnum):
    """What exactly is mixed in with the question in arm C.

    Distinguishing them is mandatory: the chunks and the endpoint finished answer
    measure different things. Over chunks, what is tested is whether the model can
    work with raw data — not fill in what is missing, not substitute a neighbouring
    fact. Over a finished answer, the model credulity towards a foreign conclusion:
    will it repeat someone else invention. Mixing these numbers into one share
    means getting a quantity about nothing.
    """

    NONE = "none"  # arm A: there is no context at all
    ENDPOINT_FRAGMENTS = "endpoint_fragments"  # the chunks that were found
    ENDPOINT_ANSWER = "endpoint_answer"  # the endpoint finished answer
    ENDPOINT_BOTH = "endpoint_both"  # both, as the endpoint handed them over
    ORACLE_CHUNK = "oracle_chunk"  # the source chunk: the ceiling, no retrieval
    ENDPOINT_OWN = "endpoint_own"  # arm B: the endpoint assembled the context itself


class ExpectedBehavior(StrEnum):
    """What counts as the correct behaviour on this question.

    Before the control set existed, every question was answerable by construction
    — they are generated from chunks — and the benchmark measured half the
    behaviour: what the pair does when there is NO answer in the corpus was not
    measured at all. Meanwhile that is the most frequent question a live user asks.

    The field sits on the pair, not on the run: there is one set and three arms,
    and the correct behaviour is determined by the question, not by who answers it.
    """

    ANSWER = "answer"  # there is an answer in the corpus — answering is right
    ABSTAIN = "abstain"  # there is no answer in the corpus — abstaining is right
    CORRECT_PREMISE = "correct_premise"  # the premise is false — refuting it is right


# What the correct behaviour is called in the report. The control half of the set
# is not homogeneous: on a question without an answer the right thing is to stay
# silent, and on a question with a false premise to refute it. Without a label the
# rows read as duplicates.
BEHAVIOUR_LABEL: dict[str, str] = {
    ExpectedBehavior.ANSWER.value: "answer",
    ExpectedBehavior.ABSTAIN.value: "abstain",
    ExpectedBehavior.CORRECT_PREMISE.value: "refute the premise",
}


class Verdict(StrEnum):
    """The three outcomes a judge reduces any answer to, and one expectation.

    ``PENDING`` is not an outcome and takes no part in the shares: it is an answer
    that was received but not yet judged. The state exists for the sake of deferred
    judging — the answers are collected by machine and the verdicts are issued by a
    console judge later — and so that such an answer is visible. Without it an
    answer with no verdict would have to be either thrown away or recorded as an
    outcome nobody issued.
    """

    CORRECT = "correct"
    ABSTAIN = "abstain"
    HALLUCINATE = "hallucinate"
    PENDING = "pending"


class TextMetric(StrEnum):
    """A mechanical measure of an answer resemblance to the gold one.

    The verdict is issued by a judge, that is, by a model, and there is nothing to
    check it with except another opinion. These metrics are computed mechanically
    and therefore work as a second, independent view: if the verdict and the
    textual match diverge, that is grounds for a look with your own eyes.

    They do not know correctness and cannot: what is measured is word overlap. So
    they enter no share of the report and are not published.
    """

    BLEU = "bleu"  # n-gram overlap with a brevity penalty
    ROUGE = "rouge"  # ROUGE-1/2 and ROUGE-L by F1
    BERTSCORE = "bertscore"  # embedding similarity; needs the bert-score package


class EvalBlock(StrEnum):
    """The test block. A port of the LiveTruth phase-3 blocks.

    The blocks are independent and switched on separately: `direct` is cheap and
    mandatory in meaning, while the other two cost several times as much —
    denial_loop makes K extra rounds per correct answer, monte_carlo multiplies the
    question by the number of temperatures and trials.
    """

    DIRECT = "direct"  # one question, one answer — baseline accuracy
    DENIAL_LOOP = "denial_loop"  # pressure on a correct answer: will it give in
    MONTE_CARLO = "monte_carlo"  # repeats at different temperatures: stability


class JudgePolicy(StrEnum):
    """How strictly to require the judge independence from the model under test.

    A judge and a model under test from one provider is a conflict of interest: a
    model tends to approve its own style of answer. It cannot be ruled out entirely
    (a local model has no provider at all), so the policy is configurable.

    ``RECUSE`` is the working choice for a panel: the judge does not judge "its
    own", but the run carries on with the other judges. ``STRICT`` is appropriate
    with a single judge, when there is nothing to carry on with and stopping is
    better.
    """

    OFF = "off"  # do not check
    WARN = "warn"  # warn and carry on
    RECUSE = "recuse"  # the judge recuses itself, those answers stay unassessed
    STRICT = "strict"  # refuse the run


class PairStatus(StrEnum):
    """The state of a (question, gold answer) pair.

    Screened-out ones are not deleted: they are material for tuning the generator
    prompts, not rubbish.

    ``RETIRED`` is not a screening either: the item is fit, the document it grew
    from has simply left the freshness window. Such an item stops taking part in
    the measurement and may come back if the document lands in the window again. It
    must on no account be deleted: it carries the verdicts of every previous run,
    and the cascade would take the measurement history away with the question.
    """

    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    RETIRED = "retired"


class JobState(StrEnum):
    """The state of a job launched from outside.

    Created for the sake of a button in the UI: launching a measurement takes
    hours, an HTTP response cannot wait that long, and the owner needs something to
    look at while the run goes on.

    ``QUEUED`` is separated from ``RUNNING`` not for elegance: a measurement costs
    money and takes up the node entirely, so one job at a time is allowed per node
    and the rest wait. Without a separate "waiting" state a queue is
    indistinguishable from a hung run.

    ``CANCELLED`` means stopped by the owner, and that is not an error: half a
    measurement is data too, and its runs and verdicts are already written and stay
    in the database.
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def final(self) -> bool:
        """The job has finished counting and will not move again."""
        return self in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}


class JobPhase(StrEnum):
    """Where the job is now. Shown to the owner rather than computed.

    The phases differ in length and in cost, and an owner who sees "running" cannot
    tell a ten-minute generation from a multi-hour polling of nine models.
    """

    PENDING = "pending"
    GENERATE = "generate"
    EVALUATE = "evaluate"
    REPORT = "report"
    PUBLISH = "publish"
    DONE = "done"


class DatasetMode(StrEnum):
    """Where the items in the next generation run come from.

    Three modes answer three different questions, and they must not be confused.

    ``INCREMENTAL`` — **what new has appeared in the corpus.** The set accumulates:
    new material adds items, and the earlier ones stay in the measurement forever.
    That is how a stable corpus is measured, where a correct answer does not go out
    of date: documentation, a reference, a knowledge base.

    ``ROLLING`` — **what is current now.** The set moves with time: in the
    measurement is what grew out of documents from the last N days. What leaves the
    window leaves the set, and what returns comes back — and comes back for free,
    with the same items. That is how a live stream is measured, where the interest
    is precisely in what is fresh.

    ``REBUILD`` — **are the questions themselves any good.** The material is the
    same, while the pool of questions is built afresh, as a separate cohort: with a
    different generator model, a different prompt, simply a different pass. The
    material is one and the metrics diverged — which means it is not about the
    model under test but about the quality of the questions and gold answers. That
    can only be answered by comparing cohorts, and the mode exists for it.

    Note how REBUILD differs from ROLLING in cost: a rolling set reuses ready-made
    items and calls the generator only for new material, whereas a rebuild pays for
    the whole set again. So it is not scheduled for every night.
    """

    INCREMENTAL = "incremental"
    ROLLING = "rolling"
    REBUILD = "rebuild"


class SpaceConfig(BaseModel):
    """One node under test: its API and its own ChromaDB."""

    key: str = Field(..., description="A short name, also the name in the CLI")
    title: str = Field(default="", description="A human name for reports")
    url: str = Field(..., description="The base address of the Space API")
    endpoint: str = Field(..., description="The slug of the endpoint under test")
    token: str | None = Field(
        default=None, description="The Space API access token, if it is closed"
    )
    container: str = Field(
        default="",
        description="The docker container name — the fallback transport to ChromaDB",
    )
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(
        default=0, description="0 — the port is not published, we go via docker exec"
    )
    collection: str = Field(
        default="",
        description=(
            "The collection name in the index. Empty — the node key is used. They "
            "coincide only when the key has been hand-picked to match the index: a "
            "Space names the collection after its own dataset, and a node "
            "configured from the UI is almost certainly named otherwise"
        ),
    )

    # The endpoint retrieval parameters. They are here and not only in the shared
    # settings because the threshold is tuned to the corpus: different values are
    # meaningful on homogeneous documentation and on a mixed archive.
    # None — take the shared value from the process settings.
    retrieval_top_k: int | None = Field(
        default=None, description="How many chunks to ask the endpoint for"
    )
    similarity_threshold: float | None = Field(
        default=None,
        description=(
            "The similarity threshold. Zero means the endpoint will return top-k "
            "for any question, including one whose answer is not in the corpus"
        ),
    )

    @property
    def name(self) -> str:
        return self.title or self.key


class Settings(BaseSettings):
    """The process settings. Read from the environment and .env."""

    model_config = SettingsConfigDict(
        env_prefix="BENCH_", env_file=".env", extra="ignore"
    )

    database_url: str = Field(
        default="postgresql+psycopg://benchmark:benchmark@localhost:5442/benchmark",
        description="The benchmark Postgres",
    )

    ollama_url: str = Field(
        default="http://localhost:11434",
        description=(
            "The base address of an OpenAI-compatible API. A local Ollama by "
            "default; in development mode an external provider can be put here — "
            "see allow_external_models"
        ),
    )
    llm_api_key: str = Field(
        default="",
        description=(
            "The provider key, if it requires one. A local Ollama does not need "
            "it; an external one does, and without a key a call returns 401"
        ),
    )
    llm_app_name: str = Field(
        default="syft-benchmark",
        description="How to introduce ourselves to the provider in the X-Title header",
    )
    generator_model: str = Field(
        default="gemma3-4b-gpu", description="The model that generates the pairs"
    )
    judge_model: str = Field(
        default="gemma3-4b-gpu", description="The judge; the same one for both runs"
    )
    judge_models: list[str] = Field(
        default_factory=list,
        description=(
            "The panel of judges: the assessment is run once per judge. Empty — "
            "a single judge_model judges"
        ),
    )

    # --- The model roles
    #
    # Three roles, each with its own provider. The split is no formality: the
    # generator works over documents and should normally stay inside the
    # perimeter, the models under test do not see documents and are almost always
    # external, and the judge must not be from the same provider as the model
    # under test.
    #
    # An empty address for a role means "take the shared one" — from ollama_url
    # and llm_api_key.
    generator_url: str = Field(default="", description="The generator provider")
    generator_key: str = Field(default="", description="The generator provider key")

    subject_url: str = Field(
        default="", description="The provider of the models under test"
    )
    subject_key: str = Field(default="", description="That provider key")
    subject_models: list[str] = Field(
        default_factory=list,
        description=(
            "The models tested in the run without context. Empty — the generator "
            "model is tested, that is, the local one"
        ),
    )

    judge_url: str = Field(default="", description="The judge provider")
    judge_key: str = Field(default="", description="The judge provider key")
    judge_policy: JudgePolicy = Field(
        default=JudgePolicy.WARN,
        description="Whether the judge must be independent of the model under test",
    )

    # --- The measurement arms. All three by default: they measure different
    # things, and without arm C the model interaction with RAG is not measured.
    arms: list[ContextMode] = Field(
        default_factory=lambda: [
            ContextMode.CLOSED_BOOK,
            ContextMode.OPEN_BOOK,
            ContextMode.MODEL_WITH_CONTEXT,
        ],
        description="Which arms to run when no arm is named explicitly",
    )
    context_source: ContextSource = Field(
        default=ContextSource.ENDPOINT_FRAGMENTS,
        description=(
            "What to mix in with the question in arm C. Chunks are the main path: "
            "what is tested is the model work with data, not its trust in a "
            "foreign conclusion"
        ),
    )
    context_docs: int = Field(
        default=3,
        ge=1,
        le=20,
        description="How many top chunks found to put into the arm C prompt",
    )

    # --- The parameters of the request to the endpoint.
    #
    # The similarity threshold is an axis of the measurement, not a constant. At
    # zero the endpoint is obliged to return top-k for any question, including one
    # whose answer is not in the corpus, and it is physically unable to stay
    # silent. Zero is left as the default so that earlier runs stay comparable, but
    # on the control set it makes sense to run several values and see where the
    # inventions stop appearing.
    retrieval_top_k: int = Field(
        default=5, ge=1, le=50, description="How many chunks to ask the endpoint for"
    )
    similarity_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="The similarity threshold in retrieval"
    )
    endpoint_max_tokens: int = Field(
        default=500, ge=1, description="The ceiling on the endpoint answer in arm B"
    )
    endpoint_temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, description="The endpoint temperature in arm B"
    )

    # --- The test blocks. All are on by default.
    blocks: list[EvalBlock] = Field(
        default_factory=lambda: [
            EvalBlock.DIRECT,
            EvalBlock.DENIAL_LOOP,
            EvalBlock.MONTE_CARLO,
        ],
        description="Which test blocks to apply",
    )
    denial_rounds: int = Field(
        default=5, ge=1, le=12, description="How many rounds of pressure in denial_loop"
    )
    monte_carlo_temperatures: list[float] = Field(
        default_factory=lambda: [0.1, 0.3, 0.6, 0.9],
        description="The temperatures for monte_carlo",
    )
    monte_carlo_trials: int = Field(
        default=3, ge=1, le=20, description="Trials per temperature"
    )

    # --- Concurrency
    #
    # A run is busy not computing but waiting: almost all its time is an open
    # socket to a model, to a judge or to the endpoint. A sequential walk pays that
    # wait once per call, and on a live set the count runs into days. Here it is
    # set how many waits to keep in flight at once.
    #
    # There are two lanes because the addressees have different capacity. An
    # external model provider holds dozens of requests; the endpoint under test is
    # one node with one model, and a queue to it does not speed it up but only
    # accumulates timeouts. One number for both would mean choosing between an idle
    # provider and a swamped node.
    concurrency: int = Field(
        default=8,
        ge=1,
        le=64,
        description=(
            "How many calls to models to keep in flight at once: the model under "
            "test, the judges, the pressure and repeat blocks"
        ),
    )
    endpoint_concurrency: int = Field(
        default=2,
        ge=1,
        le=32,
        description=(
            "How many requests to keep in flight to the endpoint under test. It "
            "is a foreign node, and its capacity is set by its owner, not by us"
        ),
    )
    # --- the text metrics
    #
    # Off by default, and that is not caution. The headline assessment is the
    # judge verdict; text similarity does not know correctness, enters no share and
    # is not published. It is switched on when a view of the same answers that is
    # independent of the judge is needed.
    text_metrics: list[TextMetric] = Field(
        default_factory=list,
        description=(
            "Mechanical measures of an answer resemblance to the gold one: bleu, "
            "rouge, bertscore. Computed only where the answer is prose"
        ),
    )
    bertscore_model: str = Field(
        default="bert-base-multilingual-cased",
        description=(
            "The model for BERTScore. Multilingual by default: a corpus is not "
            "always English, and an English model on a non-English answer gives a "
            "plausible number about nothing"
        ),
    )

    question_set: Path | None = Field(
        default=None,
        description=(
            'The file of the frozen slice of questions. As long as "which '
            'questions" is decided by selection on the fly, two runs take '
            "different sets, and the difference in numbers means not what was "
            "measured but that the set has grown"
        ),
    )
    strict_question_set: bool = Field(
        default=True,
        description=(
            "A divergence between the set and the slice is a refusal. Switching it "
            "off lowers that to a warning and throws out the diverged items"
        ),
    )
    resume: bool = Field(
        default=False,
        description=(
            "Resume an interrupted measurement: do not re-ask what the judge "
            "already has a usable verdict for. Off by default — otherwise a repeat "
            "launch on the same day would silently measure nothing"
        ),
    )
    resume_window_hours: int = Field(
        default=24,
        ge=0,
        description=(
            "How old a verdict may be and still count as ours when resuming. "
            "Zero — no window. What is resumed is an interrupted attempt, not a "
            "cancellation of yesterday measurement: without a window the daily "
            "cycle would decide on its second day that everything was already done"
        ),
    )
    max_consecutive_failures: int = Field(
        default=20,
        ge=0,
        description=(
            "After how many failed questions in a row to abandon an arm. Zero — do "
            "not abandon. A port from LiveTruth: a wrong key or a node that has "
            "gone down is otherwise paid for in hours and a table of nothing but "
            "failures"
        ),
    )
    reuse_answers: bool = Field(
        default=True,
        description=(
            "Do not ask the same thing twice: the endpoint retrieval for a question "
            "and the model answer to an already-asked prompt at zero temperature. "
            "Switched off when the spread of repeated calls itself has to be measured"
        ),
    )

    # --- The generators. All eight are on by default.
    disabled_generators: list[str] = Field(
        default_factory=list,
        description="Generators not to run, even when all are asked for",
    )

    # --- The judging and screening thresholds.
    #
    # This is calibration, not the design of the measurement: it changes along with
    # the corpus and the models, and keeping it as constants in the code means
    # demanding a commit for every attempt to tune it.
    key_facts_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "What share of the listed facts has to be covered for an explanation to "
            "count as correct. Not one: the eli5 level legitimately drops the "
            "particulars it exists to drop"
        ),
    )
    answer_coverage_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Share of the gold answer content words looked for in the chunk. Not "
            "one: a gold answer paraphrases, inflects and abbreviates, and "
            "demanding it verbatim would screen out almost everything. Not a "
            "third: at that an answer assembled from the chunk's common words "
            "and an invented substance gets through"
        ),
    )
    consistency_floor: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Below this consistency the accuracy measured speaks about which run "
            "made it into the report rather than about the model"
        ),
    )

    # --- The audit log
    #
    # The benchmark numbers are a judge model verdicts, and they can only be
    # checked against the raw records: what exactly was asked, with what prompt,
    # what was answered in each arm and how the judge justified it. The log is
    # written beside the answer rather than assembled after the fact: a prompt
    # depends on the settings of the moment, and those change.
    audit_log: bool = Field(
        default=True,
        description="Save the prompts and the judge reasoning beside every answer",
    )
    audit_max_chars: int = Field(
        default=20000,
        ge=1000,
        description="The ceiling on one log record: chunks can be long",
    )
    methodology_profile: str = Field(
        default="default",
        description=(
            "The methodology profile name. Written into every run: as soon as the "
            "thresholds and prompts are configurable, the report is obliged to know "
            "how a row was obtained, otherwise it will silently mix non-comparable "
            "runs"
        ),
    )

    spaces_file: Path = Field(default=Path("config/spaces.json"))

    # --- The control API
    #
    # Off until a token is set, and that is not over-caution. Its one route starts
    # work that runs for hours and costs money on external models; a port open by
    # default would mean that anyone who could reach the network could spend
    # someone else budget. The behaviour is the same as a Space with its
    # benchmarks_mode: not "you may not" but "there is nothing here".
    control_token: str = Field(
        default="",
        description="The control API key. Empty — the API says it is not configured",
    )
    control_host: str = Field(default="0.0.0.0", description="The control API address")
    control_port: int = Field(default=8200, ge=1, le=65535)
    control_origins: list[str] = Field(
        default_factory=list,
        description=(
            "The origins CORS is allowed for. Empty — there are no browser requests "
            "at all: the UI comes here through its own server, not from a page"
        ),
    )

    llm_timeout: float = Field(
        default=900.0,
        description=(
            "Ollama keeps one model in memory and serves one request at a time, so "
            "the wait is long"
        ),
    )
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    answer_max_tokens: int = Field(
        default=8192,
        ge=64,
        description=(
            "The ceiling on any model answer: the model under test, the judge, the "
            "grounding check. One for all and generous — a port of decision P1 from "
            "LiveTruth, where reasoning measurements reached 3269 tokens and one "
            "case burned 4096. This adds nothing to the bill: max_tokens limits, it "
            "does not order"
        ),
    )

    # --- The Space ChromaDB
    chroma_tenant: str = Field(default="default_tenant")
    chroma_database: str = Field(default="default_database")
    chroma_internal_port: int = Field(
        default=8100, description="The ChromaDB port inside the Space container"
    )

    # --- Generation
    chunks_per_run: int = Field(default=8, ge=1)
    pairs_per_chunk: int = Field(default=2, ge=1)
    min_chunk_chars: int = Field(default=400, ge=0)

    # --- What the set is like over time
    #
    # The corpus grows, and the measurement cannot grow along with it: three arms
    # across nine models multiply by every item. Sooner or later you have to choose
    # not "how much we can manage" but "what exactly we are measuring", and that
    # choice is substantive.
    #
    # An incremental set accumulates: that is how a stable corpus is measured, where
    # a correct answer does not go out of date. A rolling one moves with time: in
    # the measurement is what grew out of fresh documents, and that is sensible
    # where the interest is in the latest, while last year document answers a
    # question nobody asks any more.
    dataset_mode: DatasetMode = Field(
        default=DatasetMode.INCREMENTAL,
        description=(
            "incremental — the set accumulates; rolling — only items from documents "
            "of the last document_window_days are in the measurement; rebuild — the "
            "same material, but the pool of questions is built afresh as a separate "
            "cohort"
        ),
    )
    document_window_days: int = Field(
        default=0,
        ge=0,
        description=(
            "The freshness window for documents, in days. Zero — no window, the "
            "whole corpus. It applies in incremental mode too: there it limits what "
            "to BUILD items from, but does not take those already built out of the set"
        ),
    )
    dataset_max_pairs: int = Field(
        default=0,
        ge=0,
        description=(
            "The ceiling on active items in the set. Zero — no ceiling. The surplus "
            "is taken out of the measurement rather than deleted: the selection goes "
            "by the same round-robin over halves and generators as the run limit"
        ),
    )

    # --- The extractive generators: what to cut the span with
    #
    # The decision is made automatically and per document: a corpus can be mixed,
    # and making the user choose a language for every file means offloading an
    # implementation detail onto them.
    #
    #   auto  — if there is a spaCy model for the document language we go through
    #           it; otherwise the same chunk is processed by an LLM. Nothing to set.
    #   spacy — spaCy only. Documents in languages without a model are skipped.
    #           Meaningful when reproducibility matters: the span is cut out of the
    #           text and the gold answer cannot be invented.
    #   llm   — LLM only. One path for any language, spaCy not needed at all.
    extractive_mode: str = Field(
        default="auto",
        description="What to build fill-in-the-blank with: auto, spacy or llm",
    )
    spacy_models: dict[str, str] = Field(
        default_factory=lambda: {
            "en": "en_core_web_sm",
            "ru": "ru_core_news_sm",
            "de": "de_core_news_sm",
            "fr": "fr_core_news_sm",
            "es": "es_core_news_sm",
            "it": "it_core_news_sm",
            "pt": "pt_core_news_sm",
            "nl": "nl_core_news_sm",
        },
        description=(
            "Language code -> spaCy model name. Only the installed ones are taken; "
            "the rest silently go down the LLM path"
        ),
    )

    # --- The bounds outwards (invariant 2)
    allow_external_models: bool = Field(
        default=False,
        description=(
            "Allow calls to models outside the perimeter. Off by default: the "
            "questions are generated from private documents and often quote them "
            "almost verbatim"
        ),
    )
    external_hosts: list[str] = Field(
        default_factory=list,
        description="Hosts allowed explicitly when allow_external_models is on",
    )

    # --- The master key for stored secrets
    #
    # The provider keys and the Space tokens are sealed before they reach the
    # database. Without this there is nowhere to put them: the service refuses
    # to store a secret rather than writing it in the clear, because a service
    # that quietly falls back ends up with half its secrets encrypted and
    # nobody aware of which half.
    secret_key: str = Field(
        default="",
        description=(
            "The master key, base64, 32 bytes — `syft-benchmark secrets keygen` "
            "makes one. Empty: secrets cannot be stored"
        ),
    )
    secret_keys_retired: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Keys kept only so that rows sealed under them still open, by the "
            "fingerprint they are recorded under. This is what makes rotation a "
            "step rather than a migration of everything at once"
        ),
    )

    # --- The daily cycle
    generate_in_cycle: bool = Field(
        default=True,
        description=(
            "Build the dataset at the start of the cycle. Switched off when the "
            "dataset is filled separately or the corpus is closed to the generator"
        ),
    )

    # --- Publishing
    #
    # The published arm is deliberately not here. It is a property of the NODE, not
    # of the installation: an endpoint in raw mode does not formulate an answer, arm
    # B is not run against it at all, and a setting would leave such a node without
    # a single number despite excellent retrieval. It is chosen by the card, by the
    # kind of product — see report.card.
    #
    # For a multi-Space installation this was broken twice over: one Space is
    # summary, another raw, and the setting is one for both.

    def load_spaces(self) -> list[SpaceConfig]:
        """Read the Space registry.

        Raises:
            FileNotFoundError: there is no such file — that is a configuration
                error, not an empty list: a benchmark without a single Space is
                meaningless, and a silent "zero checks" is worse than a refusal.
        """
        if not self.spaces_file.exists():
            raise FileNotFoundError(
                f"there is no file with the list of Spaces: {self.spaces_file} "
                f"(see config/spaces.example.json)"
            )
        raw = json.loads(self.spaces_file.read_text(encoding="utf-8"))
        return [SpaceConfig.model_validate(item) for item in raw]

    def retrieval_for(self, space: SpaceConfig) -> tuple[int, float]:
        """The retrieval parameters for this Space: its own value or the shared one.

        Returns:
            (how many chunks to ask for, the similarity threshold)
        """
        top_k = (
            space.retrieval_top_k
            if space.retrieval_top_k is not None
            else self.retrieval_top_k
        )
        threshold = (
            space.similarity_threshold
            if space.similarity_threshold is not None
            else self.similarity_threshold
        )
        return top_k, threshold

    def measurement_params(self, space: SpaceConfig | None = None) -> dict[str, Any]:
        """A snapshot of the settings a run was obtained with.

        Written into ``runs.params`` and goes into the audit export. The point is
        exactly one: in six months it must be visible from a report row which
        threshold and which ceilings produced it — otherwise a configurable
        methodology turns the history of measurements into a mess.
        """
        top_k, threshold = (
            self.retrieval_for(space)
            if space is not None
            else (self.retrieval_top_k, self.similarity_threshold)
        )
        return {
            "profile": self.methodology_profile,
            # The frozen slice is part of HOW a row was obtained, on a par with the
            # threshold: a run over a slice and a run over the whole set answer
            # different questions, and their shares must not be added up.
            "question_set": str(self.question_set) if self.question_set else "",
            "retrieval_top_k": top_k,
            "similarity_threshold": threshold,
            "context_source": self.context_source.value,
            "context_docs": self.context_docs,
            "endpoint_max_tokens": self.endpoint_max_tokens,
            "endpoint_temperature": self.endpoint_temperature,
            "key_facts_threshold": self.key_facts_threshold,
            "text_metrics": [m.value for m in self.text_metrics],
            "denial_rounds": self.denial_rounds,
            "monte_carlo_temperatures": list(self.monte_carlo_temperatures),
            "monte_carlo_trials": self.monte_carlo_trials,
        }

    def space_by_key(self, key: str) -> SpaceConfig:
        spaces = self.load_spaces()
        for space in spaces:
            if space.key == key:
                return space
        known = ", ".join(s.key for s in spaces)
        raise KeyError(f"unknown Space: {key} (available: {known})")


class ExternalCallBlocked(RuntimeError):
    """An attempt to call a model outside the perimeter while permission is off."""


_LOCAL_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}
)


def check_model_host(url: str, settings: Settings) -> None:
    """Let a model call through only if it stays inside the perimeter.

    Called before every LLM request. Local addresses and docker-network service
    names always pass; everything else only with ``allow_external_models``
    explicitly on and only from the ``external_hosts`` list.

    Args:
        url: The address about to be called
        settings: The current settings

    Raises:
        ExternalCallBlocked: the address is outside the perimeter and there is no
            permission
    """
    host = (urlparse(url).hostname or "").lower()

    # A name without dots is a docker-network service (ollama, space, chroma), that
    # is, an address inside the perimeter. External names always contain a dot.
    if host in _LOCAL_HOSTS or "." not in host:
        return

    if settings.allow_external_models and host in {
        h.lower() for h in settings.external_hosts
    }:
        return

    raise ExternalCallBlocked(
        f"the call to {host} is blocked: the questions are built on a private "
        f"corpus and must not leave the perimeter. To allow it deliberately — "
        f'BENCH_ALLOW_EXTERNAL_MODELS=true and BENCH_EXTERNAL_HOSTS=["{host}"]'
    )


# --- Where a setting is allowed to live -------------------------------------
#
# Three layers assemble a measurement: the installation's defaults, the Space's
# instrument, the node's probe. The bottom layer is a row in
# `installation_settings`, with the environment as the read-only layer under it.

# Read before the database can be read, or read instead of trusting it.
#
# The database address cannot be in the settings it holds; the control key
# cannot be either, because a lock whose key is inside it is not a lock;
# `spaces_file` and `secret_key` are the same kind of thing.
#
# The perimeter is here for a stronger reason. The ban on calls outside is a
# check rather than an agreement, because the questions are built from private
# documents — and an allowed-hosts list editable through the API would let
# anyone holding the control key send the corpus anywhere.
BOOTSTRAP_FIELDS: frozenset[str] = frozenset(
    {
        "database_url",
        "control_token",
        "control_host",
        "control_port",
        "control_origins",
        "allow_external_models",
        "external_hosts",
        "spaces_file",
        "secret_key",
        "secret_keys_retired",
    }
)

# Stored sealed, in `credentials`, never in the settings document: those are
# copied into every job snapshot and run params, handed out by /defaults and
# written to the log, and a key would travel with them.
SECRET_FIELDS: frozenset[str] = frozenset(
    {"llm_api_key", "generator_key", "judge_key", "subject_key"}
)


def stored_fields() -> frozenset[str]:
    """The settings the installation's row is allowed to carry."""
    return frozenset(Settings.model_fields) - BOOTSTRAP_FIELDS - SECRET_FIELDS


def env_settings() -> Settings:
    """The settings as the environment alone has them.

    The bootstrap layer, and the layer beneath everything the store holds.
    Nothing that runs a measurement should call this — it does not know about
    the installation's row, and would quietly measure with the defaults.
    """
    return Settings()


def get_settings() -> Settings:
    """The settings a measurement is run with.

    The environment for what must come from the environment, the installation's
    row for the rest, and the sealed credentials for the keys. The layers above
    this one — the Space's instrument and the node's probe — are applied by
    ``control.compose.settings_for`` on top of what this returns.

    The stored half is cached: this is called from several dozen places, and
    reading a row each time would mean a query per settings lookup. A write
    through the store clears it.
    """
    from syft_benchmark.db import store

    base = Settings()
    return store.apply(base)
