"""The control API's contract: what may be configured and launched from outside.

The benchmark has some fifty settings, and dumping them outwards as one flat
pile is not on — not because of the size, but because they belong to different
owners and are overridden at different depths. Here they are split into three
layers, and the split is a meaningful one:

* **Instrument** — what we measure with: the arms, the blocks, the judge and
  the panel, the models under test, the judging thresholds. It is the same for
  every node of one installation, and that is the whole point: the card
  declares it in the ``instrument`` block, and the endpoints that can be
  compared with one another are exactly those whose instrument matched.
  Allowing it to be changed on a single node means quietly making two nodes
  incomparable while leaving the promise of the opposite in their cards.

* **Probe** — what we ask a particular node and how: the set's mode, the
  freshness window, the cap on items, the generators, the retrieval and answer
  parameters. Here a difference between nodes is legitimate and expected — the
  corpora differ — and the card reports it honestly in the ``dataset`` block.

* **Process** — addresses, keys, the database, concurrency. It does not go
  outwards at all. A model provider's key that has travelled into another
  service's database for the sake of a form in a UI is a leak paid for with
  convenience.

Every field is optional, and ``None`` means "take it from the layer above", not
zero. There are three layers: the endpoint's value → the space's value → the
installation's default. Without that distinction "0 documents in the window"
and "the window was never configured" would merge into one value, and a default
setting would silently change the measurement.
"""

from __future__ import annotations

import string
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    DatasetMode,
    EvalBlock,
    JudgePolicy,
    TextMetric,
)
from syft_benchmark.llm.catalog import ModelEntry


class Layer(BaseModel):
    """What both settings layers share: strictness and the merge rule."""

    model_config = ConfigDict(extra="forbid")

    def overrides(self) -> dict[str, object]:
        """Only what is actually set on this layer.

        Merging goes by the fields that were set, not by the non-empty ones: an
        empty list of generators is a meaningful "do not disable any", and
        losing it during the overlay would bring back a setting the owner
        removed.
        """
        return self.model_dump(exclude_unset=True, exclude_none=True, mode="json")


# The wrappers a copied list leaves behind: the quotes of a JSON string, the
# brackets of an array. They are trimmed off the ends rather than refused, and
# a stored row is the reason. A target saved before this check existed is read
# back through this same model, and refusing it there would leave its owner
# unable to open the very form that fixes it.
_WRAPPERS = "\"'`[]{}" + string.whitespace

# What no repair can turn into a name, because it is not a leftover: a space or
# a quote in the MIDDLE means the value is several names in one — a list that
# was split on the wrong character, or not split at all.
_NOT_IN_A_MODEL_NAME = "\"'`[]{}<>(),"


def _model_name(value: str) -> str:
    """One model name as the provider will see it, or a refusal naming why not.

    A list of models travels between a config file, documentation and a form,
    and on the way it keeps the punctuation of wherever it came from:
    ``"a/b", "c/d"`` out of JSON, ``["a/b", "c/d"]`` out of an array. A form
    that splits on the comma without taking the quotes off leaves them inside
    the name, the name reaches the provider verbatim, and every call of the run
    is refused with 400 — after the whole pass has been paid for.

    The check lives here rather than in the form because the form is someone
    else's and there is more than one of them: the next one will parse a list
    its own way, and this will still be here.
    """
    name = value.strip(_WRAPPERS)
    if not name:
        raise ValueError("a model name cannot be empty")
    found = sorted(
        {char for char in name if char in _NOT_IN_A_MODEL_NAME or char.isspace()}
    )
    if found:
        listed = ", ".join(repr(char) for char in found)
        raise ValueError(
            f"{value!r} is not a model name: it holds {listed}. "
            "Give one name per entry, without quotes or brackets"
        )
    return name


class Instrument(Layer):
    """What we measure with. One per space, not overridden on a single node."""

    # --- What we run
    arms: list[ContextMode] | None = Field(
        default=None,
        description=(
            "The arms of the measurement. Arm B does not run on a node in raw "
            "mode regardless of this setting: such a node does not compose answers"
        ),
    )
    blocks: list[EvalBlock] | None = Field(
        default=None, description="Ways of checking: direct, denial_loop, monte_carlo"
    )
    denial_rounds: int | None = Field(default=None, ge=1, le=12)
    monte_carlo_temperatures: list[float] | None = None
    monte_carlo_trials: int | None = Field(default=None, ge=1, le=20)

    context_source: ContextSource | None = Field(
        default=None, description="What to mix into the question in arm C"
    )
    context_docs: int | None = Field(default=None, ge=1, le=20)

    # --- Who takes part
    generator_model: str | None = None
    subject_models: list[str] | None = Field(
        default=None,
        description="The models under test. Empty — the generator model alone",
    )
    judge_model: str | None = None
    judge_models: list[str] | None = Field(
        default=None,
        description="The panel of judges. Empty — a single judge_model grades",
    )
    judge_policy: JudgePolicy | None = None

    # --- Judging thresholds
    key_facts_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    answer_coverage_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    consistency_floor: float | None = Field(default=None, ge=0.0, le=1.0)

    # --- Everything else about the instrument
    text_metrics: list[TextMetric] | None = Field(
        default=None,
        description=(
            "Mechanical similarity measures. They do not enter the report's shares"
        ),
    )
    extractive_mode: str | None = Field(
        default=None, description="What cuts the span out: auto, spacy or llm"
    )
    methodology_profile: str | None = Field(
        default=None,
        description=(
            "The profile's name. It is written into every run and into the card: "
            "change the thresholds but not the name and the report will silently "
            "mix incomparable runs"
        ),
    )
    max_consecutive_failures: int | None = Field(default=None, ge=0)
    reuse_answers: bool | None = None
    audit_log: bool | None = None

    # The models are the one group of settings whose values nobody can check
    # against a list: they are the provider's. So they are checked against what
    # a name cannot contain — see _model_name.
    @field_validator("generator_model", "judge_model")
    @classmethod
    def _one_model_name(cls, value: str | None) -> str | None:
        return None if value is None else _model_name(value)

    @field_validator("subject_models", "judge_models")
    @classmethod
    def _every_model_name(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else [_model_name(name) for name in value]


class Probe(Layer):
    """What we ask a node and how. Set per space and refined per endpoint."""

    # --- The item set
    dataset_mode: DatasetMode | None = Field(
        default=None, description="incremental, rolling or rebuild"
    )
    document_window_days: int | None = Field(
        default=None,
        ge=0,
        description="The documents' freshness window. Zero — the whole corpus",
    )
    dataset_max_pairs: int | None = Field(
        default=None, ge=0, description="Cap on active items. Zero — no cap"
    )
    disabled_generators: list[str] | None = Field(
        default=None, description="Generators not to run on this node"
    )
    chunks_per_run: int | None = Field(default=None, ge=1)
    pairs_per_chunk: int | None = Field(default=None, ge=1)
    min_chunk_chars: int | None = Field(default=None, ge=0)
    generate_in_cycle: bool | None = Field(
        default=None, description="Build the dataset at the start of the cycle"
    )

    # --- How we ask the node itself
    retrieval_top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "The similarity threshold. Zero means the node will return top-k for "
            "any question, including one the corpus holds no answer to"
        ),
    )
    endpoint_max_tokens: int | None = Field(default=None, ge=1)
    endpoint_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    endpoint_concurrency: int | None = Field(
        default=None,
        ge=1,
        le=32,
        description="How many requests to keep in flight to the node. Its capacity",
    )


class TargetSpec(BaseModel):
    """A node under test, as its owner enters it.

    The ChromaDB address sits next to the Space's address and is not derived
    from it: the benchmark goes to the index directly, past the Space's API, and
    gets there over the internal network or through ``docker exec``. The Space
    has no "hand me pieces of the corpus" route and is not meant to have one —
    questions and reference answers quote the documents almost verbatim, and the
    only way not to let them out is to have no code that can hand them over.
    """

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=64)
    title: str = ""
    url: str = Field(..., description="The base address of the Space's API")
    endpoint: str = Field(default="", description="The slug of the endpoint under test")
    token: str | None = Field(
        default=None,
        description=(
            "An access token for the Space's API. It is needed to hand the card "
            "back; it does not affect reading the corpus — that goes past the Space"
        ),
    )
    container: str = ""
    chroma_host: str = "localhost"
    chroma_port: int = Field(default=0, ge=0, le=65535)
    collection: str = Field(
        default="",
        description=(
            "The collection's name in the index. Empty — the target's key is "
            "taken, and it only matches when it was picked to fit the index by "
            "hand: checking the target will show what the index actually holds"
        ),
    )

    instrument: Instrument = Field(default_factory=Instrument)
    probe: Probe = Field(default_factory=Probe)

    enabled: bool = True
    # The schedule applies: the service watches it itself, and a target with an
    # interval set is measured without anybody pressing anything. An empty
    # interval means it is not — a disabled target is not measured either, and
    # keeps its schedule for when it is switched back on.
    schedule: str = Field(
        default="",
        description="An interval such as 24h or 90m. Empty — measure on request only",
    )
    schedule_at: str = Field(
        default="",
        description=(
            "The hour of the launch, HH:MM, IN UTC. It applies to a daily "
            "interval; on a shorter one the step is counted from the previous "
            "launch. UTC rather than the owner's time zone because the service "
            "has no way of knowing what the owner's night is"
        ),
    )


class TargetView(TargetSpec):
    """A target as its owner sees it. The token is not returned outwards."""

    token: str | None = Field(default=None, exclude=True)
    has_token: bool = False
    last_job: JobView | None = None
    # When the schedule will next fire, in UTC. Handed out rather than left to
    # the UI to work out: the service is the one that decides, and two
    # computations of one moment diverge on exactly the questions the owner asks
    # this one for — "why has it not run yet" and "did my change take".
    next_run_at: datetime | None = None


class SettingsDocument(BaseModel):
    """The installation's own settings — the layer under the instrument.

    A whole document rather than a patch, for the same reason a target is: the
    owner sees the form all at once, and "absent means unchanged" would leave
    no way to unset a field ever again.

    What may not be in it: a provider key, which is a secret and is stored
    sealed, and anything the process reads before it can read this row — the
    database, the control key, the perimeter. The refusal names the field and
    says which of the two it is.
    """

    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any] = Field(
        default_factory=dict,
        description="Only what is being overridden; the rest keeps its default",
    )


class SecretValue(BaseModel):
    """A secret on its way in. It only ever travels in this direction."""

    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, description="The secret itself")


class SecretView(BaseModel):
    """A secret as it may be spoken of: that it exists, and since when."""

    name: str
    updated_at: datetime


class RunRequest(BaseModel):
    """A request to measure now.

    The layers may be sent right here — then they lie on top of the ones saved
    on the target without touching them. This is not decoration: a trial run
    with a different similarity threshold must not change the setting the
    ordinary nightly measurement will go by.
    """

    model_config = ConfigDict(extra="forbid")

    instrument: Instrument | None = None
    probe: Probe | None = None
    generate: bool | None = Field(
        default=None,
        description=(
            "Build the dataset before measuring. None — as configured on the "
            "target. It is turned off when the corpus has not changed but a "
            "re-measurement is needed"
        ),
    )
    evaluate: bool | None = Field(
        default=None,
        description=(
            "Ask and grade after the dataset is built. None — yes. Turned off "
            "for a launch that only wants the question set refreshed: building "
            "it is cheap, asking a model about every item in it is not"
        ),
    )
    publish: bool = Field(
        default=True, description="Hand the card to the Space when it is over"
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many items to take PER GENERATOR. It exists for a trial run: "
            "a configuration has to be checkable without paying for hours. It is "
            "not an overall cap — a generator is a separate skill, and at a small "
            "value an overall cap would simply throw some skills out of the "
            "measurement. Publishing follows `publish` here as it does for a "
            "full run; the thin sample shows up in the card as `few_samples`"
        ),
    )


class JobView(BaseModel):
    """The state of a launch — what the owner watches while a measurement runs."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    target: str
    state: str
    phase: str
    # Runs: how many are finished out of how many. The full extent is not known
    # at once, and a zero in total means "still counting", not "nothing to do".
    done: int
    total: int
    # What is going on right now and how far it has got within itself. Two
    # counts rather than one: runs and questions inside a run are different
    # units, and merged into one bar they both lie.
    arm: str = ""
    block: str = ""
    model: str = ""
    step_done: int = 0
    step_total: int = 0
    message: str
    trigger: str
    error: str
    # The card assembled after measuring, in the shape the Space accepts it in
    # — present whether or not it was ever published. None until the job has
    # measured something to build one from.
    card: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @property
    def share(self) -> float | None:
        """The share of what is done. None while the extent of the work is unknown."""
        return self.done / self.total if self.total else None

    @property
    def questions_total(self) -> int:
        """How many questions will be asked over the whole measurement.

        The set is one and the same for every run — the arm, the block and the
        model change — and so the total extent is "questions in a run × number
        of runs". Until the first run has picked its items the extent is
        unknown, and this is zero.
        """
        return self.step_total * self.total

    @property
    def questions_done(self) -> int:
        """How many questions have been asked, counting finished runs whole."""
        return self.step_total * self.done + self.step_done


class RoleProvider(BaseModel):
    """Where one role goes. There is no key here and there cannot be — only a flag.

    The roles are listed by name because each has its own address/key pair, and
    a blanket "the provider is such-and-such" is sometimes wrong: the generator
    normally has to stay inside the perimeter, while the models under test are
    almost always external.
    """

    role: str = Field(description="generator, subject or judge")
    url: str = Field(description="The address this role actually uses")
    key_set: bool
    own: bool = Field(
        description="The role is pointed at its own provider rather than the shared one"
    )


class ProviderInfo(BaseModel):
    """Who does the computing: this installation's model provider.

    For display only. The key lives in the service's environment and does not
    leave it — neither by value nor into any storage. What travels outwards is
    exactly what the owner needs in order to understand what they are being
    measured with and at whose expense: the address, the signature in someone
    else's call console and the "a key is set" flag.
    """

    url: str
    app_name: str = Field(
        description="How the service introduces itself to the provider"
    )
    key_set: bool
    external_hosts: list[str] = Field(
        default_factory=list,
        description="Hosts allowed to answer when the way out is open",
    )
    roles: list[RoleProvider] = Field(default_factory=list)
    editable: bool = Field(
        default=False,
        description=(
            "Whether it is editable from here. Not for now: the provider is set "
            "by the service's environment, and the form shows that rather than "
            "editing it"
        ),
    )


class Capabilities(BaseModel):
    """What this installation can do — so the UI does not offer the impossible.

    The list comes from the benchmark rather than being hard-wired into the
    space. Otherwise the settings form would offer a generator this installation
    does not have, a model nobody gave it a key for, and an arm that does not
    run on this node — and that would come to light an hour into a run, in the
    log.
    """

    version: str
    profile: str = Field(description="This installation's methodology profile")
    arms: list[str]
    blocks: list[str]
    generators: list[str]
    subject_models: list[str]
    judge_models: list[str]
    text_metrics: list[str]
    extractive_modes: list[str]
    external_models: bool = Field(
        description="Whether calls to models outside the perimeter are allowed"
    )
    provider: ProviderInfo


class ModelCatalogView(BaseModel):
    """The models a form may offer, and how current the list is.

    The entries come from ``llm.catalog`` unchanged; what this adds is what the
    picker needs around them. ``pins`` matters most: handing the map out lets a
    form offer the convenient ``~vendor/thing-latest`` name and store the model
    it means today, which is the only one a run can be repeated under.
    """

    models: list[ModelEntry]
    vendors: list[str] = Field(description="Every vendor present, for the filter")
    pins: dict[str, str] = Field(
        default_factory=dict,
        description="Moving names, and what each one resolves to right now",
    )
    fetched: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Source -> when it was last refreshed. A catalogue whose age is "
            "invisible is one nobody thinks to refresh"
        ),
    )
    total: int = Field(description="How many models matched before any limit")


TargetView.model_rebuild()
