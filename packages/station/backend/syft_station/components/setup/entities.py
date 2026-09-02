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
    hub_pat: str = Field(
        default="",
        description=(
            "SyftHub API token used to verify buyers and register the "
            "satellite. One per station, not per wallet: any wallet's buyers "
            "verify against the same hub account"
        ),
    )
    hub_user_id: int | None = Field(
        default=None,
        description=(
            "SyftHub user id of the token's owner — published on paid "
            "endpoints as wallet_owner so the hub mints buyer tokens for it"
        ),
    )
    satellite_id: str = Field(
        default="",
        description=(
            "This station's satellite on SyftHub. Registered by hand because "
            "nothing heartbeats the station's origin"
        ),
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
