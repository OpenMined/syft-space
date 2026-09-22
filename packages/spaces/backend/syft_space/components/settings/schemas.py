"""Settings API schemas for request/response models."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class PublicUrlResponse(BaseModel):
    """Response model for public URL."""

    public_url: str | None = Field(None, description="Public URL for the server")


class UpdatePublicUrlRequest(BaseModel):
    """Request model for updating the public URL."""

    public_url: HttpUrl = Field(..., description="New public URL to set")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "public_url": "https://my-server.example.com",
            }
        }


class ManagedResponse(BaseModel):
    """Response model for managed-mode status."""

    managed: bool = Field(
        ...,
        description="True when this space is run by a station "
        "(SYFT_CLUSTER_MANAGED_BY is set)",
    )
    public_url: str | None = Field(
        None, description="Public URL for the server (same value as /public-url)"
    )


class DiagnosticsResponse(BaseModel):
    """Response model for diagnostics preference."""

    enabled: bool = Field(False, description="Whether anonymous diagnostics is enabled")


class UpdateDiagnosticsRequest(BaseModel):
    """Request model for updating diagnostics preference."""

    enabled: bool = Field(..., description="Whether to enable anonymous diagnostics")


BENCHMARKS_MODES = ("off", "local")


class BenchmarksModeResponse(BaseModel):
    """Response model for the benchmark-reporting mode."""

    mode: str = Field(
        "off",
        description="How benchmark results are accepted: 'off' or 'local'",
    )


class UpdateBenchmarksModeRequest(BaseModel):
    """Request model for updating the benchmark-reporting mode."""

    mode: Literal["off", "local"] = Field(
        ...,
        description=(
            "'off' hides the reporting API entirely; 'local' accepts results "
            "from an authenticated caller on this Space"
        ),
    )


class ProxyStatusResponse(BaseModel):
    """Response model for proxy status."""

    connected: bool = Field(..., description="Whether the proxy tunnel is connected")
    public_url: str | None = Field(
        None, description="Public URL of the tunnel if connected"
    )
    has_token: bool = Field(False, description="Whether an ngrok token is configured")
