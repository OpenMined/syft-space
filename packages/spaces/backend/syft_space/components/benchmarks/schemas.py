"""What the benchmark pages send and receive.

Settings travel as open documents — ``dict[str, Any]`` — and that is the whole
design, not a shortcut. The Space stores what the owner set and hands it to the
benchmark; naming the fields here would mean a migration in this repository
every time the benchmark grows a knob, and a forgotten migration would mean a
form that silently cannot configure something that already works.

What *is* named here is everything the Space itself decides: which benchmark,
which endpoint, on or off, when. Those are the owner's answers, and they are
the Space's business.
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
        description=(
            "Control key. Omit to keep the stored one — the form is never told "
            "what it is, so it cannot send it back, and without this rule "
            "renaming a connection would silently revoke its access"
        ),
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
    """The two layers of settings the owner set for this benchmark.

    Sent whole, not patched: the form shows the settings as one document, and
    with a patch a cleared field would be indistinguishable from a field the
    form did not send — so clearing one would be impossible.
    """

    instrument: dict[str, Any] = Field(default_factory=dict)
    probe: dict[str, Any] = Field(default_factory=dict)


class ConnectionResponse(BaseModel):
    """A connection as the settings page sees it. Never carries the key."""

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

    # What the benchmark last told us about itself. Stale on purpose: a
    # benchmark that is down should not make this page unopenable.
    reachable: bool = False
    detail: str = ""
    checked_at: datetime | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    fields: dict[str, Any] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)

    is_default: bool = False
    is_active: bool = True
    endpoints: int = Field(default=0, description="How many endpoints it measures")


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
            "What differs for this endpoint. Unset fields fall back to the "
            "connection's, and those to the benchmark's own defaults"
        ),
    )
    # The benchmark watches these itself and measures without being asked.
    #
    # The hour is UTC, and the form is obliged to say so. The benchmark keeps
    # and fires it in UTC because a service in a container has no way of
    # knowing what the owner's night is, and one that took its own clock for it
    # would shift every schedule the day its host moved.
    schedule: str = Field(
        default="",
        description="An interval such as 24h or 6h; empty — measure on request only",
    )
    schedule_at: str = Field(
        default="",
        description=(
            "The hour of the launch, HH:MM, IN UTC. It applies to a daily "
            "interval; on a shorter one the step runs from the previous launch"
        ),
    )


class JobResponse(BaseModel):
    """A run in flight, or the last one that finished."""

    id: str
    state: str
    phase: str
    # Passes finished out of passes planned. Zero as the total means the scale
    # is not known yet, not that there is nothing to do.
    done: int = 0
    total: int = 0
    # What is running right now, and how far into itself it is. Two counts
    # rather than one: passes and the questions inside a pass are different
    # units, and merged into a single bar they misreport both.
    arm: str = ""
    block: str = ""
    model: str = ""
    step_done: int = 0
    step_total: int = 0
    message: str = ""
    error: str = ""
    trigger: str = ""
    # The card assembled after measuring, in the shape a marketplace is handed
    # — present whether or not this run was published. None until the job has
    # measured something to build one from, or when it never asked at all
    # (a launch that only refreshed the question set).
    card: dict[str, Any] | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TargetResponse(BaseModel):
    """How this endpoint is measured, and where its last run got to."""

    endpoint_slug: str
    measured: bool = Field(
        default=False,
        description=(
            "Whether this endpoint has been opted into measuring at all. False "
            "is not a score of zero and must never be rendered as one"
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
    schedule: str = ""
    schedule_at: str = ""
    # When the benchmark will next fire this schedule, in UTC. Asked of the
    # benchmark rather than worked out here: it is the one that decides, and
    # two computations of one moment part company on exactly the question this
    # is displayed to answer — "why has it not run yet".
    next_run_at: datetime | None = None
    synced_at: datetime | None = None

    # Copied from the connection so the endpoint page can draw its form without
    # a second request — it is the same form, with one layer more.
    fields: dict[str, Any] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)
    connection_probe: dict[str, Any] = Field(
        default_factory=dict,
        description="The Space-wide layer, shown as what this endpoint inherits",
    )

    last_job: JobResponse | None = None
    reachable: bool = False
    detail: str = ""


class CheckResponse(BaseModel):
    """Whether the benchmark can reach this endpoint's index and API.

    Both roads are reported separately because they are separate: the index is
    reached directly, the endpoint over HTTP, and one can work while the other
    does not. A single "available" flag would hide exactly the half that is
    missing.
    """

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
    """Measure now."""

    generate: bool | None = Field(
        default=None,
        description="Rebuild the question set first; empty — as configured",
    )
    evaluate: bool | None = Field(
        default=None,
        description=(
            "Ask and grade after the question set is built; empty — yes. Off "
            "for a launch that only wants the set refreshed and nothing asked "
            "against it yet"
        ),
    )
    publish: bool = Field(
        default=True, description="Hand the card over when the run finishes"
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Questions per generator, for a trial run. Publishing follows "
            "`publish` here too — the thin sample is named in the card rather "
            "than hidden"
        ),
    )
