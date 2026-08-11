"""Image catalog handler — caching layer over the registry client."""

import asyncio
import time

from fastapi import HTTPException
from loguru import logger

from syft_station.components.images.registry import (
    ImageRegistryClient,
    RegistryError,
    ResolvedImage,
)
from syft_station.components.images.schemas import ImageTagResponse

# How long a fetched tag list stays fresh. Per-tag metadata is immutable and
# memoized forever; this TTL only bounds how quickly new tags show up.
_CACHE_TTL_SECONDS = 300.0


class ImageHandler:
    """Serves the newest image tags, cached so GHCR isn't hit per request."""

    def __init__(self, registry: ImageRegistryClient):
        self.registry = registry
        self._memo: dict[str, ResolvedImage] = {}
        self._catalog: list[ResolvedImage] = []  # last good result, newest first
        self._latest_digest: str | None = None
        self._has_result = False
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def list_images(
        self, limit: int, refresh: bool = False
    ) -> list[ImageTagResponse]:
        """The ``limit`` newest build tags, flagging the one ``latest`` matches.

        Refreshes from the registry when the cache has expired — or on
        ``refresh``, which bypasses the TTL (the per-tag memo makes that
        cheap: only tags never seen before cost registry requests). If a
        refresh fails but an earlier one succeeded, the stale catalog is
        served; with nothing cached at all the registry error surfaces as
        a 502.
        """
        async with self._lock:
            if refresh or time.monotonic() >= self._expires_at:
                await self._refresh()
        return [
            ImageTagResponse(
                tag=image.tag,
                created=image.created,
                revision=image.revision,
                is_latest=(
                    self._latest_digest is not None
                    and image.digest == self._latest_digest
                ),
            )
            for image in self._catalog[:limit]
        ]

    async def _refresh(self) -> None:
        try:
            resolved, latest_digest = await self.registry.fetch_catalog(self._memo)
        except RegistryError as e:
            if not self._has_result:
                raise HTTPException(
                    status_code=502, detail=f"Image registry is unreachable: {e}"
                ) from e
            logger.warning(f"Image catalog refresh failed, serving cached list: {e}")
            return
        self._memo = {image.tag: image for image in resolved}
        self._catalog = sorted(resolved, key=lambda i: i.created, reverse=True)
        self._latest_digest = latest_digest
        self._has_result = True
        self._expires_at = time.monotonic() + _CACHE_TTL_SECONDS
