"""Pending-job consumer.

Drains PENDING ``IngestionJob`` rows, re-checks fingerprints, fetches item
content via the source, and delegates to the dataset_type's ``ingest()``.

Communicates with the producer (SourceScanner) only through shared seams:
- the ``ingestion_jobs`` table (the work queue),
- a ``sources`` cache (warm source objects for running datasets),
- a ``job_signal`` event (wake-on-new-work).

These shared primitives are owned by the IngestionManager facade and handed
in via ``bind()`` at startup.
"""

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.factory import DatasetTypeFactory
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.shared.ingest_types import IngestContext, IngestRequest
from syft_space.components.sources.interfaces import BaseSource

if TYPE_CHECKING:
    from syft_space.components.datasets.repository import DatasetRepository


class JobProcessor:
    """Consumes pending ingestion jobs and runs them to a terminal state."""

    def __init__(
        self,
        dataset_repository: "DatasetRepository",
        ingestion_repository: IngestionJobRepository,
        factory: DatasetTypeFactory,
    ):
        self._dataset_repository = dataset_repository
        self._ingestion_repository = ingestion_repository
        self._factory = factory

        # Shared primitives, bound at startup by the facade.
        self._shutdown_event: asyncio.Event | None = None
        self._job_signal: asyncio.Event | None = None
        self._sources: dict[UUID, BaseSource] = {}

        self._task: asyncio.Task | None = None

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

    def start(self) -> None:
        """Spawn the job-processor loop task."""
        self._task = asyncio.create_task(self._loop(), name="IngestionJobProcessor")

    def notify(self) -> None:
        """Wake the loop — a new pending job may be available."""
        if self._job_signal is not None:
            self._job_signal.set()

    async def stop(self) -> None:
        """Cancel and await the loop task."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
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
            dataset_type = self._factory.build(dataset)
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

        external_id = job.external_id
        # Flips to True once we've claimed the job (marked it IN_PROGRESS).
        # Only after claiming can a concurrent edit or unselect race our
        # terminal write, so only then do we guard it. A failure *before*
        # claiming leaves the row PENDING and must mark FAILED unconditionally,
        # or the job would loop forever.
        claimed = False
        try:
            # Re-fingerprint before claiming: if the item changed since the job
            # was queued, re-queue it under the new fingerprint and cancel this
            # one. The fingerprint is an opaque string the source owns.
            try:
                current_fp = source.fingerprint(external_id)
                if current_fp != job.fingerprint:
                    logger.info(f"Item changed during processing: {external_id}")
                    await self._ingestion_repository.upsert_by_external_id(
                        tenant_id=job.tenant_id,
                        dataset_id=job.dataset_id,
                        external_id=external_id,
                        fingerprint=current_fp,
                    )
                    await self._ingestion_repository.update_status(
                        job.id,
                        IngestionJobStatus.CANCELLED,
                        "Item changed during processing",
                    )
                    return
            except FileNotFoundError:
                await self._ingestion_repository.update_status(
                    job.id,
                    IngestionJobStatus.CANCELLED,
                    "Item no longer exists",
                )
                return
            except OSError as e:
                # Can't re-fingerprint — proceed and let the ingest try anyway.
                logger.debug(f"Fingerprint recheck failed for {external_id}: {e}")

            # Claim the job.
            await self._ingestion_repository.update_status(
                job.id, IngestionJobStatus.IN_PROGRESS
            )
            claimed = True

            try:
                async with source.fetch(external_id) as ingest_file:
                    # The dataset may have been deleted while we fetched.
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

                    ctx = IngestContext(
                        sender="system@openmined.org", dataset_id=dataset.id
                    )
                    try:
                        await dataset_type.ingest(  # type: ignore[attr-defined]
                            ctx, IngestRequest(files=[ingest_file])
                        )
                    except Exception as ingest_err:
                        raise RuntimeError(
                            f"[{dataset.dtype}] Ingestion error: {ingest_err}"
                        ) from ingest_err
            except FileNotFoundError:
                await self._ingestion_repository.update_status(
                    job.id,
                    IngestionJobStatus.CANCELLED,
                    "File no longer exists",
                )
                return

            # Mark COMPLETED only if the row is still the job we claimed. A
            # concurrent edit (re-queued it to PENDING) or unselect (tombstoned
            # it to DELETED) must win — a blind write would silently drop it.
            await self._ingestion_repository.update_status(
                job.id,
                IngestionJobStatus.COMPLETED,
                expected_status=IngestionJobStatus.IN_PROGRESS,
            )
            logger.info(f"Successfully ingested: {external_id}")

        except Exception as e:
            logger.exception(f"Failed to ingest {external_id}: {e}")
            # Same guard as COMPLETED, but only once claimed: a failed ingest of
            # the old content must not overwrite a row re-queued or tombstoned
            # mid-flight. Before claiming, the row is still PENDING — fail it
            # outright so it doesn't retry forever.
            await self._ingestion_repository.update_status(
                job.id,
                IngestionJobStatus.FAILED,
                str(e),
                expected_status=(IngestionJobStatus.IN_PROGRESS if claimed else None),
            )
