"""Provisioner lifecycle manager for dataset provisioners."""

import asyncio

from loguru import logger

from syftai_space.components.datasets.entities import ProvisionerStatus
from syftai_space.components.datasets.handlers import DatasetHandler


class ProvisionerManager:
    """Lightweight manager for shared dataset provisioner lifecycle.

    Orchestrates startup and shutdown of provisioners based on ProvisionerState records.
    Key behavior:
    - Startup: Only starts provisioners that have at least one dataset attached
    - Shutdown: Stops all running provisioners
    - All business logic is delegated to DatasetHandler
    """

    def __init__(self, dataset_handler: DatasetHandler):
        """Initialize provisioner manager.

        Args:
            dataset_handler: Handler with provisioner business logic
        """
        self.dataset_handler = dataset_handler
        self._shutdown_event = asyncio.Event()
        self._startup_tasks: list[asyncio.Task] = []

    async def startup(self) -> None:
        """Start provisioners for all dtypes that have datasets attached (non-blocking).

        Only starts provisioners that have at least one dataset - orphaned
        provisioner states (with no datasets) are not started automatically.
        This method initiates startups but doesn't wait for them.
        """
        # Check if shutdown already initiated
        if self._shutdown_event.is_set():
            logger.warning(
                "⚠️  Shutdown already initiated, skipping provisioner startup"
            )
            return

        logger.info("🚀 Initiating shared provisioner startups...")

        # Get all provisioner states that have at least one dataset attached
        states = self.dataset_handler.get_all_provisioner_states_with_datasets()

        if not states:
            logger.info("No provisioner states with datasets found")
            return

        # Start each provisioner in background
        for state in states:
            task = asyncio.create_task(self._start_provisioner_async(state))
            # Add callback to remove task from list when it completes
            task.add_done_callback(self._remove_completed_task)
            self._startup_tasks.append(task)

        logger.info(
            f"Initiated {len(self._startup_tasks)} provisioner startup(s) in background "
            "(app will continue loading)"
        )

        # Don't wait - let them run in background
        # They will complete independently while app serves requests

    async def shutdown(self) -> None:
        """Stop all running provisioners gracefully (blocking).

        This method:
        1. Signals shutdown via event
        2. Cancels any ongoing startup tasks
        3. Stops all running provisioners
        4. Waits for all operations to complete
        """
        # Signal shutdown to prevent new startups
        self._shutdown_event.set()

        logger.info("🛑 Shutting down shared provisioners...")

        # Step 1: Cancel ongoing startup tasks
        if self._startup_tasks:
            logger.info(
                f"Cancelling {len(self._startup_tasks)} ongoing startup task(s)..."
            )
            for task in self._startup_tasks:
                if not task.done():
                    task.cancel()

            # Wait for cancellations to complete
            startup_results = await asyncio.gather(
                *self._startup_tasks, return_exceptions=True
            )

            # Log cancellation results
            cancelled_count = sum(
                1
                for r in startup_results
                if isinstance(r, asyncio.CancelledError)
                or (not isinstance(r, Exception))
            )
            logger.info(
                f"✅ Startup task cancellations complete: {cancelled_count} cancelled/completed"
            )

        # Step 2: Stop all running provisioners
        # Get all provisioner states with RUNNING status
        running_states = (
            self.dataset_handler.provisioner_state_repository.get_all_by_status(
                ProvisionerStatus.RUNNING
            )
        )

        if not running_states:
            logger.info("No running provisioners to shut down")
            self._startup_tasks.clear()
            return

        # Stop all provisioners concurrently
        stop_tasks = []
        for state in running_states:
            task = asyncio.create_task(self._stop_provisioner_async(state))
            stop_tasks.append(task)

        # Wait for all to complete
        stop_results = await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Log summary
        success_count = sum(1 for r in stop_results if not isinstance(r, Exception))
        failure_count = len(stop_results) - success_count

        logger.info(
            f"✅ Provisioner shutdown complete: "
            f"{success_count} succeeded, {failure_count} failed"
        )

        # Final cleanup: clear task list
        self._startup_tasks.clear()

    async def _start_provisioner_async(self, state) -> None:
        """Start a single provisioner asynchronously with cancellation support.

        Args:
            state: ProvisionerState entity

        Handles CancelledError by attempting cleanup of partially started provisioners.
        """
        try:
            # Run blocking provisioner start in thread pool
            await asyncio.to_thread(
                self.dataset_handler.start_provisioner_for_state, state
            )
        except asyncio.CancelledError:
            # Shutdown was called mid-startup - clean up partial resources
            logger.warning(
                f"⚠️  Startup cancelled for '{state.dtype}', attempting cleanup..."
            )
            try:
                # Best-effort cleanup: call stop to clean up any partial state
                await asyncio.to_thread(
                    self.dataset_handler.stop_provisioner_for_state, state
                )
                logger.info(f"✅ Cleanup successful for '{state.dtype}'")
            except Exception as e:
                logger.error(f"❌ Cleanup failed for '{state.dtype}': {e}")

            # Re-raise to signal cancellation completed
            raise
        except Exception as e:
            # Normal error during startup (already logged in handler)
            logger.error(f"❌ Provisioner startup failed for '{state.dtype}': {e}")

    def _remove_completed_task(self, task: asyncio.Task) -> None:
        """Remove a completed task from the startup tasks list.

        This callback is automatically invoked when a task completes (successfully,
        with error, or by cancellation). Keeps the task list clean and prevents
        memory leaks.

        Args:
            task: The completed asyncio Task
        """
        try:
            self._startup_tasks.remove(task)
            logger.debug(
                f"Removed completed task from tracking list "
                f"({len(self._startup_tasks)} active tasks remaining)"
            )
        except ValueError:
            # Task was already removed (e.g., during shutdown cleanup)
            pass

    async def _stop_provisioner_async(self, state) -> None:
        """Stop a single provisioner asynchronously.

        Args:
            state: ProvisionerState entity
        """
        try:
            # Run blocking provisioner stop in thread pool
            await asyncio.to_thread(
                self.dataset_handler.stop_provisioner_for_state, state
            )
        except Exception as e:
            # Error already logged in handler
            logger.error(f"❌ Provisioner shutdown failed for '{state.dtype}': {e}")
