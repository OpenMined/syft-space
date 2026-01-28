"""Provisioner lifecycle manager for dataset provisioners."""

import asyncio

from loguru import logger

from syft_space.components.datasets.handlers import DatasetHandler
from syft_space.components.shared.lifecycle import LifecycleService


class ProvisionerManager(LifecycleService):
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
        self._shutdown_event: asyncio.Event | None = None  # Initialized in startup()
        self._startup_complete_event: asyncio.Event | None = None  # Set by main.py

    def set_startup_complete_event(self, event: asyncio.Event) -> None:
        """Set the event to signal when startup is complete.

        Args:
            event: Event to set when provisioner startup finishes
        """
        self._startup_complete_event = event

    async def startup(self) -> None:
        """Start all provisioners that have at least one dataset."""
        # Initialize async primitives in async context (not in __init__)
        self._shutdown_event = asyncio.Event()

        logger.info("Starting shared provisioners in background...")
        # Fire-and-forget: Start provisioners without blocking server startup
        asyncio.create_task(self._startup_provisioners_background())

    async def _startup_provisioners_background(self) -> None:
        """Background task to start all provisioners."""
        try:
            await self.dataset_handler.startup_all_provisioners()
            logger.info("Provisioner startup complete")
        except Exception as e:
            logger.error(f"Error during provisioner startup: {e}")
        finally:
            # Signal that provisioner startup is done (success or failure)
            # This allows ingestion to proceed even if provisioners failed
            if self._startup_complete_event:
                self._startup_complete_event.set()

    async def shutdown(self) -> None:
        """Stop all running provisioners gracefully."""
        if self._shutdown_event:
            self._shutdown_event.set()

        logger.info("Shutting down shared provisioners...")
        try:
            await self.dataset_handler.shutdown_all_provisioners()
            logger.info("Provisioner shutdown complete")
        except Exception as e:
            logger.error(f"Error during provisioner shutdown: {e}")
