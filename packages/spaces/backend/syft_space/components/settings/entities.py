"""Settings database entities."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Settings(SQLModel, table=True):
    """Application settings entity."""

    __tablename__ = "settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    public_url: str | None = Field(
        default=None, description="Public URL for the Syft Space"
    )
    ngrok_token: str | None = Field(
        default=None, description="Ngrok authentication token for proxy tunnel"
    )
    ngrok_domain: str | None = Field(
        default=None, description="Domain for ngrok tunnel"
    )
    diagnostics_enabled: bool = Field(
        default=False, description="Whether anonymous diagnostics sharing is enabled"
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# The singleton row's fixed id. Two concurrent first writes then collide on
# the primary key instead of leaving two rows behind, with reads picking one
# of them at random.
BENCHMARK_SETTINGS_ID = UUID("00000000-0000-0000-0000-000000000b01")


class BenchmarkSettings(SQLModel, table=True):
    """How this Space accepts benchmark cards.

    Its own row rather than another column on ``settings``: that row is already
    a grab bag of unrelated switches, and a feature that can be absent entirely
    is better off as a row that can be absent entirely. A Space that never
    turns benchmarking on never writes here, and reads back the default.

    Singleton and without a ``tenant_id``, matching ``settings`` — nothing in
    the path that reads this setting carries a tenant, and a column no query
    could fill would only promise a multi-tenancy that is not there.
    """

    __tablename__ = "benchmark_settings"

    id: UUID = Field(default=BENCHMARK_SETTINGS_ID, primary_key=True)
    # "off" (the default) means the reporting API is not there at all: a fresh
    # Space makes no calls to any marketplace on a benchmark's behalf, and
    # nothing reaching its API can be made to speak for its owner.
    #
    # A string rather than a bool because the ways a benchmark may be trusted
    # will multiply (a scoped token, a named remote runner); "local" is simply
    # the first of them.
    mode: str = Field(
        default="off",
        description=(
            "How benchmark results are accepted: 'off' (rejected) or "
            "'local' (accepted from an authenticated caller on this Space)"
        ),
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
