"""Benchmark API schemas.

Measurement settings are open ``dict[str, Any]`` documents owned by the
benchmark; only what the Space itself decides (connection, endpoint, on/off,
schedule) is typed here.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConnectionRequest(BaseModel):
    """Connect a benchmark, or change how this Space is wired to it."""

    name: str = Field(..., min_length=1, max_length=120)
    url: str = Field(..., min_length=1, description="Base URL of the control API")
    token: str | None = Field(
        default=None,
        description=("Control key. Omit to keep the stored one"),
    )

    space_url: str = Field(
        default="", description="This Space's address as the benchmark sees it"
    )
    chroma_host: str = Field(default="")
    chroma_port: int = Field(default=0, ge=0, le=65535)
    container: str = Field(default="")

    is_default: bool = False
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


class ConnectionSettings(BaseModel):
    """Connection-wide measurement settings, sent whole so cleared fields are cleared."""

    instrument: dict[str, Any] = Field(default_factory=dict)
    probe: dict[str, Any] = Field(default_factory=dict)


class ConnectionResponse(BaseModel):
    """A connection, without its key."""

    id: UUID
    name: str
    url: str
    has_token: bool

    space_url: str
    chroma_host: str
    chroma_port: int
    container: str

    instrument: dict[str, Any] = Field(default_factory=dict)
    probe: dict[str, Any] = Field(default_factory=dict)

    # The benchmark's cached self-description.
    reachable: bool = False
    detail: str = ""
    checked_at: datetime | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    fields: dict[str, Any] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)

    is_default: bool = False
    is_active: bool = True
    endpoints: int = Field(default=0, description="How many endpoints it measures")


class ProviderRole(BaseModel):
    """One provider role.

    Blank ``url`` means the benchmark's default, given in ``url_default``. The
    key is never returned, only whether it is set and when.
    """

    url: str = ""
    url_default: str = ""
    key_set: bool = False
    key_updated_at: datetime | None = None


class ProviderResponse(BaseModel):
    """The benchmark's provider slots: the shared default and one per role."""

    shared: ProviderRole = Field(default_factory=ProviderRole)
    generator: ProviderRole = Field(default_factory=ProviderRole)
    subject: ProviderRole = Field(default_factory=ProviderRole)
    judge: ProviderRole = Field(default_factory=ProviderRole)
    filter: ProviderRole = Field(
        default_factory=ProviderRole,
        description="The web check; blank fields take the models under test's",
    )


class ProviderUrls(BaseModel):
    """Provider URLs, sent whole so cleared fields are cleared."""

    ollama_url: str = ""
    generator_url: str = ""
    subject_url: str = ""
    judge_url: str = ""
    filter_url: str = ""


class ProviderCredential(BaseModel):
    """One provider key, set or cleared by name."""

    value: str = Field(..., min_length=1)


class TargetRequest(BaseModel):
    """Start measuring an endpoint, or change how it is measured."""

    connection_id: UUID | None = Field(
        default=None, description="Which benchmark; empty — the default one"
    )
    enabled: bool = True
    collection: str = Field(
        default="",
        description="Collection in the index; empty — resolved from the dataset",
    )
    probe: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Per-endpoint probe settings. Unset fields fall back to the "
            "connection's, then to the benchmark's defaults"
        ),
    )
    instrument: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Arms, blocks, judges, subject models and thresholds for this "
            "endpoint. Unset fields fall back to the connection's, then to "
            "the benchmark's defaults"
        ),
    )
    # The benchmark runs the schedule itself, in UTC.
    schedule: str = Field(
        default="",
        description="An interval such as 24h or 6h; empty — measure on request only",
    )
    schedule_at: str = Field(
        default="",
        description=(
            "Launch time, HH:MM UTC, for a daily interval; shorter intervals "
            "count from the previous launch"
        ),
    )


class JobResponse(BaseModel):
    """A benchmark job."""

    id: str
    state: str
    phase: str
    kind: str = "pipeline"
    # Passes done of planned; total 0 means not known yet.
    done: int = 0
    total: int = 0
    # The current pass and its progress in questions.
    arm: str = ""
    block: str = ""
    model: str = ""
    step_done: int = 0
    step_total: int = 0
    message: str = ""
    error: str = ""
    trigger: str = ""
    # The card built after measuring; None if nothing was graded.
    card: dict[str, Any] | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # The evaluation plan behind step_total; null until evaluation starts.
    progress_plan: dict[str, Any] | None = None


class TargetResponse(BaseModel):
    """This endpoint's benchmark settings and last job."""

    endpoint_slug: str
    measured: bool = Field(
        default=False,
        description=(
            "Whether this endpoint is opted into measuring. False is not a "
            "score of zero"
        ),
    )
    connection_id: UUID | None = None
    connection_name: str = ""
    enabled: bool = True
    collection: str = ""
    resolved_collection: str = Field(
        default="",
        description="What the collection resolves to when none was given",
    )
    probe: dict[str, Any] = Field(default_factory=dict)
    instrument: dict[str, Any] = Field(default_factory=dict)
    schedule: str = ""
    schedule_at: str = ""
    # Next scheduled run in UTC, as reported by the benchmark.
    next_run_at: datetime | None = None
    synced_at: datetime | None = None

    # Copied from the connection so the endpoint form needs no second request.
    fields: dict[str, Any] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(
        default_factory=dict,
        description="What the benchmark offers: arms, generators, models",
    )
    connection_probe: dict[str, Any] = Field(
        default_factory=dict,
        description="The Space-wide layer, shown as what this endpoint inherits",
    )
    connection_instrument: dict[str, Any] = Field(
        default_factory=dict,
        description="The Space-wide layer, shown as what this endpoint inherits",
    )

    last_job: JobResponse | None = None
    reachable: bool = False
    detail: str = ""


class WindowResponse(BaseModel):
    """Articles in the time window, counted by the benchmark's generation rule."""

    count: int = Field(0, description="Articles in the window, undated included")
    undated: int = Field(0, description="Articles with no date; generation keeps them")
    total: int = Field(0, description="Articles in the index")
    window_days: int = Field(0, description="The window in days; 0 means no window")


class CheckResponse(BaseModel):
    """Whether the benchmark can reach this endpoint's index and its HTTP API, separately."""

    ok: bool = False
    corpus: bool = False
    endpoint: bool = False
    transport: str = ""
    collection: str = ""
    available: list[str] = Field(
        default_factory=list, description="Collections the index actually holds"
    )
    chunks: int = 0
    usable: int = 0
    documents: int = 0
    response_type: str = ""
    blocked_arms: dict[str, str] = Field(default_factory=dict)
    problems: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    """Start a run."""

    generate: bool | None = Field(
        default=None,
        description="Rebuild the question set first; empty — as configured",
    )
    filter: bool | None = Field(
        default=None,
        description=("Filter the pending pairs; empty — follow `generate`"),
    )
    evaluate: bool | None = Field(
        default=None,
        description=("Ask and grade after the question set is built; empty — yes"),
    )
    defer_judging: bool = Field(
        default=False,
        description=("Collect answers without judging; verdicts stay pending"),
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description=("Questions per generator, for a trial run; noted on the card"),
    )
