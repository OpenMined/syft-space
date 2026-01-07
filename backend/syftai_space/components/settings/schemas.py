"""Settings API schemas for request/response models."""

from pydantic import BaseModel, Field


class PublicUrlResponse(BaseModel):
    """Response model for public URL."""

    public_url: str | None = Field(None, description="Public URL for the server")


class UpdatePublicUrlRequest(BaseModel):
    """Request model for updating the public URL."""

    public_url: str = Field(..., description="New public URL to set")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "public_url": "https://my-server.example.com",
            }
        }
