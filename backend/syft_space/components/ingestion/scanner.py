"""Per-dataset source consumer (producer side of ingestion).

Spawns one task per dataset that iterates ``source.change_stream()`` and turns
change events into PENDING ``IngestionJob`` rows, then wakes the JobProcessor.

Communicates with the consumer (JobProcessor) only through shared seams — the
``ingestion_jobs`` table, the ``sources`` cache, and the ``job_signal`` event —
all owned by the IngestionManager facade and handed in via ``bind()``.
"""

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from syft_space.components.datasets.entities import Dataset
from syft_space.components.ingestion.factory import DatasetTypeFactory
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.sources.interfaces import BaseSource, SourceChangeEvent

if TYPE_CHECKING:
    from syft_space.components.datasets.repository import DatasetRepository


class SourceScanner:
    """Owns the per-dataset source consumer tasks."""

    def __init__(
        self,
        dataset_repository: "DatasetRepository",
        ingestion_repository: IngestionJobRepository,
        factory: DatasetTypeFactory,
    ):
        self._dataset_repository = dataset_repository
        self._ingestion_repository = ingestion_repository
        self._factory = factory

        self._source_tasks: dict[UUID, asyncio.Task] = {}

        # Shared primitives, bound at startup by the facade.
        self._shutdown_event: asyncio.Event | None = None
        self._job_signal: asyncio.Event | None = None
        self._sources: dict[UUID, BaseSource] = {}

    def bind(
        self,
        *,
        shutdown_event: asyncio.Event,
        job_signal: asyncio.Event,
        sources: dict[UUID, BaseSource],
    ) -> None:
        """Wire the shared coordination primitives owned by the facade."""
        self._shutdown_event = shutdown_event
        self._job_signal = job_signal
        self._sources = sources

    def is_watching(self, dataset_id: UUID) -> bool:
        return dataset_id in self._source_tasks

    async def start(self, dataset: Dataset) -> int:
        """Spawn a per-dataset source consumer task.

        Returns 1 once the task is spawned (or already running), 0 only
        when the dataset has no source. Note: this no longer pre-counts
        files — discovery happens asynchronously inside the source.
        """
        if dataset.id in self._source_tasks:
            logger.debug(f"Source task already running for '{dataset.name}'")
            return 1

        try:
            dataset_type = self._factory.build(dataset)
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

    async def stop(self, dataset_id: UUID) -> int:
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

    async def stop_all(self) -> None:
        """Cancel and await every per-dataset source consumer."""
        source_tasks = list(self._source_tasks.values())
        for task in source_tasks:
            task.cancel()
        if source_tasks:
            await asyncio.gather(*source_tasks, return_exceptions=True)
        self._source_tasks.clear()
        self._sources.clear()

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
            await self._ingestion_repository.delete_by_external_id(
                dataset_id, event.external_id
            )
            return

        await self._ingestion_repository.upsert_by_external_id(
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            external_id=event.external_id,
            fingerprint=event.fingerprint,
        )
        if self._job_signal is not None:
            self._job_signal.set()
