"""Deleting a dataset stops the job that is ingesting it.

Without this, a long conversion keeps running for a dataset that no longer
exists and holds up every job queued behind it.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from syft_space.components.chunking import docling_local
from syft_space.components.chunking.docling_local import LocalDoclingBackend
from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.job_processor import JobProcessor
from syft_space.components.ingestion.manager import IngestionManager
from syft_space.components.shared.cancellation import CancelToken
from syft_space.components.shared.ingest_types import IngestCancelled, IngestFile

# ── the conversion subprocess ───────────────────────────────────────────


def sleeping_worker(monkeypatch) -> None:
    """Stand in for the docling worker with a process that never finishes."""
    monkeypatch.setattr(
        docling_local,
        "_self_command",
        lambda: [sys.executable, "-c", "import time; time.sleep(120)"],
    )


def run_one_page(tmp_path: Path, cancel: CancelToken):
    file = IngestFile(external_id="a.pdf", path=tmp_path / "a.pdf", filename="a.pdf")
    return LocalDoclingBackend._run_page_subprocess(
        file.path, 1, 1, tmp_path / "images", "doc", file, cancel
    )


def test_cancel_kills_the_running_subprocess(tmp_path, monkeypatch):
    sleeping_worker(monkeypatch)
    cancel = CancelToken()
    threading.Timer(0.3, cancel.cancel).start()

    started = time.monotonic()
    with pytest.raises(IngestCancelled):
        run_one_page(tmp_path, cancel)

    assert time.monotonic() - started < 10


def test_a_cancelled_token_starts_no_subprocess(tmp_path, monkeypatch):
    def no_worker():
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(docling_local, "_self_command", no_worker)
    cancel = CancelToken()
    cancel.cancel()

    with pytest.raises(IngestCancelled):
        run_one_page(tmp_path, cancel)


# ── the job processor ───────────────────────────────────────────────────


class FakeJobs:
    """Job repository that records status writes and honours the guard."""

    def __init__(self, status: IngestionJobStatus = IngestionJobStatus.PENDING):
        self.status = status
        self.writes: list[IngestionJobStatus] = []

    async def update_status(self, job_id, status, error=None, expected_status=None):
        if expected_status is not None and self.status != expected_status:
            return None
        self.status = status
        self.writes.append(status)
        return SimpleNamespace(id=job_id)


def make_processor(ingest, jobs: FakeJobs) -> tuple[JobProcessor, SimpleNamespace]:
    job = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        dataset_id=uuid4(),
        external_id="book.pdf",
        fingerprint="fp",
    )
    source = MagicMock()
    source.fingerprint = MagicMock(return_value="fp")

    @asynccontextmanager
    async def fetch(external_id):
        yield IngestFile(
            external_id=external_id, path=Path("book.pdf"), filename="book.pdf"
        )

    source.fetch = fetch
    dataset_repository = MagicMock()
    dataset_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=job.dataset_id, dtype="local_file")
    )
    processor = JobProcessor(dataset_repository, jobs, MagicMock())
    processor._resolve_source_for_job = AsyncMock(
        return_value=(source, SimpleNamespace(ingest=ingest))
    )
    return processor, job


def blocking_ingest(started: asyncio.Event):
    """An ingest that runs until its token is cancelled, like a long PDF."""

    async def ingest(ctx, request):
        started.set()
        while not ctx.cancel.cancelled:
            await asyncio.sleep(0.01)
        raise IngestCancelled("stopped")

    return ingest


async def test_cancelling_a_dataset_stops_its_running_job_and_waits_for_it():
    started = asyncio.Event()
    jobs = FakeJobs()
    processor, job = make_processor(blocking_ingest(started), jobs)
    running = asyncio.create_task(processor._process_single_job(job))
    await asyncio.wait_for(started.wait(), timeout=5)

    await asyncio.wait_for(processor.cancel_dataset(job.dataset_id), timeout=5)

    # The job is already finished when cancel_dataset returns.
    assert running.done()
    assert jobs.writes == [
        IngestionJobStatus.IN_PROGRESS,
        IngestionJobStatus.CANCELLED,
    ]


async def test_cancelling_another_dataset_leaves_the_running_job_alone():
    started = asyncio.Event()
    jobs = FakeJobs()
    processor, job = make_processor(blocking_ingest(started), jobs)
    running = asyncio.create_task(processor._process_single_job(job))
    await asyncio.wait_for(started.wait(), timeout=5)

    await asyncio.wait_for(processor.cancel_dataset(uuid4()), timeout=5)

    assert not running.done()
    await processor.cancel_dataset(job.dataset_id)


async def test_a_job_cancelled_while_queued_is_never_started():
    """The processor lists jobs in batches; one may be cancelled before its turn."""
    ingest = AsyncMock()
    jobs = FakeJobs(status=IngestionJobStatus.CANCELLED)
    processor, job = make_processor(ingest, jobs)

    await processor._process_single_job(job)

    ingest.assert_not_awaited()
    assert jobs.writes == []


async def test_stopping_the_processor_cancels_the_running_job():
    started = asyncio.Event()
    jobs = FakeJobs()
    processor, job = make_processor(blocking_ingest(started), jobs)
    running = asyncio.create_task(processor._process_single_job(job))
    await asyncio.wait_for(started.wait(), timeout=5)

    await processor.stop()
    await asyncio.wait_for(running, timeout=5)

    assert jobs.status is IngestionJobStatus.CANCELLED


# ── the manager ─────────────────────────────────────────────────────────


async def test_stopping_a_dataset_cancels_pending_jobs_then_the_running_one():
    order: list[str] = []
    manager = IngestionManager.__new__(IngestionManager)

    async def stop(dataset_id):
        order.append("pending")
        return 3

    async def cancel_dataset(dataset_id):
        order.append("running")

    manager._scanner = SimpleNamespace(stop=stop)
    manager._job_processor = SimpleNamespace(cancel_dataset=cancel_dataset)

    assert await manager.stop_dataset_ingestion(uuid4()) == 3
    assert order == ["pending", "running"]
