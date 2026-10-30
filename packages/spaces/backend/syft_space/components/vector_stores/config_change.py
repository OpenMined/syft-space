"""Reaction of the vector-store layer to a dataset configuration edit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from syft_space.components.shared import client_cache

if TYPE_CHECKING:
    from syft_space.components.datasets.events import DatasetConfigurationChanged

__all__ = ["ClientCacheEvictor"]


class ClientCacheEvictor:
    """Drops the cached client of a connection that an edit replaced.

    The cache is keyed by ``connection_fields``, so the new connection gets
    a fresh client on first use either way; this closes the old one instead
    of leaving it open until shutdown.
    """

    async def on_configuration_changed(
        self, event: DatasetConfigurationChanged
    ) -> None:
        if not event.vector_store.changed:
            return
        store_cls = event.vector_store_cls
        try:
            old = store_cls(event.vector_store.old)
            new = store_cls(event.vector_store.new)
            if old.client_key() == new.client_key():
                return
            await client_cache.evict(store_cls.NAME, old.client_key())
        except Exception as e:
            logger.warning(
                f"Could not evict the old client of dataset '{event.dataset.name}': {e}"
            )
