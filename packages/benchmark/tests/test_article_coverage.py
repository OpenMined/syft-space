"""Kinds that stop on their budget still cover every article in the window."""

from __future__ import annotations

import pytest

from syft_benchmark.config import Settings
from syft_benchmark.generation import pipeline
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pipeline import (
    EXTRACTIVE_KEYS,
    GenerationReport,
    pick_chunks,
)
from syft_benchmark.sources import Chunk, Document


def _documents(count: int, chunks: int = 6) -> list[Document]:
    return [
        Document(
            doc_id=f"d{n:03}",
            title=f"D{n}",
            url="",
            source="",
            file_name=f"d{n:03}.md",
            chunks=[
                Chunk(
                    chunk_id=f"d{n:03}-{i}",
                    doc_id=f"d{n:03}",
                    chunk_index=i,
                    text="x" * 500,
                    file_name=f"d{n:03}.md",
                    headings="",
                )
                for i in range(chunks)
            ],
        )
        for n in range(count)
    ]


def _queues(documents: list[Document], cohort: str = "c1") -> list[pipeline._Queue]:
    specs = list(GENERATORS.values())
    extractive = tuple(s.key for s in specs if s.key in EXTRACTIVE_KEYS)
    return pipeline._queues(
        "pytest-space",
        specs,
        extractive,
        documents,
        cohort,
        Settings(spaces_file="config/spaces.json"),  # type: ignore[arg-type]
        GenerationReport(space="pytest-space", cohort=cohort),
    )


@pytest.fixture(autouse=True)
def nothing_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "_processed_ids", lambda *a: set())


def test_kinds_on_a_budget_together_read_every_article() -> None:
    documents = _documents(200)

    # 1000 questions over 10 kinds, 2 per passage: 50 units per queue.
    read = {doc.doc_id for q in _queues(documents) for doc, _ in q.units[:50]}

    assert read == {doc.doc_id for doc in documents}


def test_the_order_is_fixed_by_the_cohort() -> None:
    documents = _documents(30)

    def first(cohort: str) -> list[str | None]:
        return [
            q.units[0][1].chunk_id if q.units[0][1] else q.units[0][0].doc_id
            for q in _queues(documents, cohort)
        ]

    assert first("c1") == first("c1")
    assert first("c1") != first("c2")


def test_a_seed_shuffles_passages_within_each_article() -> None:
    documents = _documents(1, chunks=20)

    plain = [c.chunk_index for _, c in pick_chunks(documents, set())]
    seeded = [c.chunk_index for _, c in pick_chunks(documents, set(), seed="s")]

    assert plain == list(range(20))
    assert sorted(seeded) == plain and seeded != plain
