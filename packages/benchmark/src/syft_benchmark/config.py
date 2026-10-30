"""The benchmark's settings and the domain vocabulary they are written in.

``Settings`` is read from the environment and .env; the installation's stored
overrides are laid over it by ``get_settings``. The enums here name the arms,
verdicts, blocks, pair and job states shared by every package.

The ban on external calls (invariant 2, docs/privacy.md) lives here too, as a
check rather than an agreement: the questions are generated from private
documents, so a model call leaves the perimeter only for an explicitly allowed
host.
"""

from __future__ import annotations

import ipaddress
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ContextMode(StrEnum):
    """The measurement arm: who answers and what they have in front of them.

    Without this field the arms are indistinguishable in the database, and the
    whole construction rests on comparing them with one another.

    The two arms measure different things, and they must not be added up; what
    each measures is in ``ARM_MEANING``.
    """

    CLOSED_BOOK = "closed_book"  # arm A: the question without a single corpus chunk
    MODEL_WITH_CONTEXT = "model_with_context"  # arm C: the same model + the retrieval


# The arms a measurement runs, in the order it runs them.
MEASURED_ARMS: tuple[ContextMode, ...] = (
    ContextMode.CLOSED_BOOK,
    ContextMode.MODEL_WITH_CONTEXT,
)

# The arm letter for reports. Reading "closed_book vs model_with_context" in a
# table is hard, while "A vs C" is exactly the language the methodology is
# described in.
ARM_LETTER: dict[str, str] = {
    ContextMode.CLOSED_BOOK.value: "A",
    ContextMode.MODEL_WITH_CONTEXT.value: "C",
}

# What each arm measures, as the report states it.
ARM_MEANING: dict[ContextMode, str] = {
    ContextMode.CLOSED_BOOK: "the model alone, without a single corpus chunk. "
    "Measures the honesty of the model itself: a correct answer here means not "
    "node quality but that the corpus is already familiar to it (or a guess)",
    ContextMode.MODEL_WITH_CONTEXT: "the same model as in arm A, plus what the "
    "endpoint returned. A and C differ by exactly the presence of context, so "
    "their difference is interpretable",
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


class ExpectedBehavior(StrEnum):
    """What counts as the correct behaviour on this question.

    Questions generated from chunks are answerable by construction; the control
    half (no answer in the corpus, a false premise) measures the rest of the
    behaviour.

    The field sits on the pair, not on the run: the correct behaviour is
    determined by the question, not by who answers it.
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
    """The three outcomes a judge reduces any answer to, and two non-outcomes.

    ``PENDING`` — an answer received but not yet judged, for deferred judging:
    answers collected by machine, verdicts issued from the console later.

    ``TECHNICAL`` — nothing was measured: the endpoint unreachable, the provider
    refusing, the key out, the retrieval empty, the judge itself silent. Such a
    row says something about the rig and nothing about the model.

    Neither enters a share, and neither may be issued by hand.
    ``runs.judge.is_technical`` tests the verdict; ``runs.judge.is_error`` tests
    the answer text for a failure message.
    """

    CORRECT = "correct"
    ABSTAIN = "abstain"
    HALLUCINATE = "hallucinate"
    PENDING = "pending"
    TECHNICAL = "technical"
    # A control question answered with specifics its web search supports: not
    # a hallucination, counted on its own.
    WEB_SOURCED = "web_sourced"
    # An explanation the article supports that falls short of the key-facts
    # bar: neither right nor hallucinated, counted like abstain in the shares.
    INCOMPLETE = "incomplete"


class ControlOutcome(StrEnum):
    """How a control question was handled, as the judge reads it.

    Kept in ``Result.extra["behavior"]``. The verdict carries it into the
    shares: declined -> abstain, corrected -> correct on a false premise
    (abstain otherwise), web_sourced -> web_sourced, made_up -> hallucinate.
    """

    DECLINED = "declined"
    CORRECTED = "corrected"
    WEB_SOURCED = "web_sourced"
    MADE_UP = "made_up"


class TextMetric(StrEnum):
    """A mechanical measure of an answer resemblance to the gold one.

    The verdict is issued by a judge, that is, by a model, and there is nothing to
    check it with except another opinion. These metrics are computed mechanically
    and therefore work as a second, independent view: if the verdict and the
    textual match diverge, that is grounds for a look with your own eyes.

    They do not know correctness and cannot: what is measured is word overlap. So
    they enter no share of the report.
    """

    BLEU = "bleu"  # n-gram overlap with a brevity penalty
    ROUGE = "rouge"  # ROUGE-1/2 and ROUGE-L by F1
    BERTSCORE = "bertscore"  # embedding similarity; needs the bert-score package


class EvalBlock(StrEnum):
    """The test block.

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

    ``STRICT`` refuses to save or start a configuration with a clash (the
    control API answers 422), and a run that still meets one stops. ``WARN``
    allows it and logs every clash. The settings form offers these two;
    ``OFF`` and ``RECUSE`` are accepted when set by hand.
    """

    OFF = "off"  # do not check
    WARN = "warn"  # allow, log the clash
    RECUSE = "recuse"  # the judge recuses itself, those answers stay unassessed
    STRICT = "strict"  # refuse the save, the launch and the run


class WebSearchEngine(StrEnum):
    """Which web search a model uses when a role searches.

    ``NATIVE`` is the model's own search, ``PLUGIN`` the Exa engine (OpenRouter's
    web plugin). ``AUTO`` takes native when the catalogue says the model has it.
    """

    AUTO = "auto"
    NATIVE = "native"
    PLUGIN = "plugin"


class JudgeReasoningEffort(StrEnum):
    """How hard a judge reasons: OpenRouter's ``reasoning.effort``.

    ``DEFAULT`` sends nothing and leaves the model's own default.
    """

    NONE = "none"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DEFAULT = "default"


# The layer value that asks for the model's own temperature: a layer's null
# means "inherit", so "model default" needs a value of its own.
MODEL_DEFAULT: Literal["default"] = "default"


class ManualStatusPriority(StrEnum):
    """Who decides a question the user returned to the set by hand.

    ``FILTER``: the web check may reject it again. ``MANUAL``: the user's choice
    wins and the web check skips it.
    """

    FILTER = "filter"
    MANUAL = "manual"


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


class StatusReason(StrEnum):
    """Why a pair is not active, as a code (``qa_pairs.status_reason``)."""

    GROUNDING = "grounding"
    RETRIEVAL_GATE = "retrieval_gate"
    # Live retrieval did not find the answer to an ordinary question
    # (generation/filter_stage.py, the archive check).
    NOT_ANSWERABLE = "not_answerable"
    # No row is stored for a duplicate (the unique index refuses it); the code
    # exists for the report's funnel.
    DUPLICATE = "duplicate"
    OWNER = "owner"
    # Taken out by the freshness window, a newer cohort or the set cap.
    ROTATION = "rotation"
    # The web check model answered it correctly with web search
    # (generation/web_check.py).
    WEB_ANSWERABLE = "web_answerable"
    # A trick question the web check model answered with specifics its search
    # supports (generation/web_check.py).
    PUBLIC_KNOWLEDGE = "public_knowledge"
    # Rejected as written (generation/pipeline.py): the item is in another
    # language than its article, or names a subject the question alone does
    # not identify.
    WRONG_LANGUAGE = "wrong_language"
    AMBIGUOUS_ENTITY = "ambiguous_entity"
    OTHER = "other"


class JobState(StrEnum):
    """The state of a job launched from outside.

    ``QUEUED`` is separate from ``RUNNING`` because one job at a time runs per
    node and the rest wait; without it a queue is indistinguishable from a hung
    run.

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
    """Where the job is now. Shown to the owner rather than computed."""

    PENDING = "pending"
    GENERATE = "generate"
    FILTER = "filter"
    EVALUATE = "evaluate"
    JUDGE = "judge"
    DONE = "done"


class JobKind(StrEnum):
    """What operation a job is, as opposed to ``phase``, which is where it is now.

    ``execute()`` picks a function by ``kind`` before there is any phase.
    ``PIPELINE`` is every job ``/targets/{key}/runs`` creates: any combination
    of the ``generate``/``filter``/``evaluate`` flags is one call to
    ``scheduler.measure()``. ``FILTER`` and ``JUDGE`` work over already-stored
    input (pending pairs; pending verdicts), so each has its own kind and route.
    """

    PIPELINE = "pipeline"
    FILTER = "filter"
    JUDGE = "judge"


class DatasetMode(StrEnum):
    """Where the items in the next generation run come from.

    ``INCREMENTAL`` — the set accumulates: new material adds items and the
    earlier ones stay. For a stable corpus where an answer does not go stale.

    ``ROLLING`` — the set holds what grew out of documents from the last N days.
    What leaves the window leaves the set; what returns comes back with the same
    items, at no generation cost.

    ``REBUILD`` — the same material, a fresh pool of questions as a separate
    cohort. Comparing cohorts tells the quality of the questions apart from the
    model under test. It pays for the whole set again.
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

    @property
    def name(self) -> str:
        return self.title or self.key


class SpaceSeed(SpaceConfig):
    """One entry of the seed file (``config/spaces.json``).

    The node's description plus the two retrieval keys the file may set: the
    seed carries them into the target's probe, where they are edited from then
    on. None — the probe inherits the installation's value.
    """

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

    # --- The model roles, each with its own provider: the generator sees
    # documents and normally stays inside the perimeter, the models under test
    # do not and are usually external, and the judge must not share the tested
    # model's provider. An empty address means the shared ollama_url and
    # llm_api_key.
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
    filter_model: str | None = Field(
        default=None,
        description=(
            "The web check model: asked each new question with web search on, "
            "and a question it answers is dropped. Empty — no web check"
        ),
    )
    filter_judge_model: str | None = Field(
        default=None,
        description="The judge of the web check's answers. Empty — the first judge",
    )
    filter_url: str = Field(
        default="",
        description="The web check provider. Empty — the models under test's",
    )
    filter_key: str = Field(
        default="",
        description="The web check provider key. Empty — the models under test's",
    )
    judge_temperature: float | None = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description=(
            "Every judge's temperature, where the model takes one. "
            "None — the model's default"
        ),
    )
    judge_reasoning_effort: JudgeReasoningEffort = Field(
        default=JudgeReasoningEffort.LOW,
        description=(
            "Every judge's reasoning effort, where the model reasons; "
            "default — the model's own"
        ),
    )
    manual_status_priority: ManualStatusPriority = Field(
        default=ManualStatusPriority.FILTER,
        description=(
            "A question returned by hand: filter — the web check may reject it "
            "again; manual — the user's choice wins"
        ),
    )

    # --- Web search, per role. Only OpenRouter models search; elsewhere the
    # toggle has no effect. The web check model always searches.
    web_search_engine: WebSearchEngine = Field(
        default=WebSearchEngine.AUTO,
        description=(
            "auto: the model's own search when it has one, else Exa; native; "
            "plugin: Exa search"
        ),
    )
    web_search_closed_book: bool = Field(
        default=True, description="The tested model searches the web on its own"
    )
    web_search_with_context: bool = Field(
        default=False,
        description="The tested model searches the web when given the endpoint's data",
    )
    web_search_generator: bool = Field(
        default=False, description="The question writer searches the web"
    )
    web_search_judge: bool = Field(
        default=False, description="The judges search the web"
    )
    web_search_max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Results per search, for the Exa engine",
    )
    web_search_max_calls: int = Field(
        default=0,
        ge=0,
        le=30,
        description=(
            "Searches one answer of a tested model may make. Zero — the "
            "provider's own limit (30 on OpenRouter)"
        ),
    )

    # --- The measurement arms. Both by default: A and C differ by exactly the
    # context, and that difference is the measurement.
    arms: list[ContextMode] = Field(
        default_factory=lambda: list(MEASURED_ARMS),
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
    fragment_max_chars: int = Field(
        default=2000,
        ge=200,
        le=20000,
        description=(
            "The ceiling on one chunk's text, applied before the arm C prompt is "
            "assembled: it decides what the model sees, not only what is kept"
        ),
    )

    # --- The request to the endpoint. The similarity threshold is an axis of
    # the measurement: at zero the endpoint returns top-k for any question,
    # including one whose answer is not in the corpus.
    retrieval_top_k: int = Field(
        default=5, ge=1, le=50, description="How many chunks to ask the endpoint for"
    )
    similarity_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="The similarity threshold in retrieval"
    )
    endpoint_max_tokens: int = Field(
        default=500,
        ge=1,
        description="The ceiling on the endpoint's answer when arm C reads it",
    )
    endpoint_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="The endpoint's temperature when it answers",
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

    # --- Concurrency: how many calls to keep in flight. Two lanes, because an
    # external provider holds dozens of requests while the endpoint under test
    # is one node with one model, where a queue only accumulates timeouts.
    concurrency: int = Field(
        default=16,
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
    # --- The text metrics. Off by default: they do not know correctness and
    # enter no share; they give a view of the answers independent of the judge.
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
            "not abandon. A wrong key or a node that has "
            "gone down is otherwise paid for in hours and a table of nothing but "
            "failures"
        ),
    )
    max_job_usd: float = Field(
        default=100.0,
        ge=0.0,
        description=(
            "A job whose priced calls reach this many USD is stopped, as if by "
            "the owner. Zero — no cap"
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

    # --- The generators. All are on by default.
    disabled_generators: list[str] = Field(
        default_factory=list,
        description="Generators not to run, even when all are asked for",
    )

    # --- The judging and screening thresholds: calibration that changes with
    # the corpus and the models.
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
    entity_check: bool = Field(
        default=True,
        description=(
            "Ask the question writer, in a fresh call, whether every person, "
            "organisation and product a question names is identifiable from the "
            "question alone; questions that fail are rejected"
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

    # --- The audit log: the prompts and the judge's reasoning, written beside
    # each answer, since a prompt depends on the settings of the moment.
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

    # --- The control API. Off until a token is set: it starts work that runs
    # for hours and costs money on external models.
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
            "grounding check. One for all and generous: reasoning alone can take "
            "4096 tokens. This adds nothing to the bill: max_tokens limits, it "
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
    chunks_per_run: int = Field(
        default=8,
        ge=1,
        description=(
            "The question budget: each kind writes at most chunks_per_run x "
            "pairs_per_chunk questions per run, walking every passage in the window"
        ),
    )
    pairs_per_chunk: int = Field(default=2, ge=1)
    min_chunk_chars: int = Field(default=400, ge=0)

    # --- What the set is like over time; see ``DatasetMode``.
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
            "round-robin over the generators"
        ),
    )
    top_up_max_usd: float = Field(
        default=5.0,
        ge=0.0,
        description=(
            "What a build may spend, in USD, writing and checking more of the kinds "
            "the checks left short of their target. Zero — no top-up"
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

    # --- The master key for stored secrets. Without it a secret is refused
    # rather than written in the clear (see db/crypto.py).
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

    @field_validator("judge_temperature", mode="before")
    @classmethod
    def _model_default_temperature(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip().lower() in ("", MODEL_DEFAULT):
            return None
        return value

    def load_spaces(self) -> list[SpaceSeed]:
        """Read the seed file.

        Raises:
            FileNotFoundError: no seed file — nothing to seed.
            UnicodeDecodeError: the file is not UTF-8.
            json.JSONDecodeError: the file is not JSON.
            pydantic.ValidationError: an entry is not a Space description.
        """
        if not self.spaces_file.exists():
            raise FileNotFoundError(
                f"there is no file with the list of Spaces: {self.spaces_file} "
                f"(see config/spaces.example.json)"
            )
        raw = json.loads(self.spaces_file.read_text(encoding="utf-8"))
        return [SpaceSeed.model_validate(item) for item in raw]

    def measurement_params(self) -> dict[str, Any]:
        """A snapshot of the settings a run was obtained with.

        Written into ``runs.params`` and the audit export, so a report row says
        which threshold and ceilings produced it.
        """
        return {
            "profile": self.methodology_profile,
            # A run over a slice and one over the whole set must not be added up.
            "question_set": str(self.question_set) if self.question_set else "",
            "retrieval_top_k": self.retrieval_top_k,
            "similarity_threshold": self.similarity_threshold,
            "context_source": self.context_source.value,
            "context_docs": self.context_docs,
            # A ceiling on what the model was shown, not on what was stored.
            "fragment_max_chars": self.fragment_max_chars,
            "answer_max_tokens": self.answer_max_tokens,
            "endpoint_max_tokens": self.endpoint_max_tokens,
            "endpoint_temperature": self.endpoint_temperature,
            "key_facts_threshold": self.key_facts_threshold,
            "text_metrics": [m.value for m in self.text_metrics],
            "denial_rounds": self.denial_rounds,
            "monte_carlo_temperatures": list(self.monte_carlo_temperatures),
            "monte_carlo_trials": self.monte_carlo_trials,
            # Searching changes what a model can answer, so it is part of how a
            # row was obtained.
            "web_search_engine": self.web_search_engine.value,
            "web_search_closed_book": self.web_search_closed_book,
            "web_search_with_context": self.web_search_with_context,
            "web_search_judge": self.web_search_judge,
            "web_search_max_results": self.web_search_max_results,
            "web_search_max_calls": self.web_search_max_calls,
            # How the judges were tuned decides their verdicts.
            "judge_temperature": self.judge_temperature,
            "judge_reasoning_effort": self.judge_reasoning_effort.value,
        }


class ExternalCallBlocked(RuntimeError):
    """An attempt to call a model outside the perimeter while permission is off."""


_LOCAL_NAMES = frozenset({"localhost", "host.docker.internal"})

# A single DNS label: letters, digits and inner hyphens, at most 63 characters.
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
# A label a resolver may read as an IPv4 address (``2130706433``, ``0x7f000001``).
_NUMERIC = re.compile(r"0x[0-9a-f]*|[0-9]+")


# The schemes the model client can call; any other address is unreadable.
_CALLABLE_SCHEMES = frozenset({"http", "https"})


def model_host(url: str) -> str:
    """The host of an http(s) ``url``, lower-cased, IPv6 brackets dropped.

    Empty, so refused by the perimeter, when the address has no host or any
    scheme other than http/https, scheme-relative ``//ollama:11434`` included:
    the model client cannot call it, so it must not pass as inside.
    """
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in _CALLABLE_SCHEMES:
            return ""
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


def host_is_inside(host: str) -> bool:
    """Whether a call to ``host`` stays inside the perimeter.

    Inside: ``localhost``, ``host.docker.internal``, loopback IP addresses (v4,
    v6, or v4-mapped v6), and a single-label hostname (a service on the docker
    network such as ``ollama``) that no resolver reads as a number. Everything
    else is outside: private, link-local and unspecified addresses, public
    hosts, and an empty host, since an address that cannot be read cannot be
    shown to stay in.
    """
    host = host.lower()
    if host in _LOCAL_NAMES:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return _LABEL.fullmatch(host) is not None and not _NUMERIC.fullmatch(host)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback


def url_is_inside(url: str) -> bool:
    """Whether a call to ``url`` stays inside the perimeter (``host_is_inside``)."""
    return host_is_inside(model_host(url))


def check_model_host(url: str, settings: Settings) -> None:
    """Let a model call through only if it stays inside the perimeter.

    Called before every LLM request. An address inside the perimeter
    (``host_is_inside``) always passes; any other only with
    ``allow_external_models`` explicitly on and its host in ``external_hosts``.

    Args:
        url: The address about to be called
        settings: The current settings

    Raises:
        ExternalCallBlocked: the address is outside the perimeter and there is no
            permission
    """
    host = model_host(url)
    if host_is_inside(host):
        return
    if not host:
        raise ExternalCallBlocked(
            f"the call to {url!r} is blocked: it cannot be read as an http(s) "
            f"address with a host, so it "
            f"cannot be shown to stay inside the perimeter"
        )
    if settings.allow_external_models and host in {
        h.lower() for h in settings.external_hosts
    }:
        return

    raise ExternalCallBlocked(
        f"the call to {host} is blocked: the questions are built on a private "
        f"corpus and must not leave the perimeter. To allow it deliberately — "
        f'BENCH_ALLOW_EXTERNAL_MODELS=true and BENCH_EXTERNAL_HOSTS=["{host}"]'
    )


# Three layers assemble a measurement: the installation's defaults (a row in
# `installation_settings` over the read-only environment), the Space's
# instrument, the node's probe.

# Read only from the environment: needed before the database can be read (its
# address, the spaces file, the master keys), or not to be trusted to it (the
# control API's own settings; the perimeter, which an API-editable host list
# would let anyone holding the control key widen).
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
    {"llm_api_key", "generator_key", "judge_key", "subject_key", "filter_key"}
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
    row for the rest, and the sealed credentials for the keys. The Space's
    instrument and the node's probe are applied on top of this by
    ``control.compose.settings_for``. The stored half is cached by ``db.store``.
    """
    from syft_benchmark.db import store

    base = Settings()
    return store.apply(base)
