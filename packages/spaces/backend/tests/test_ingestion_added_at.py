"""Every ingested file carries the time it was added to this Space.

The benchmark's time window reads ``added_at`` for articles without a
publication date; the vector store writes it as ``added_at`` and
``added_at_ts``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from syft_space.components.ingestion.entities import IngestionJobStatus
from syft_space.components.ingestion.job_processor import JobProcessor
from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    _chroma_scalars,
)


class _Source:
    def __init__(self, file: IngestFile) -> None:
        self.file = file

    def fingerprint(self, external_id: str) -> str:
        return "fp"

    @asynccontextmanager
    async def fetch(self, external_id: str):
        yield self.file


@pytest.mark.asyncio
async def test_the_ingested_file_is_stamped_with_its_add_time() -> None:
    source_file = IngestFile(
        external_id="/docs/a.md",
        path=Path("/docs/a.md"),
        filename="a.md",
        metadata={"source": "local_file"},
    )
    dataset = SimpleNamespace(id=uuid4(), dtype="local_file")
    dataset_type = SimpleNamespace(source=_Source(source_file), ingest=AsyncMock())

    datasets = AsyncMock()
    datasets.get_by_id = AsyncMock(return_value=dataset)
    jobs = AsyncMock()
    factory = Mock()
    factory.build = Mock(return_value=dataset_type)
    processor = JobProcessor(datasets, jobs, factory)

    job = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        dataset_id=dataset.id,
        external_id="/docs/a.md",
        fingerprint="fp",
    )
    before = datetime.now(timezone.utc)
    await processor._process_single_job(job)  # type: ignore[arg-type]

    request = dataset_type.ingest.await_args.args[1]
    stamped = request.files[0].metadata
    assert stamped["source"] == "local_file"
    assert before <= stamped["added_at"] <= datetime.now(timezone.utc)
    # The source's own object is left as it was.
    assert "added_at" not in source_file.metadata
    assert jobs.update_status.await_args.args[1] == IngestionJobStatus.COMPLETED


def test_the_add_time_reaches_chroma_as_text_and_epoch() -> None:
    at = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
    scalars = _chroma_scalars({"added_at": at})
    assert scalars["added_at"] == "2026-10-06T09:00:00+00:00"
    assert scalars["added_at_ts"] == int(at.timestamp())
