"""Provisioner lifecycle manager for dataset provisioners."""

import asyncio

from loguru import logger

from syftai_space.components.datasets.handlers import DatasetHandler


class ProvisionerManager:
    """Lightweight manager for shared dataset provisioner lifecycle.

    Manages startup and shutdown of dataset provisioners (e.g., Weaviate collections).
    All business logic is delegated to DatasetHandler.
    """

    def __init__(self, dataset_handler: DatasetHandler):
        """Initialize provisioner manager.

        Args:
            dataset_handler: Handler with provisioner business logic
        """
        self.dataset_handler = dataset_handler
        self._shutdown_event = asyncio.Event()

    async def startup(self) -> None:
        """Start all provisioners that have at least one dataset."""
        if self._shutdown_event.is_set():
            logger.warning("Shutdown already initiated, skipping startup")
            return

        logger.info("Starting shared provisioners...")
        try:
            await asyncio.to_thread(self.dataset_handler.startup_all_provisioners)
            logger.info("Provisioner startup complete")
        except Exception as e:
            logger.error(f"Error during provisioner startup: {e}")

    async def shutdown(self) -> None:
        """Stop all running provisioners gracefully."""
        self._shutdown_event.set()

        logger.info("Shutting down shared provisioners...")
        try:
            await asyncio.to_thread(self.dataset_handler.shutdown_all_provisioners)
            logger.info("Provisioner shutdown complete")
        except Exception as e:
            logger.error(f"Error during provisioner shutdown: {e}")
