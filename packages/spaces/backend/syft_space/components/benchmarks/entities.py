"""Benchmark wiring: which benchmark measures this Space, and how.

A Space ships without a benchmark. Measuring is somebody else's job — a
separate service, run by whoever the owner trusts — and the Space's part is to
say *which* one, *how* it should measure, and *what* it is allowed to measure.

Two tables, because they answer two different questions.

``benchmark_connections`` is **where the benchmark lives and how it measures**.
Modelled on ``marketplaces``: an address, a key, a default flag. It also carries
the settings, and that is deliberate — settings that outlived the connection
they were written for would be settings for a benchmark that grades differently,
silently applied.

``benchmark_targets`` is **which endpoints are measured**. One row per endpoint
that opted in. Absent row means not measured, which is the honest default: a
Space that has not been asked to measure anything should measure nothing.

Nothing here stores questions, reference answers, or corpus text. The Space
never sees them — they live in the benchmark, and they quote the owner's
documents almost verbatim.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, UniqueConstraint
from sqlmodel import Column, Field, ForeignKey, SQLModel


class BenchmarkConnection(SQLModel, table=True):
    """A benchmark this Space is wired to, and the settings it measures with."""

    __tablename__ = "benchmark_connections"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    name: str = Field(..., description="What the owner calls this benchmark")
    url: str = Field(..., description="Base URL of the benchmark's control API")
    token: str = Field(
        default="",
        description=(
            "Key for the control API. The benchmark refuses everything without "
            "it — a run costs hours and money, so an open port would mean "
            "anyone who can reach the network can spend the owner's budget"
        ),
    )

    # How the benchmark reaches this Space. It needs two roads, and they are
    # different: the API by URL, and the index directly — ChromaDB's own port
    # or `docker exec` into the container. There is no route through this
    # Space's API for corpus text and there is not meant to be one.
    space_url: str = Field(
        default="",
        description="This Space's address as the benchmark sees it",
    )
    chroma_host: str = Field(default="", description="Index host as seen by benchmark")
    chroma_port: int = Field(
        default=0, description="0 — not published, use the container"
    )
    container: str = Field(default="", description="Container name, the fallback road")

    # What the owner set. Partial by design: unset means "the benchmark's own
    # default", and a full snapshot would freeze those defaults on the day the
    # connection was made.
    instrument: dict | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
        description="How to measure: arms, judges, subject models, thresholds",
    )
    probe: dict | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
        description="How to question a node: dataset shape, search, answer limits",
    )

    # What this installation can do, as it last told us. Cached so the settings
    # form can be drawn without a round trip, and stale on purpose: a benchmark
    # that is down should not make the page unopenable.
    capabilities: dict | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    fields: dict | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
        description="Shape of the settings fields, as the benchmark describes them",
    )
    defaults: dict | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
        description="What an unset setting turns into. Shown as placeholders",
    )
    checked_at: datetime | None = Field(default=None)
    reachable: bool = Field(default=False)
    detail: str = Field(default="", description="Why the last check failed, if it did")

    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BenchmarkTarget(SQLModel, table=True):
    """An endpoint this Space has opted into measuring, and how it differs.

    Separate from the endpoint row because it is optional and belongs to a
    different conversation: an endpoint exists to serve, and this table says
    whether anyone is also grading it.

    ``probe`` here is the third layer. Unset fields fall back to the
    connection's, and those to the benchmark's own defaults. Instrument is
    absent on purpose: judges, panel and thresholds are what the card declares
    in ``instrument``, and letting one endpoint use different ones would make
    two endpoints of the same Space quietly incomparable while the card still
    promised otherwise.
    """

    __tablename__ = "benchmark_targets"
    __table_args__ = (
        UniqueConstraint("endpoint_id", name="uq_benchmark_target_endpoint"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    endpoint_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("endpoints.id", ondelete="CASCADE")),
        description="The endpoint being measured",
    )
    connection_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("benchmark_connections.id", ondelete="SET NULL")),
        description="Which benchmark measures it; empty — the default one",
    )

    enabled: bool = Field(
        default=True,
        description="Paused rather than deleted: settings and history survive",
    )
    collection: str = Field(
        default="",
        description=(
            "Collection name in the index. Empty — resolved from the dataset. "
            "Stored because resolution can be wrong: the owner may have pointed "
            "the endpoint at a dataset whose collection is named by hand"
        ),
    )
    probe: dict | None = Field(default=None, sa_column=Column(JSON(none_as_null=True)))

    # Schedule lives per endpoint, not per Space: a news corpus wants nightly,
    # a manual kept for reference wants monthly, and one answer for both would
    # be wrong for one of them.
    schedule: str = Field(default="", description="Interval like 24h; empty — manual")
    schedule_at: str = Field(default="", description="Hour HH:MM, if fixed")

    # What the benchmark said last time we asked. A cached answer, so the page
    # opens while the benchmark is down, and plainly marked with its age.
    last_job: dict | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    synced_at: datetime | None = Field(
        default=None, description="When this target was last pushed to the benchmark"
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
