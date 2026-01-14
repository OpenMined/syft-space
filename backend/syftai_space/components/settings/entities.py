"""Settings database entities."""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Settings(SQLModel, table=True):
    """Application settings entity - singleton row (id=1)."""

    __tablename__ = "settings"

    id: int = Field(default=1, primary_key=True)
    public_url: str | None = Field(
        default=None, description="Public URL for the SyftAI Space"
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
