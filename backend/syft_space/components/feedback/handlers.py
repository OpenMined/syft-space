"""Feedback handlers — forwards feedback to SyftHub which creates Linear issues."""

from __future__ import annotations

from uuid import UUID

import httpx
from loguru import logger

from syft_space.components.feedback.schemas import (
    CreateFeedbackRequest,
    FeedbackResponse,
)
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.shared.syfthub_client import SyftHubClient


class FeedbackHandler:
    """Handler that forwards feedback to SyftHub's /api/v1/feedback endpoint."""

    def __init__(self, marketplace_repository: MarketplaceRepository) -> None:
        self.marketplace_repository = marketplace_repository

    async def create_feedback(
        self,
        tenant_id: UUID,
        request: CreateFeedbackRequest,
        screenshot_bytes: bytes | None = None,
    ) -> FeedbackResponse:
        """Submit feedback via SyftHub's authenticated feedback proxy.

        Logs into the default marketplace and forwards the feedback
        to SyftHub, which holds the Linear credentials.
        """
        marketplace = await self.marketplace_repository.get_default(tenant_id)
        if not marketplace:
            logger.warning("No default marketplace configured for feedback")
            return FeedbackResponse(
                success=False,
                message="Marketplace not configured. Please connect to a marketplace first.",
            )

        try:
            async with SyftHubClient(str(marketplace.url)) as syfthub:
                await syfthub.login(marketplace.email, marketplace.password)

                # Build multipart form data
                data = {
                    "category": request.category,
                    "description": request.description,
                }
                if request.page_url:
                    data["page_url"] = request.page_url
                if request.app_version:
                    data["app_version"] = request.app_version
                if request.browser_info:
                    data["browser_info"] = request.browser_info

                files = None
                if screenshot_bytes:
                    files = {
                        "screenshot": (
                            "screenshot.png",
                            screenshot_bytes,
                            "image/png",
                        )
                    }

                # Use the authenticated client to POST to feedback endpoint
                response = await syfthub._client.post(
                    "/api/v1/feedback",
                    data=data,
                    files=files,
                    timeout=30.0,
                )

            result = response.json()

            if result.get("success"):
                ticket_id = result.get("ticket_id")
                logger.info(f"Feedback submitted successfully: {ticket_id}")
                return FeedbackResponse(
                    success=True,
                    message=result.get("message", "Thank you for your feedback!"),
                    ticket_id=ticket_id,
                )
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"SyftHub feedback endpoint returned error: {error_msg}")
                return FeedbackResponse(
                    success=False,
                    message="Failed to submit feedback. Please try again.",
                )

        except httpx.HTTPError as e:
            logger.error(f"Failed to reach SyftHub feedback service: {e}")
            return FeedbackResponse(
                success=False,
                message="Failed to submit feedback. Please try again.",
            )
        except Exception as e:
            logger.error(f"Unexpected error submitting feedback: {e}")
            return FeedbackResponse(
                success=False,
                message="Failed to submit feedback. Please try again.",
            )
