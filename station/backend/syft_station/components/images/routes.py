"""Image catalog API routes."""

from fastapi import APIRouter, Depends, Query

from syft_station.components.auth.session import SessionUser, require_admin
from syft_station.components.images.handlers import ImageHandler
from syft_station.components.images.schemas import ImageTagResponse


def build_image_routes(handler: ImageHandler) -> APIRouter:
    """Build the image catalog routes."""
    router = APIRouter(prefix="/images", tags=["images"])

    def get_handler() -> ImageHandler:
        return handler

    @router.get("", response_model=list[ImageTagResponse])
    async def list_images(
        limit: int = Query(default=5, ge=1, le=25),
        refresh: bool = Query(
            default=False,
            description="Bypass the catalog TTL — pick up tags pushed moments ago",
        ),
        user: SessionUser = Depends(require_admin),
        handler: ImageHandler = Depends(get_handler),
    ) -> list[ImageTagResponse]:
        """Newest syft-space image tags from the registry (admin)."""
        return await handler.list_images(limit, refresh=refresh)

    return router
