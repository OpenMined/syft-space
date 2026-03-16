"""Feedback API routes."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from loguru import logger

from syft_space.components.auth.public import public_route
from syft_space.components.feedback.handlers import FeedbackHandler
from syft_space.components.feedback.schemas import (
    CreateFeedbackRequest,
    FeedbackResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_feedback_routes(handler: FeedbackHandler) -> APIRouter:
    """Build the feedback routes."""
    router = APIRouter(prefix="/feedback", tags=["feedback"])

    def get_handler() -> FeedbackHandler:
        return handler

    @public_route
    @router.post("", response_model=FeedbackResponse)
    async def create_feedback(
        category: str = Form(default="feedback"),
        description: str = Form(...),
        page_url: str | None = Form(default=None),
        app_version: str | None = Form(default=None),
        browser_info: str | None = Form(default=None),
        screenshot: UploadFile | None = File(default=None),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: FeedbackHandler = Depends(get_handler),
    ) -> FeedbackResponse:
        """Submit feedback or bug report.

        Forwards to SyftHub which creates a Linear issue.
        """
        screenshot_bytes = None
        if screenshot:
            try:
                screenshot_bytes = await screenshot.read()
            except Exception as e:
                logger.warning(f"Failed to read screenshot upload: {e}")

        request = CreateFeedbackRequest(
            category=category,
            description=description,
            page_url=page_url,
            app_version=app_version,
            browser_info=browser_info,
        )

        return await handler.create_feedback(tenant.id, request, screenshot_bytes)

    return router
