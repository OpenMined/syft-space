"""Source-agnostic ingestion orchestrator (lifecycle facade).

Coordinates two collaborators, decoupled by the ``ingestion_jobs`` queue:

- ``SourceScanner`` (producer) — one task per dataset, iterates
  ``source.change_stream()`` and writes PENDING ``IngestionJob`` rows.
- ``JobProcessor`` (consumer) — drains pending jobs, fetches content via the
  source, and delegates to the dataset_type's ``ingest()`` method.

The facade owns the shared coordination primitives (the ``sources`` cache, the
``job_signal`` wake event, and the ``shutdown_event``) and hands them to both
collaborators; it also owns application-lifecycle wiring (startup/shutdown,
provisioner-ready gating, starting existing datasets).

Filesystem watching, sync→async bridging, and observer ownership all live
inside the source (and the shared ``LocalFileWatcher``); the manager treats
every source uniformly.
"""

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.entities import Dataset
from syft_space.components.datasets.selection_repository import (
    DatasetSelectionRepository,
)
from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.factory import DatasetTypeFactory
from syft_space.components.ingestion.job_processor import JobProcessor
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.ingestion.scanner import SourceScanner
from syft_space.components.shared.lifecycle import LifecycleService
from syft_space.components.sources.interfaces import BaseSource

if TYPE_CHECKING:
    from syft_space.components.datasets.repository import DatasetRepository


class IngestionManager(LifecycleService):
    """Facade coordinating the source scanner and the job processor."""

    def __init__(
        self,
        dataset_repository: "DatasetRepository",
        ingestion_repository: IngestionJobRepository,
        selection_repository: DatasetSelectionRepository,
        registry: DatasetTypeRegistry,
    ):
        self._dataset_repository = dataset_repository
        self._ingestion_repository = ingestion_repository

        self._factory = DatasetTypeFactory(registry)
        self._scanner = SourceScanner(
            dataset_repository,
            ingestion_repository,
            selection_repository,
            self._factory,
        )
        self._job_processor = JobProcessor(
            dataset_repository, ingestion_repository, self._factory
        )

        # Shared coordination state (owned here, bound into the collaborators).
        self._sources: dict[UUID, BaseSource] = {}
        self._shutdown_event: asyncio.Event | None = None
        self._job_signal: asyncio.Event | None = None

        self._startup_init_task: asyncio.Task | None = None
        self._provisioner_ready_event: asyncio.Event | None = None

    def set_provisioner_ready_event(self, event: asyncio.Event) -> None:
        self._provisioner_ready_event = event

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def startup(self) -> None:
        logger.info("Starting ingestion manager...")
        self._shutdown_event = asyncio.Event()
        self._job_signal = asyncio.Event()

        self._scanner.bind(
            shutdown_event=self._shutdown_event,
            job_signal=self._job_signal,
            sources=self._sources,
        )
        self._job_processor.bind(
            shutdown_event=self._shutdown_event,
            job_signal=self._job_signal,
            sources=self._sources,
        )

        # Recover jobs left IN_PROGRESS by a previous process that died
        # mid-ingest (reload/crash/OOM). No worker is running yet, so any such
        # row is stale — re-queue it before the processor starts draining,
        # otherwise it stays IN_PROGRESS forever (the processor only claims
        # PENDING jobs).
        requeued = await self._ingestion_repository.reset_orphaned_in_progress()
        if requeued:
            logger.info(f"Re-queued {requeued} orphaned in-progress ingestion jobs")

        self._job_processor.start()
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
                if not self._factory.has_source(dataset):
                    continue
                try:
                    await self._scanner.start(dataset)
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
        # Wake the job processor so its loop observes the shutdown flag.
        self._job_processor.notify()

        # Cancel and await every per-dataset source consumer.
        await self._scanner.stop_all()

        # Cancel job processor + startup tasks.
        await self._job_processor.stop()
        if self._startup_init_task and not self._startup_init_task.done():
            self._startup_init_task.cancel()
            try:
                await self._startup_init_task
            except asyncio.CancelledError:
                pass

        logger.info("Ingestion manager shutdown complete")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def start_dataset_ingestion(self, dataset: Dataset) -> int:
        """Spawn a per-dataset source consumer task."""
        return await self._scanner.start(dataset)

    async def stop_dataset_ingestion(self, dataset_id: UUID) -> int:
        return await self._scanner.stop(dataset_id)

    async def restart_dataset_ingestion(
        self, dataset_id: UUID, tenant_id: UUID
    ) -> None:
        """Restart a dataset's stream so it runs with the current selection.

        Called after picks are added or removed. The restarted stream
        re-reads the selection table and re-emits everything in scope;
        the job repository's fingerprint dedup makes that cheap. Silent
        on missing/sourceless datasets.
        """
        dataset = await self._dataset_repository.get_by_id(dataset_id, tenant_id)
        if not dataset or not self._factory.has_source(dataset):
            return
        await self._scanner.restart(dataset)

    async def apply_unselection(
        self, dataset_id: UUID, tenant_id: UUID, item_ids: list[str]
    ) -> int:
        """Tombstone the ingestion jobs produced by removed picks.

        Which jobs a pick produced is id-space knowledge owned by the
        source provider (``selection_covers``): a directory pick covers the
        files under it, a post pick covers itself. Overlapping picks
        self-heal — the restarted stream's initial scan resurrects any item
        still covered by a remaining pick.

        Returns the number of jobs tombstoned.
        """
        dataset = await self._dataset_repository.get_by_id(dataset_id, tenant_id)
        if not dataset:
            return 0
        try:
            provider = self._factory.provider_cls(dataset)
        except KeyError:
            return 0

        # Test every live job against the removed picks (unbounded — a directory
        # pick can cover thousands of jobs), then tombstone the covered ones in
        # a single bulk write.
        external_ids = await self._ingestion_repository.get_active_external_ids(
            dataset_id, tenant_id
        )
        covered = [
            external_id
            for external_id in external_ids
            if any(
                provider.selection_covers(item_id, external_id) for item_id in item_ids
            )
        ]
        count = await self._ingestion_repository.mark_deleted_by_external_ids(
            dataset_id, covered
        )
        if count:
            logger.info(
                f"Tombstoned {count} jobs for dataset {dataset_id} "
                f"after unselecting {len(item_ids)} pick(s)"
            )
        return count

    async def start_ingestion_by_id(self, dataset_id: UUID, tenant_id: UUID) -> int:
        """Convenience for auto-start after dataset creation. Silent on miss."""
        dataset = await self._dataset_repository.get_by_id(dataset_id, tenant_id)
        if not dataset:
            logger.warning(f"Dataset not found for ingestion: {dataset_id}")
            return 0
        if not self._factory.has_source(dataset):
            return 0
        return await self._scanner.start(dataset)

    def is_watching(self, dataset_id: UUID) -> bool:
        return self._scanner.is_watching(dataset_id)

    async def retry_failed_jobs(self, dataset_id: UUID, tenant_id: UUID) -> int:
        jobs_reset = await self._ingestion_repository.reset_failed_jobs(
            dataset_id, tenant_id
        )
        if jobs_reset > 0:
            self._job_processor.notify()
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
