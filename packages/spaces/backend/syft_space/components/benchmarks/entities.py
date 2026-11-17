"""Benchmark tables.

``benchmark_connections``: where a benchmark is, its key, and how it reaches
this Space. ``benchmark_targets``: one row per endpoint opted into measuring,
with its settings; no row means not measured. Questions, answers and corpus
text stay in the benchmark.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, UniqueConstraint
from sqlmodel import Column, Field, ForeignKey, SQLModel


class BenchmarkConnection(SQLModel, table=True):
    """A benchmark this Space is wired to."""

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
        description=("Key for the control API; the benchmark refuses calls without it"),
    )

    # How the benchmark reaches this Space: the API by URL, and the index
    # directly (ChromaDB port, or `docker exec` into the container).
    space_url: str = Field(
        default="",
        description="This Space's address as the benchmark sees it",
    )
    chroma_host: str = Field(default="", description="Index host as seen by benchmark")
    chroma_port: int = Field(
        default=0, description="0 — not published, use the container"
    )
    container: str = Field(default="", description="Container name, the fallback road")

    # The benchmark's cached self-description.
    capabilities: dict | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )
    defaults: dict | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
        description="Values unset settings take; shown as placeholders",
    )
    checked_at: datetime | None = Field(default=None)
    reachable: bool = Field(default=False)
    detail: str = Field(default="", description="Why the last check failed, if it did")

    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BenchmarkTarget(SQLModel, table=True):
    """An endpoint opted into measuring, with its own settings.

    ``probe`` and ``instrument`` are partial: unset fields take the benchmark's
    defaults.
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
        description="False pauses measuring; settings and history are kept",
    )
    collection: str = Field(
        default="",
        description=("Collection name in the index. Empty — resolved from the dataset"),
    )
    probe: dict | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
        description="How to question a node: dataset shape, search, answer limits",
    )
    instrument: dict | None = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True)),
        description="How to measure: arms, judges, subject models, thresholds",
    )

    schedule: str = Field(default="", description="Interval like 24h; empty — manual")
    schedule_at: str = Field(default="", description="Hour HH:MM, if fixed")

    # Last job seen, shown while the benchmark is unreachable.
    last_job: dict | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True))
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
