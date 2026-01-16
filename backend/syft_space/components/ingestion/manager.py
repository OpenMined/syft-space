"""Ingestion manager for watch-based file ingestion."""

import threading
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from syft_space.components.dataset_types.interfaces import IngestFile, IngestRequest
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.entities import Dataset
from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.ingestion.utils import rglob_visible
from syft_space.components.shared.domain_types import Context

if TYPE_CHECKING:
    from syft_space.components.datasets.repository import DatasetRepository


class DatasetFileEventHandler(FileSystemEventHandler):
    """Watchdog event handler for a specific dataset.

    Handles file system events and schedules ingestion jobs.
    Filters events by allowed file extensions.
    """

    def __init__(
        self,
        dataset_id: UUID,
        tenant_id: UUID,
        ingestion_manager: "IngestionManager",
    ):
        """Initialize the event handler.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            ingestion_manager: Parent IngestionManager for callbacks
        """
        super().__init__()
        self.dataset_id = dataset_id
        self.tenant_id = tenant_id
        self.ingestion_manager = ingestion_manager

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file created event.

        Only handles newly created files. We intentionally ignore:
        - on_modified: Fires multiple times during writes, fingerprint unreliable mid-write
        - on_moved: Complex edge cases (cross-filesystem = delete+create, same filesystem = moved)

        For re-ingestion of modified files, users can use the retry API or restart ingestion.
        """
        if event.is_directory:
            return

        src_path = Path(event.src_path)

        logger.debug(f"File created: {src_path}")
        self.ingestion_manager.schedule_file_job(
            self.dataset_id, self.tenant_id, src_path
        )

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deleted event.

        Cleans up the ingestion job record when a file is removed.
        """
        if event.is_directory:
            return

        src_path = Path(event.src_path)
        logger.debug(f"File deleted: {src_path}")
        self.ingestion_manager.handle_file_deleted(self.dataset_id, src_path)


class IngestionManager:
    """Manages file watchers and ingestion job processing.

    Lifecycle:
    - startup(): Start watchers for all IngestableDatasetType datasets
    - shutdown(): Stop all watchers and worker thread

    Processing:
    - Background worker thread processes pending jobs
    - Calls dataset_type.ingest() for each file
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

        # Worker thread for processing jobs
        self._worker_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._job_available_event = threading.Event()

        # Lock for thread-safe operations
        self._lock = threading.Lock()

    def _is_file_ingestable_dataset_type(self, dtype: str) -> bool:
        """Check if dataset type implements FileIngestableDatasetType.

        FileIngestableDatasetType extends IngestableDatasetType with:
        - watched_paths(): Returns list of paths to monitor
        """
        try:
            dataset_type_cls = self._registry.get_dataset_type(dtype)
            # Duck typing check for FileIngestableDatasetType protocol
            return (
                hasattr(dataset_type_cls, "ingest")
                and callable(getattr(dataset_type_cls, "ingest", None))
                and hasattr(dataset_type_cls, "watched_paths")
                and callable(getattr(dataset_type_cls, "watched_paths", None))
            )
        except KeyError:
            return False

    def _get_file_fingerprint(self, file_path: Path) -> tuple[int, int]:
        """Get file fingerprint (size, mtime_ns).

        Args:
            file_path: Path object

        Returns:
            Tuple of (file_size, mtime_ns)
        """
        stat = file_path.stat()
        return (stat.st_size, stat.st_mtime_ns)

    def _scan_existing_files(self, dataset: Dataset) -> int:
        """Scan existing files in dataset paths and create pending jobs.

        Uses FileIngestableDatasetType interface methods to get paths
        and allowed extensions, rather than hardcoding config keys.

        Args:
            dataset: Dataset entity

        Returns:
            Number of jobs created
        """
        # Instantiate dataset type to access interface methods
        dataset_type_cls = self._registry.get_dataset_type(dataset.dtype)
        dataset_type = dataset_type_cls(dataset.configuration)

        # Use interface methods instead of config keys
        file_paths = dataset_type.watched_paths()

        count = 0
        for path_str in file_paths:
            path = Path(path_str)
            if not path.exists():
                logger.warning(f"Path does not exist: {path_str}")
                continue

            if path.is_file():
                # Single file
                count += self._create_job_for_file(dataset.id, dataset.tenant_id, path)
            elif path.is_dir():
                # Directory - scan recursively
                for file_path in rglob_visible(path):
                    if file_path.is_file():
                        count += self._create_job_for_file(
                            dataset.id, dataset.tenant_id, file_path
                        )

        return count

    def _create_job_for_file(
        self, dataset_id: UUID, tenant_id: UUID, file_path: Path
    ) -> int:
        """Create ingestion job for a single file.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            file_path: Path object

        Returns:
            1 if job created/updated, 0 if skipped
        """
        try:
            file_size, file_mtime_ns = self._get_file_fingerprint(file_path)
            file_name = file_path.name

            self._ingestion_repository.upsert_by_path(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                file_path=str(file_path),
                file_name=file_name,
                file_size=file_size,
                file_mtime_ns=file_mtime_ns,
            )
            return 1
        except OSError as e:
            logger.warning(f"Failed to stat file {file_path}: {e}")
            return 0

    def schedule_file_job(
        self, dataset_id: UUID, tenant_id: UUID, file_path: Path
    ) -> None:
        """Schedule an ingestion job for a file (called by event handler).

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            file_path: Path object
        """
        logger.debug(f"Scheduling file job for {file_path}")
        self._create_job_for_file(dataset_id, tenant_id, file_path)
        # Signal worker that new job is available
        self._job_available_event.set()

    def handle_file_deleted(self, dataset_id: UUID, file_path: Path) -> None:
        """Handle file deletion (called by event handler).

        Args:
            dataset_id: Dataset UUID
            file_path: Path object
        """
        self._ingestion_repository.delete_by_path(dataset_id, str(file_path))

    def start_watcher(self, dataset: Dataset) -> bool:
        """Start file watcher for a dataset.

        Uses FileIngestableDatasetType interface methods to get paths
        and allowed extensions.

        Args:
            dataset: Dataset entity

        Returns:
            True if watcher started, False otherwise
        """
        if not self._is_file_ingestable_dataset_type(dataset.dtype):
            logger.debug(
                f"Dataset '{dataset.name}' type '{dataset.dtype}' does not support file ingestion, skipping watcher"
            )
            return False

        with self._lock:
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

            # Use interface methods instead of config keys
            file_paths = dataset_type.watched_paths()

            # Create event handler
            handler = DatasetFileEventHandler(
                dataset_id=dataset.id,
                tenant_id=dataset.tenant_id,
                ingestion_manager=self,
            )
            self._handlers[dataset.id] = handler

            # Schedule watches for each path
            watches = []
            for path_str in file_paths:
                path = Path(path_str)
                if not path.exists():
                    logger.warning(f"Cannot watch non-existent path: {path_str}")
                    continue

                # Watch directory containing the file, or the directory itself
                watch_path = str(path) if path.is_dir() else str(path.parent)
                recursive = path.is_dir()

                try:
                    watch = self._observer.schedule(
                        handler,
                        watch_path,
                        recursive=recursive,
                    )
                    watches.append(watch)
                    logger.info(
                        f"Started watching '{watch_path}' for dataset '{dataset.name}' (recursive={recursive})"
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
        with self._lock:
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
        with self._lock:
            return dataset_id in self._watches

    def _worker_loop(self) -> None:
        """Background worker loop for processing pending jobs."""
        logger.info("Ingestion worker started")

        while not self._shutdown_event.is_set():
            # Wait for job or shutdown (with timeout to check shutdown periodically)
            self._job_available_event.wait(timeout=5.0)
            self._job_available_event.clear()

            if self._shutdown_event.is_set():
                break

            # Process pending jobs
            self._process_pending_jobs()

        logger.info("Ingestion worker stopped")

    def _process_pending_jobs(self) -> None:
        """Process all pending ingestion jobs."""
        # Get pending jobs (batch)
        pending_jobs = self._ingestion_repository.get_pending_jobs(limit=50)

        if not pending_jobs:
            return

        logger.debug(f"Processing {len(pending_jobs)} pending ingestion jobs")

        for job in pending_jobs:
            if self._shutdown_event.is_set():
                break

            self._process_single_job(job)

    def _process_single_job(self, job: IngestionJob) -> None:
        """Process a single ingestion job.

        Args:
            job: IngestionJob to process
        """

        file_path = Path(job.file_path)
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.CANCELLED, "File does not exist"
            )
            return

        if not file_path.is_file():
            logger.warning(f"File is not a file: {file_path}")
            self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.CANCELLED, "File is not a file"
            )
            return

        logger.debug(f"Processing ingestion job {job.id} {file_path}")
        # Update status to IN_PROGRESS
        self._ingestion_repository.update_status(job.id, IngestionJobStatus.IN_PROGRESS)

        try:
            # Get dataset (internal - background worker has no tenant context)
            dataset = self._dataset_repository.get_by_id(job.dataset_id, job.tenant_id)
            if not dataset:
                logger.warning(f"Dataset not found for job {job.id}")
                self._ingestion_repository.update_status(
                    job.id, IngestionJobStatus.CANCELLED, "Dataset not found"
                )
                return

            # Verify fingerprint (file may have changed while queued)
            try:
                current_size, current_mtime = self._get_file_fingerprint(file_path)
            except OSError as e:
                logger.warning(f"Cannot stat file {file_path}: {e}")
                self._ingestion_repository.update_status(
                    job.id, IngestionJobStatus.FAILED, f"Cannot read file: {e}"
                )
                return

            if current_size != job.file_size or current_mtime != job.file_mtime_ns:
                # File changed, create new job with updated fingerprint
                logger.info(f"File changed during processing: {file_path}")
                self._ingestion_repository.upsert_by_path(
                    tenant_id=job.tenant_id,
                    dataset_id=job.dataset_id,
                    file_path=str(file_path),
                    file_name=job.file_name,
                    file_size=current_size,
                    file_mtime_ns=current_mtime,
                )
                self._ingestion_repository.update_status(
                    job.id,
                    IngestionJobStatus.CANCELLED,
                    "File changed during processing",
                )
                return

            # Get dataset type and call ingest
            dataset_type_cls = self._registry.get_dataset_type(dataset.dtype)
            dataset_type = dataset_type_cls(dataset.configuration)

            # Create IngestFile and IngestRequest
            with file_path.open("rb") as f:
                file_handle = BytesIO(f.read())

                # Detect content type from extension
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

                # Call ingest
                dataset_type.ingest(ctx, ingest_request)

            # Success
            self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.COMPLETED
            )
            logger.info(f"Successfully ingested: {job.file_path}")

        except Exception as e:
            logger.error(f"Failed to ingest {job.file_path}: {str(e)}")
            self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.FAILED, str(e)
            )

    async def startup(self) -> None:
        """Start the ingestion manager.

        Called during app startup:
        1. Start observer
        2. Start watchers for all FileIngestableDatasetType datasets
        3. Start worker thread
        """
        logger.info("Starting ingestion manager...")

        # Initialize observer
        self._observer = Observer()
        self._observer.start()

        # Get all datasets that have provisioner (i.e., local datasets that need watching)
        all_datasets = self._dataset_repository.get_all_with_provisioner_state_id()

        for dataset in all_datasets:
            if self._is_file_ingestable_dataset_type(dataset.dtype):
                # Scan existing files and create pending jobs
                job_count = self._scan_existing_files(dataset)
                logger.info(
                    f"Created {job_count} ingestion jobs for dataset '{dataset.name}'"
                )

                # Start watcher
                self.start_watcher(dataset)

                # Signal worker if jobs were created
                if job_count > 0:
                    self._job_available_event.set()

        # Start worker thread
        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="IngestionWorker",
            daemon=True,
        )
        self._worker_thread.start()

        logger.info("Ingestion manager started")

    async def shutdown(self) -> None:
        """Shutdown the ingestion manager.

        Called during app shutdown:
        1. Signal worker to stop
        2. Stop all watchers (unschedules watches)
        3. Stop observer
        """
        logger.info("Shutting down ingestion manager...")

        # Signal shutdown
        self._shutdown_event.set()
        self._job_available_event.set()  # Wake up worker

        # Wait for worker to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10.0)

        # Stop all watchers (unschedules all watches)
        # This is critical to prevent semaphore leaks on macOS where watchdog
        # uses multiprocessing internally
        if self._observer:
            # Iterate over a copy of keys since stop_watcher pops from _watches
            for dataset_id in list(self._watches.keys()):
                self.stop_watcher(dataset_id)

            # Stop observer after all watches are unscheduled
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        # Clear state (should already be empty, but ensure cleanup)
        self._watches.clear()
        self._handlers.clear()

        logger.info("Ingestion manager shutdown complete")

    def start_dataset_ingestion(self, dataset: Dataset) -> int:
        """Start ingestion for a dataset (manual trigger).

        Called when user starts ingestion via API.

        Args:
            dataset: Dataset entity

        Returns:
            Number of jobs created
        """
        if not self._is_file_ingestable_dataset_type(dataset.dtype):
            raise ValueError(
                f"Dataset type '{dataset.dtype}' does not support file-based ingestion"
            )

        # Scan existing files and create pending jobs
        job_count = self._scan_existing_files(dataset)
        logger.info(f"Created {job_count} ingestion jobs for dataset '{dataset.name}'")

        # Start watcher
        self.start_watcher(dataset)

        # Signal worker if jobs were created
        if job_count > 0:
            self._job_available_event.set()

        return job_count

    def stop_dataset_ingestion(self, dataset_id: UUID) -> int:
        """Stop ingestion for a dataset.

        Args:
            dataset_id: Dataset UUID

        Returns:
            Number of jobs cancelled
        """
        # Stop watcher
        self.stop_watcher(dataset_id)

        # Cancel pending jobs
        cancelled_count = self._ingestion_repository.cancel_pending_by_dataset(
            dataset_id
        )
        logger.info(
            f"Cancelled {cancelled_count} pending jobs for dataset {dataset_id}"
        )

        return cancelled_count

    def get_ingestion_stats(self, dataset_id: UUID, tenant_id: UUID) -> dict[str, int]:
        """Get aggregated job statistics for a dataset.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)

        Returns:
            Dict with counts per status and total
        """
        return self._ingestion_repository.get_stats_by_dataset(dataset_id, tenant_id)

    def get_ingestion_jobs(
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
        return self._ingestion_repository.get_by_dataset(
            dataset_id, tenant_id, status_filter, limit, offset
        )

    def retry_failed_jobs(self, dataset_id: UUID, tenant_id: UUID) -> int:
        """Reset all failed jobs to pending for retry.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID (for security)

        Returns:
            Number of jobs reset
        """
        jobs_reset = self._ingestion_repository.reset_failed_jobs(dataset_id, tenant_id)

        # Signal worker if jobs were reset
        if jobs_reset > 0:
            self._job_available_event.set()

        return jobs_reset

    def start_ingestion_by_id(self, dataset_id: UUID, tenant_id: UUID) -> int:
        """Start ingestion for a dataset by ID.

        Convenience method for auto-starting ingestion after dataset creation.
        Silently returns 0 if dataset not found or not a FileIngestableDatasetType.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
        Returns:
            Number of jobs created, or 0 if not applicable
        """
        dataset = self._dataset_repository.get_by_id(dataset_id, tenant_id)
        if not dataset:
            logger.warning(f"Dataset not found for ingestion: {dataset_id}")
            return 0

        if not self._is_file_ingestable_dataset_type(dataset.dtype):
            # Not a file-ingestable type, silently skip
            return 0

        return self.start_dataset_ingestion(dataset)
