"""Every ingested file carries the time this Space indexed it.

The benchmark's time window reads ``syft_indexed_at`` for articles without a
publication date; the vector store writes it as ``syft_indexed_at`` and
``syft_indexed_at_ts``.
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


async def _ingested_metadata(source_file: IngestFile) -> dict:
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
        external_id=source_file.external_id,
        fingerprint="fp",
    )
    await processor._process_single_job(job)  # type: ignore[arg-type]

    assert jobs.update_status.await_args.args[1] == IngestionJobStatus.COMPLETED
    request = dataset_type.ingest.await_args.args[1]
    return request.files[0].metadata


@pytest.mark.asyncio
async def test_the_ingested_file_is_stamped_with_its_index_time() -> None:
    source_file = IngestFile(
        external_id="/docs/a.md",
        path=Path("/docs/a.md"),
        filename="a.md",
        metadata={"source": "local_file"},
    )
    before = datetime.now(timezone.utc)
    stamped = await _ingested_metadata(source_file)

    assert stamped["source"] == "local_file"
    assert before <= stamped["syft_indexed_at"] <= datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_a_source_field_named_added_at_is_kept() -> None:
    own = datetime(2020, 1, 1, tzinfo=timezone.utc)
    source_file = IngestFile(
        external_id="/docs/b.md",
        path=Path("/docs/b.md"),
        filename="b.md",
        metadata={"source": "local_file", "added_at": own},
    )
    stamped = await _ingested_metadata(source_file)

    assert stamped["added_at"] == own
    assert stamped["syft_indexed_at"] > own


def test_the_index_time_reaches_chroma_as_text_and_epoch() -> None:
    at = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
    scalars = _chroma_scalars({"syft_indexed_at": at})
    assert scalars["syft_indexed_at"] == "2026-10-06T09:00:00+00:00"
    assert scalars["syft_indexed_at_ts"] == int(at.timestamp())
