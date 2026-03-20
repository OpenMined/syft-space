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
    mpp_secret_key: str | None = Field(
        default=None, description="HMAC secret key for MPP challenge signing (auto-generated)"
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
