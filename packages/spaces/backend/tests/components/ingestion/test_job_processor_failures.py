"""A failed ingest always lands the job in FAILED with the reason; only an
unexpected error also prints a stack trace."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from loguru import logger

from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.job_processor import JobProcessor
from syft_space.components.sources.errors import SourceError


@pytest.fixture
def records():
    seen: list = []
    handle = logger.add(lambda m: seen.append(m.record), level="DEBUG")
    yield seen
    logger.remove(handle)


def _processor(error: Exception) -> tuple[JobProcessor, SimpleNamespace]:
    source = MagicMock()
    source.fingerprint = MagicMock(return_value="fp")

    @asynccontextmanager
    async def fetch(external_id):
        raise error
        yield  # pragma: no cover

    source.fetch = fetch
    processor = JobProcessor.__new__(JobProcessor)
    processor._ingestion_repository = MagicMock(update_status=AsyncMock())
    processor._dataset_repository = MagicMock()
    processor._resolve_source_for_job = AsyncMock(return_value=(source, MagicMock()))
    processor._running = None
    job = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        dataset_id=uuid4(),
        external_id="feed:item",
        fingerprint="fp",
    )
    return processor, job


def _failure_log(records):
    return [r for r in records if r["message"].startswith("Failed to ingest")]


async def test_a_source_error_is_one_warning_line_and_a_failed_job(records):
    processor, job = _processor(SourceError("Item feed:item is no longer in the feed"))
    await processor._process_single_job(job)
    (entry,) = _failure_log(records)
    assert entry["level"].name == "WARNING" and entry["exception"] is None
    assert "no longer in the feed" in entry["message"]
    processor._ingestion_repository.update_status.assert_awaited_with(
        job.id,
        IngestionJobStatus.FAILED,
        "Item feed:item is no longer in the feed",
        expected_status=IngestionJobStatus.IN_PROGRESS,
    )


async def test_any_other_error_keeps_the_stack_trace(records):
    processor, job = _processor(RuntimeError("boom"))
    await processor._process_single_job(job)
    (entry,) = _failure_log(records)
    assert entry["level"].name == "ERROR" and entry["exception"] is not None
    processor._ingestion_repository.update_status.assert_awaited_with(
        job.id,
        IngestionJobStatus.FAILED,
        "boom",
        expected_status=IngestionJobStatus.IN_PROGRESS,
    )
