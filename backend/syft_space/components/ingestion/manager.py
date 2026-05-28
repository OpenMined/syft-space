"""Source-agnostic ingestion orchestrator.

For each dataset whose dataset_type exposes a ``source`` attribute, spawn
a long-running task that iterates ``source.change_stream()`` and writes
``IngestionJob`` rows. A separate job processor task picks up pending
jobs, fetches their content via the source, and delegates to the
dataset_type's ``ingest()`` method.

Filesystem watching, sync→async bridging, and observer ownership all
live inside the source (and the shared ``LocalFileWatcher``); the
manager treats every source uniformly.
"""

import asyncio
import json
from pathlib import Path as SyncPath
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from syft_space.components.dataset_types.interfaces import (
    IngestContext,
    IngestRequest,
)
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.entities import Dataset
from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.shared.lifecycle import LifecycleService
from syft_space.components.sources.interfaces import BaseSource, SourceChangeEvent

if TYPE_CHECKING:
    from syft_space.components.datasets.repository import DatasetRepository


class IngestionManager(LifecycleService):
    """Manages per-dataset source consumer tasks and the shared job processor."""

    def __init__(
        self,
        dataset_repository: "DatasetRepository",
        ingestion_repository: IngestionJobRepository,
        registry: DatasetTypeRegistry,
    ):
        self._dataset_repository = dataset_repository
        self._ingestion_repository = ingestion_repository
        self._registry = registry

        # Per-dataset state
        self._sources: dict[UUID, BaseSource] = {}
        self._source_tasks: dict[UUID, asyncio.Task] = {}

        # Async primitives — initialized in startup()
        self._shutdown_event: asyncio.Event | None = None
        self._job_signal: asyncio.Event | None = None
        self._job_processor_task: asyncio.Task | None = None
        self._startup_init_task: asyncio.Task | None = None
        self._provisioner_ready_event: asyncio.Event | None = None

    def set_provisioner_ready_event(self, event: asyncio.Event) -> None:
        self._provisioner_ready_event = event

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _build_dataset_type(self, dataset: Dataset):
        dataset_type_cls = self._registry.get_dataset_type(dataset.dtype)
        return dataset_type_cls(dataset.configuration)

    def _has_source(self, dataset: Dataset) -> bool:
        """Whether this dataset's binding exposes a ``BaseSource`` instance."""
        try:
            dataset_type = self._build_dataset_type(dataset)
        except Exception as e:
            logger.warning(f"Cannot build dataset_type for {dataset.id}: {e}")
            return False
        return getattr(dataset_type, "source", None) is not None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def startup(self) -> None:
        logger.info("Starting ingestion manager...")
        self._shutdown_event = asyncio.Event()
        self._job_signal = asyncio.Event()

        self._job_processor_task = asyncio.create_task(
            self._job_processor_loop(), name="IngestionJobProcessor"
        )
        self._startup_init_task = asyncio.create_task(
            self._start_existing_dataset_tasks(),
            name="IngestionStartupInit",
        )
        logger.info("Ingestion manager started")

    async def _start_existing_dataset_tasks(self) -> None:
        """Spawn source consumer tasks for every dataset that has a source."""
        if self._provisioner_ready_event:
            logger.info("Waiting for provisioner startup to complete...")
            await self._provisioner_ready_event.wait()
            logger.info("Provisioner startup complete, starting dataset source tasks")

        try:
            datasets = (
                await self._dataset_repository.get_all_with_provisioner_state_id()
            )
            started = 0
            for dataset in datasets:
                if not self._has_source(dataset):
                    continue
                try:
                    await self.start_dataset_ingestion(dataset)
                    started += 1
                except Exception as e:
                    logger.exception(
                        f"Failed to start source task for '{dataset.name}': {e}"
                    )
            logger.info(f"Background: started source tasks for {started} datasets")
        except Exception as e:
            logger.exception(f"Failed to start existing dataset source tasks: {e}")

    async def shutdown(self) -> None:
        logger.info("Shutting down ingestion manager...")

        if self._shutdown_event:
            self._shutdown_event.set()
        if self._job_signal:
            self._job_signal.set()

        # Cancel and await every per-dataset source consumer
        source_tasks = list(self._source_tasks.values())
        for task in source_tasks:
            task.cancel()
        if source_tasks:
            await asyncio.gather(*source_tasks, return_exceptions=True)
        self._source_tasks.clear()
        self._sources.clear()

        # Cancel job + startup tasks
        for task in (self._job_processor_task, self._startup_init_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("Ingestion manager shutdown complete")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def start_dataset_ingestion(self, dataset: Dataset) -> int:
        """Spawn a per-dataset source consumer task.

        Returns 1 once the task is spawned (or already running), 0 only
        when the dataset has no source. Note: this no longer pre-counts
        files — discovery happens asynchronously inside the source.
        """
        if dataset.id in self._source_tasks:
            logger.debug(f"Source task already running for '{dataset.name}'")
            return 1

        try:
            dataset_type = self._build_dataset_type(dataset)
        except KeyError as e:
            raise ValueError(f"Unknown dataset_type '{dataset.dtype}'") from e

        source = getattr(dataset_type, "source", None)
        if source is None:
            raise ValueError(
                f"Dataset type '{dataset.dtype}' does not support "
                "source-based ingestion"
            )

        self._sources[dataset.id] = source
        task = asyncio.create_task(
            self._run_source(dataset.id, dataset.tenant_id, source),
            name=f"IngestionSource[{dataset.id}]",
        )
        self._source_tasks[dataset.id] = task
        logger.info(f"Started source task for dataset '{dataset.name}'")
        return 1

    async def stop_dataset_ingestion(self, dataset_id: UUID) -> int:
        task = self._source_tasks.pop(dataset_id, None)
        self._sources.pop(dataset_id, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        cancelled = await self._ingestion_repository.cancel_pending_by_dataset(
            dataset_id
        )
        logger.info(f"Cancelled {cancelled} pending jobs for dataset {dataset_id}")
        return cancelled

    async def start_ingestion_by_id(self, dataset_id: UUID, tenant_id: UUID) -> int:
        """Convenience for auto-start after dataset creation. Silent on miss."""
        dataset = await self._dataset_repository.get_by_id(dataset_id, tenant_id)
        if not dataset:
            logger.warning(f"Dataset not found for ingestion: {dataset_id}")
            return 0
        if not self._has_source(dataset):
            return 0
        return await self.start_dataset_ingestion(dataset)

    def is_watching(self, dataset_id: UUID) -> bool:
        return dataset_id in self._source_tasks

    async def retry_failed_jobs(self, dataset_id: UUID, tenant_id: UUID) -> int:
        jobs_reset = await self._ingestion_repository.reset_failed_jobs(
            dataset_id, tenant_id
        )
        if jobs_reset > 0 and self._job_signal is not None:
            self._job_signal.set()
        return jobs_reset

    async def get_ingestion_stats(
        self, dataset_id: UUID, tenant_id: UUID
    ) -> dict[str, int]:
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
        return await self._ingestion_repository.get_by_dataset(
            dataset_id, tenant_id, status_filter, limit, offset
        )

    # -------------------------------------------------------------------------
    # Source consumption (per-dataset task body)
    # -------------------------------------------------------------------------

    async def _run_source(
        self, dataset_id: UUID, tenant_id: UUID, source: BaseSource
    ) -> None:
        try:
            async for event in source.change_stream():
                if self._shutdown_event and self._shutdown_event.is_set():
                    break
                await self._handle_source_event(dataset_id, tenant_id, event)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Source task crashed for {dataset_id}: {e}")
        finally:
            logger.info(f"Source task ended for {dataset_id}")

    async def _handle_source_event(
        self, dataset_id: UUID, tenant_id: UUID, event: SourceChangeEvent
    ) -> None:
        if event.event_type == "deleted":
            await self._ingestion_repository.delete_by_path(
                dataset_id, event.external_id
            )
            return

        # PR 4 generalizes IngestionJob to carry external_id + opaque
        # fingerprint instead of file_size/file_mtime_ns columns. Until
        # then, decode the local-file fingerprint shape here so existing
        # columns stay populated.
        try:
            fp_data = json.loads(event.fingerprint) if event.fingerprint else {}
        except (json.JSONDecodeError, TypeError):
            fp_data = {}

        await self._ingestion_repository.upsert_by_path(
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            file_path=event.external_id,
            file_name=SyncPath(event.external_id).name,
            file_size=int(fp_data.get("size", 0)),
            file_mtime_ns=int(fp_data.get("mtime_ns", 0)),
        )
        if self._job_signal is not None:
            self._job_signal.set()

    # -------------------------------------------------------------------------
    # Job processing
    # -------------------------------------------------------------------------

    async def _job_processor_loop(self) -> None:
        logger.info("Job processor started")
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(self._job_signal.wait(), timeout=5.0)
                self._job_signal.clear()
            except asyncio.TimeoutError:
                pass

            if self._shutdown_event.is_set():
                break

            await self._process_pending_jobs()
        logger.info("Job processor stopped")

    async def _process_pending_jobs(self) -> None:
        pending_jobs = await self._ingestion_repository.get_pending_jobs(limit=50)
        if not pending_jobs:
            return
        logger.debug(f"Processing {len(pending_jobs)} pending ingestion jobs")
        for job in pending_jobs:
            if self._shutdown_event.is_set():
                break
            await self._process_single_job(job)

    async def _resolve_source_for_job(
        self, job: IngestionJob
    ) -> tuple[BaseSource, object] | None:
        """Return ``(source, dataset_type_instance)`` for a job.

        Falls back to constructing fresh from the dataset row when the
        source task isn't currently cached (e.g. cold restart).
        """
        dataset = await self._dataset_repository.get_by_id(
            job.dataset_id, job.tenant_id
        )
        if not dataset:
            return None

        try:
            dataset_type = self._build_dataset_type(dataset)
        except KeyError:
            return None

        source = self._sources.get(job.dataset_id) or getattr(
            dataset_type, "source", None
        )
        if source is None:
            return None
        return source, dataset_type

    async def _process_single_job(self, job: IngestionJob) -> None:
        resolved = await self._resolve_source_for_job(job)
        if resolved is None:
            await self._ingestion_repository.update_status(
                job.id,
                IngestionJobStatus.CANCELLED,
                "Dataset or source unavailable",
            )
            return
        source, dataset_type = resolved

        try:
            # Fingerprint-drift check via the source. If the file changed
            # since the job was queued, re-upsert with the new fingerprint
            # and cancel this one — the upsert produces a new pending job.
            try:
                current_fp = source.fingerprint(job.file_path)
                current_data = json.loads(current_fp)
                if (
                    current_data.get("size") != job.file_size
                    or current_data.get("mtime_ns") != job.file_mtime_ns
                ):
                    logger.info(f"File changed during processing: {job.file_path}")
                    await self._ingestion_repository.upsert_by_path(
                        tenant_id=job.tenant_id,
                        dataset_id=job.dataset_id,
                        file_path=job.file_path,
                        file_name=job.file_name,
                        file_size=int(current_data["size"]),
                        file_mtime_ns=int(current_data["mtime_ns"]),
                    )
                    await self._ingestion_repository.update_status(
                        job.id,
                        IngestionJobStatus.CANCELLED,
                        "File changed during processing",
                    )
                    return
            except FileNotFoundError:
                await self._ingestion_repository.update_status(
                    job.id,
                    IngestionJobStatus.CANCELLED,
                    "File no longer exists",
                )
                return
            except (json.JSONDecodeError, OSError) as e:
                # Best-effort: if we can't re-fingerprint, proceed with ingestion.
                logger.debug(f"Fingerprint recheck failed for {job.file_path}: {e}")

            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.IN_PROGRESS
            )

            try:
                ingest_file = await source.fetch(job.file_path)
            except FileNotFoundError:
                await self._ingestion_repository.update_status(
                    job.id,
                    IngestionJobStatus.CANCELLED,
                    "File no longer exists",
                )
                return

            # TOCTOU re-check on the dataset row (could have been deleted
            # mid-fetch).
            dataset = await self._dataset_repository.get_by_id(
                job.dataset_id, job.tenant_id
            )
            if not dataset:
                await self._ingestion_repository.update_status(
                    job.id,
                    IngestionJobStatus.CANCELLED,
                    "Dataset deleted during processing",
                )
                return

            ctx = IngestContext(sender="system@openmined.org", dataset_id=dataset.id)
            try:
                await dataset_type.ingest(  # type: ignore[attr-defined]
                    ctx, IngestRequest(files=[ingest_file])
                )
            except Exception as ingest_err:
                raise RuntimeError(
                    f"[{dataset.dtype}] Ingestion error: {ingest_err}"
                ) from ingest_err

            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.COMPLETED
            )
            logger.info(f"Successfully ingested: {job.file_path}")

        except Exception as e:
            logger.exception(f"Failed to ingest {job.file_path}: {e}")
            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.FAILED, str(e)
            )
