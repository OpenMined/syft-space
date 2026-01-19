"""Ingestion manager for watch-based file ingestion.

Architecture:
- Uses EventBridge for sync→async bridging between watchdog and async processing
- DatasetFileEventHandler (sync) pushes events via EventBridge.push_created/push_deleted
- Event processor task (async) consumes via EventBridge.pop()
- Job processor task (async) processes pending ingestion jobs
"""

import asyncio
from io import BytesIO
from pathlib import Path as SyncPath
from typing import TYPE_CHECKING
from uuid import UUID

import aiofiles
import janus
from anyio import Path as AsyncPath
from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from syft_space.components.dataset_types.interfaces import IngestFile, IngestRequest
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.entities import Dataset
from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.event_bridge import EventBridge
from syft_space.components.ingestion.events import FileEvent, FileEventType
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.ingestion.utils import rglob_visible
from syft_space.components.shared.domain_types import Context
from syft_space.components.shared.lifecycle import LifecycleService

if TYPE_CHECKING:
    from syft_space.components.datasets.repository import DatasetRepository


class DatasetFileEventHandler(FileSystemEventHandler):
    """Watchdog event handler that pushes events via EventBridge.

    Decoupled from IngestionManager:
    - Only knows about EventBridge (producer interface)
    - No callbacks, no manager reference, no async knowledge
    """

    def __init__(
        self,
        dataset_id: UUID,
        tenant_id: UUID,
        event_bridge: EventBridge,
    ):
        """Initialize the event handler.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            event_bridge: EventBridge for pushing events
        """
        super().__init__()
        self.dataset_id = dataset_id
        self.tenant_id = tenant_id
        self._bridge = event_bridge

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file created event."""
        if event.is_directory:
            return

        file_path = SyncPath(event.src_path)
        try:
            # Stat is sync - that's fine, we're in watchdog's thread
            stat = file_path.stat()
            self._bridge.push_created(
                dataset_id=self.dataset_id,
                tenant_id=self.tenant_id,
                file_path=file_path,
                file_size=stat.st_size,
                file_mtime_ns=stat.st_mtime_ns,
            )
        except OSError as e:
            logger.warning(f"Failed to stat file {file_path}: {e}")

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deleted event."""
        if event.is_directory:
            return

        file_path = SyncPath(event.src_path)
        self._bridge.push_deleted(
            dataset_id=self.dataset_id,
            tenant_id=self.tenant_id,
            file_path=file_path,
        )


class IngestionManager(LifecycleService):
    """Manages file watchers and ingestion job processing.

    Architecture:
    - EventBridge bridges sync watchdog callbacks to async processing
    - Event processor task consumes file events and creates DB records
    - Job processor task processes pending ingestion jobs

    Lifecycle:
    - startup(): Initialize EventBridge, start tasks, start watchers
    - shutdown(): Stop watchers, cancel tasks, close EventBridge
    """

    def __init__(
        self,
        dataset_repository: "DatasetRepository",
        ingestion_repository: IngestionJobRepository,
        registry: DatasetTypeRegistry,
    ):
        """Initialize the ingestion manager.

        Args:
            dataset_repository: Dataset repository (read-only access)
            ingestion_repository: Ingestion job repository
            registry: Dataset type registry
        """
        self._dataset_repository = dataset_repository
        self._ingestion_repository = ingestion_repository
        self._registry = registry

        # Watchdog observer (single observer manages all watches)
        self._observer: Observer | None = None

        # Track watches per dataset: dataset_id -> list of watch objects
        self._watches: dict[UUID, list] = {}

        # Track event handlers per dataset
        self._handlers: dict[UUID, DatasetFileEventHandler] = {}

        # EventBridge for sync→async communication - initialized in startup()
        self._event_bridge: EventBridge | None = None

        # Async primitives - initialized in startup()
        self._shutdown_event: asyncio.Event | None = None
        self._job_signal: asyncio.Event | None = None
        self._event_processor_task: asyncio.Task | None = None
        self._job_processor_task: asyncio.Task | None = None
        self._startup_init_task: asyncio.Task | None = None

    def _is_file_ingestable_dataset_type(self, dtype: str) -> bool:
        """Check if dataset type implements FileIngestableDatasetType."""
        try:
            dataset_type_cls = self._registry.get_dataset_type(dtype)
            return (
                hasattr(dataset_type_cls, "ingest")
                and callable(getattr(dataset_type_cls, "ingest", None))
                and hasattr(dataset_type_cls, "watched_paths")
                and callable(getattr(dataset_type_cls, "watched_paths", None))
            )
        except KeyError:
            return False

    # -------------------------------------------------------------------------
    # Lifecycle Methods
    # -------------------------------------------------------------------------

    async def startup(self) -> None:
        """Start the ingestion manager (fully async)."""
        logger.info("Starting ingestion manager...")

        # Initialize EventBridge for sync→async bridging
        self._event_bridge = EventBridge()
        await self._event_bridge.initialize()

        # Initialize async primitives
        self._shutdown_event = asyncio.Event()
        self._job_signal = asyncio.Event()

        # Start watchdog observer
        self._observer = Observer()
        self._observer.start()

        # Start event processor task (consumes from queue)
        self._event_processor_task = asyncio.create_task(
            self._event_processor_loop(), name="IngestionEventProcessor"
        )

        # Start job processor task (processes DB jobs)
        self._job_processor_task = asyncio.create_task(
            self._job_processor_loop(), name="IngestionJobProcessor"
        )

        # Start watchers for existing datasets in background (non-blocking)
        # This allows the server to start serving requests immediately
        self._startup_init_task = asyncio.create_task(
            self._start_existing_dataset_watchers(),
            name="IngestionStartupInit",
        )

        logger.info("Ingestion manager started")

    async def _start_existing_dataset_watchers(self) -> None:
        """Start watchers for existing datasets (runs in background).

        This runs as a fire-and-forget task so startup() completes immediately,
        allowing the FastAPI lifespan to yield and the server to start serving.
        """
        try:
            all_datasets = (
                await self._dataset_repository.get_all_with_provisioner_state_id()
            )
            for dataset in all_datasets:
                if self._is_file_ingestable_dataset_type(dataset.dtype):
                    try:
                        await self.start_dataset_ingestion(dataset)
                    except Exception as e:
                        logger.error(
                            f"Failed to start ingestion for '{dataset.name}': {e}"
                        )
            logger.info(
                f"Background: Started ingestion for {len(all_datasets)} datasets"
            )
        except Exception as e:
            logger.error(f"Failed to start existing dataset watchers: {e}")

    async def shutdown(self) -> None:
        """Shutdown the ingestion manager."""
        logger.info("Shutting down ingestion manager...")

        # Signal shutdown first
        if self._shutdown_event:
            self._shutdown_event.set()
        if self._job_signal:
            self._job_signal.set()  # Wake up job processor

        # Stop all watchers (stops producing events)
        for dataset_id in list(self._watches.keys()):
            self.stop_watcher(dataset_id)

        # Stop observer
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        # Close EventBridge BEFORE cancelling tasks
        # This unblocks any tasks waiting on pop() cleanly
        if self._event_bridge:
            await self._event_bridge.close()
            self._event_bridge = None

        # Cancel and await all async tasks
        all_tasks = [
            self._event_processor_task,
            self._job_processor_task,
            self._startup_init_task,
        ]
        for task in all_tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._watches.clear()
        self._handlers.clear()

        logger.info("Ingestion manager shutdown complete")

    # -------------------------------------------------------------------------
    # Event Processing (Async Tasks)
    # -------------------------------------------------------------------------

    async def _event_processor_loop(self) -> None:
        """Process file events from the EventBridge."""
        logger.info("Event processor started")

        while not self._shutdown_event.is_set():
            try:
                # Get event from EventBridge
                event = await self._event_bridge.pop(timeout=1.0)
                if event:
                    await self._process_file_event(event)

            except asyncio.CancelledError:
                break
            except janus.AsyncQueueShutDown:
                # Queue was closed during shutdown
                break
            except Exception as e:
                logger.error(f"Error processing file event: {e}")

        logger.info("Event processor stopped")

    async def _process_file_event(self, event: FileEvent) -> None:
        """Process a single file event."""
        if event.event_type == FileEventType.CREATED:
            await self._ingestion_repository.upsert_by_path(
                tenant_id=event.tenant_id,
                dataset_id=event.dataset_id,
                file_path=str(event.file_path),
                file_name=event.file_path.name,
                file_size=event.file_size,
                file_mtime_ns=event.file_mtime_ns,
            )
            # Signal job processor that new work is available
            self._job_signal.set()

        elif event.event_type == FileEventType.DELETED:
            await self._ingestion_repository.delete_by_path(
                event.dataset_id, str(event.file_path)
            )

    async def _job_processor_loop(self) -> None:
        """Process pending ingestion jobs (native async)."""
        logger.info("Job processor started")

        while not self._shutdown_event.is_set():
            try:
                # Wait for signal or periodic check
                await asyncio.wait_for(self._job_signal.wait(), timeout=5.0)
                self._job_signal.clear()
            except asyncio.TimeoutError:
                pass  # Periodic check for pending jobs

            if self._shutdown_event.is_set():
                break

            await self._process_pending_jobs()

        logger.info("Job processor stopped")

    async def _process_pending_jobs(self) -> None:
        """Process batch of pending jobs."""
        pending_jobs = await self._ingestion_repository.get_pending_jobs(limit=50)

        if not pending_jobs:
            return

        logger.debug(f"Processing {len(pending_jobs)} pending ingestion jobs")

        for job in pending_jobs:
            if self._shutdown_event.is_set():
                break
            await self._process_single_job(job)

    async def _process_single_job(self, job: IngestionJob) -> None:
        """Process a single ingestion job (fully async)."""
        file_path = AsyncPath(job.file_path)

        # Check file exists
        exists = await file_path.exists()
        if not exists:
            logger.warning(f"File does not exist: {file_path}")
            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.CANCELLED, "File does not exist"
            )
            return

        # Check is file
        is_file = await file_path.is_file()
        if not is_file:
            logger.warning(f"Path is not a file: {file_path}")
            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.CANCELLED, "Path is not a file"
            )
            return

        logger.debug(f"Processing ingestion job {job.id}: {file_path}")
        await self._ingestion_repository.update_status(
            job.id, IngestionJobStatus.IN_PROGRESS
        )

        try:
            # Get dataset
            dataset = await self._dataset_repository.get_by_id(
                job.dataset_id, job.tenant_id
            )
            if not dataset:
                logger.warning(f"Dataset not found for job {job.id}")
                await self._ingestion_repository.update_status(
                    job.id, IngestionJobStatus.CANCELLED, "Dataset not found"
                )
                return

            # Verify fingerprint (file may have changed while queued)
            try:
                stat = await file_path.stat()
                current_size, current_mtime = stat.st_size, stat.st_mtime_ns
            except OSError as e:
                logger.warning(f"Cannot stat file {file_path}: {e}")
                await self._ingestion_repository.update_status(
                    job.id, IngestionJobStatus.FAILED, f"Cannot read file: {e}"
                )
                return

            if current_size != job.file_size or current_mtime != job.file_mtime_ns:
                # File changed, create new job with updated fingerprint
                logger.info(f"File changed during processing: {file_path}")
                await self._ingestion_repository.upsert_by_path(
                    tenant_id=job.tenant_id,
                    dataset_id=job.dataset_id,
                    file_path=str(file_path),
                    file_name=job.file_name,
                    file_size=current_size,
                    file_mtime_ns=current_mtime,
                )
                await self._ingestion_repository.update_status(
                    job.id,
                    IngestionJobStatus.CANCELLED,
                    "File changed during processing",
                )
                return

            # Read file
            async with aiofiles.open(file_path, "rb") as file:
                file_handle = BytesIO(await file.read())

            # Get dataset type and call ingest
            dataset_type_cls = self._registry.get_dataset_type(dataset.dtype)
            dataset_type = dataset_type_cls(dataset.configuration)

            # Create IngestFile and IngestRequest
            ext = file_path.suffix.lower()

            ingest_file = IngestFile(
                file_handle=file_handle,
                filename=job.file_name,
                content_type=ext,
                file_size=job.file_size,
                metadata={
                    "dataset_id": dataset.id,
                    "file_path": str(file_path),
                },
            )

            ingest_request = IngestRequest(files=[ingest_file])

            # Create context (use system context for background ingestion)
            ctx = Context(sender="system@openmined.org")

            # Call ingest (native async)
            await dataset_type.ingest(ctx, ingest_request)

            # Success
            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.COMPLETED
            )
            logger.info(f"Successfully ingested: {job.file_path}")

        except Exception as e:
            logger.error(f"Failed to ingest {job.file_path}: {str(e)}")
            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.FAILED, str(e)
            )

    # -------------------------------------------------------------------------
    # Watcher Management
    # -------------------------------------------------------------------------

    async def _start_watcher(self, dataset: Dataset) -> bool:
        """Start file watcher for a dataset.

        Args:
            dataset: Dataset entity

        Returns:
            True if watcher started, False otherwise
        """
        if not self._is_file_ingestable_dataset_type(dataset.dtype):
            logger.debug(
                f"Dataset '{dataset.name}' type '{dataset.dtype}' does not support "
                "file ingestion, skipping watcher"
            )
            return False

        # Skip if already watching
        if dataset.id in self._watches:
            logger.debug(f"Watcher already running for dataset '{dataset.name}'")
            return True

        # Ensure observer is running
        if self._observer is None:
            self._observer = Observer()
            self._observer.start()

        # Instantiate dataset type to access interface methods
        dataset_type_cls = self._registry.get_dataset_type(dataset.dtype)
        dataset_type = dataset_type_cls(dataset.configuration)

        # Use interface methods to get watched paths
        file_paths = dataset_type.watched_paths()

        # Create handler with EventBridge
        handler = DatasetFileEventHandler(
            dataset_id=dataset.id,
            tenant_id=dataset.tenant_id,
            event_bridge=self._event_bridge,
        )
        self._handlers[dataset.id] = handler

        # Schedule watches for each path
        watches = []
        for path_str in file_paths:
            path = AsyncPath(path_str)
            if not await path.exists():
                logger.warning(f"Cannot watch non-existent path: {path_str}")
                continue

            # Watch directory containing the file, or the directory itself
            watch_path = str(path) if await path.is_dir() else str(await path.parent)
            recursive = await path.is_dir()

            try:
                watch = self._observer.schedule(
                    handler,
                    watch_path,
                    recursive=recursive,
                )
                watches.append(watch)
                logger.info(
                    f"Started watching '{watch_path}' for dataset '{dataset.name}' "
                    f"(recursive={recursive})"
                )
            except Exception as e:
                logger.error(f"Failed to watch path {watch_path}: {e}")

        self._watches[dataset.id] = watches
        return True

    def stop_watcher(self, dataset_id: UUID) -> None:
        """Stop file watcher for a dataset.

        Args:
            dataset_id: Dataset UUID
        """
        watches = self._watches.pop(dataset_id, [])
        self._handlers.pop(dataset_id, None)

        if self._observer and watches:
            for watch in watches:
                try:
                    self._observer.unschedule(watch)
                except Exception as e:
                    logger.warning(f"Error unscheduling watch: {e}")

    def is_watching(self, dataset_id: UUID) -> bool:
        """Check if a dataset is being watched.

        Args:
            dataset_id: Dataset UUID

        Returns:
            True if watching, False otherwise
        """
        return dataset_id in self._watches

    # -------------------------------------------------------------------------
    # Public API Methods
    # -------------------------------------------------------------------------

    async def start_dataset_ingestion(self, dataset: Dataset) -> int:
        """Start ingestion for a dataset (fully async).

        Args:
            dataset: Dataset entity

        Returns:
            Number of files queued for ingestion
        """
        if not self._is_file_ingestable_dataset_type(dataset.dtype):
            raise ValueError(
                f"Dataset type '{dataset.dtype}' does not support file-based ingestion"
            )

        # Scan files
        events = await self._scan_files(dataset)

        # Push events via EventBridge
        for event in events:
            await self._event_bridge.push_async(event)

        # Start watcher
        await self._start_watcher(dataset)

        logger.info(f"Queued {len(events)} files for dataset '{dataset.name}'")
        return len(events)

    async def _scan_files(self, dataset: Dataset) -> list[FileEvent]:
        """Scan files.

        Args:
            dataset: Dataset entity

        Returns:
            List of FileEvent objects for found files
        """
        events = []
        dataset_type_cls = self._registry.get_dataset_type(dataset.dtype)
        dataset_type = dataset_type_cls(dataset.configuration)

        for path_str in dataset_type.watched_paths():
            path = AsyncPath(path_str)
            if not await path.exists():
                logger.warning(f"Path does not exist: {path_str}")
                continue

            is_file = await path.is_file()
            files = (
                [path]
                if is_file
                else [file_path async for file_path in rglob_visible(path)]
            )

            for file_path in files:
                if not await file_path.is_file():
                    continue
                try:
                    stat = await file_path.stat()
                    events.append(
                        EventBridge.create_event(
                            event_type=FileEventType.CREATED,
                            dataset_id=dataset.id,
                            tenant_id=dataset.tenant_id,
                            file_path=file_path,
                            file_size=stat.st_size,
                            file_mtime_ns=stat.st_mtime_ns,
                        )
                    )
                except OSError:
                    pass

        return events

    async def stop_dataset_ingestion(self, dataset_id: UUID) -> int:
        """Stop ingestion for a dataset.

        Args:
            dataset_id: Dataset UUID

        Returns:
            Number of jobs cancelled
        """
        # Stop watcher
        self.stop_watcher(dataset_id)

        # Cancel pending jobs
        cancelled_count = await self._ingestion_repository.cancel_pending_by_dataset(
            dataset_id
        )
        logger.info(
            f"Cancelled {cancelled_count} pending jobs for dataset {dataset_id}"
        )

        return cancelled_count

    async def get_ingestion_stats(
        self, dataset_id: UUID, tenant_id: UUID
    ) -> dict[str, int]:
        """Get aggregated job statistics for a dataset.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)

        Returns:
            Dict with counts per status and total
        """
        return await self._ingestion_repository.get_stats_by_dataset(
            dataset_id, tenant_id
        )

    async def get_ingestion_jobs(
        self,
        dataset_id: UUID,
        tenant_id: UUID,
        status_filter: list[IngestionJobStatus] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[IngestionJob]:
        """Get ingestion jobs for a dataset.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)
            status_filter: Optional list of IngestionJobStatus enums to filter by
            limit: Maximum jobs to return
            offset: Pagination offset

        Returns:
            List of IngestionJob entities
        """
        return await self._ingestion_repository.get_by_dataset(
            dataset_id, tenant_id, status_filter, limit, offset
        )

    async def retry_failed_jobs(self, dataset_id: UUID, tenant_id: UUID) -> int:
        """Reset all failed jobs to pending for retry.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)

        Returns:
            Number of jobs reset
        """
        jobs_reset = await self._ingestion_repository.reset_failed_jobs(
            dataset_id, tenant_id
        )

        # Signal job processor if jobs were reset
        if jobs_reset > 0:
            self._job_signal.set()

        return jobs_reset

    async def start_ingestion_by_id(self, dataset_id: UUID, tenant_id: UUID) -> int:
        """Start ingestion for a dataset by ID.

        Convenience method for auto-starting ingestion after dataset creation.
        Silently returns 0 if dataset not found or not a FileIngestableDatasetType.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID

        Returns:
            Number of jobs created, or 0 if not applicable
        """
        dataset = await self._dataset_repository.get_by_id(dataset_id, tenant_id)
        if not dataset:
            logger.warning(f"Dataset not found for ingestion: {dataset_id}")
            return 0

        if not self._is_file_ingestable_dataset_type(dataset.dtype):
            # Not a file-ingestable type, silently skip
            return 0

        return await self.start_dataset_ingestion(dataset)
