"""Feedback API schemas for request/response models."""

from pydantic import BaseModel, Field


class CreateFeedbackRequest(BaseModel):
    """Request model for creating feedback."""

    category: str = Field(
        default="feedback",
        description="Category of feedback: bug, feedback, or idea",
    )
    description: str = Field(
        ..., min_length=1, description="Description of the issue or feedback"
    )
    page_url: str | None = Field(None, description="Current page route")
    app_version: str | None = Field(None, description="Application version")
    browser_info: str | None = Field(None, description="Browser user agent")


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    success: bool
    message: str
    ticket_id: str | None = Field(
        None, description="Linear issue identifier (e.g. TEAM-123)"
    )
