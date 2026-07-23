"""Station settings database entities."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class StationConfig(SQLModel, table=True):
    """Singleton row holding the station's first-run configuration."""

    __tablename__ = "station_config"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    domain: str = Field(
        default="",
        description="Base domain for spaces (subdomain.<domain>); '' = not onboarded",
    )
    supported_version: str = Field(
        default="",
        description="The single syft-space version this station deploys",
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
