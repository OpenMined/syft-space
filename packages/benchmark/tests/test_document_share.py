"""A run over a list of documents gives each document the same share.

Each document gives every passage kind ``passages_per_document`` unparsed
passages and every article kind one unit, so a kind's budget is its units
times the questions per unit, whatever the batch. Window runs keep
``chunks_per_run``.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from syft_benchmark.config import SpaceConfig
from syft_benchmark.generation import cohort as cohorts
from syft_benchmark.generation import pipeline
from syft_benchmark.generation.generators import GENERATORS, Scope
from syft_benchmark.generation.pipeline import EXTRACTIVE_KEYS, GenerationReport
from syft_benchmark.sources import Chunk, Document

from fakes import ChromaStub, openrouter_settings

SPACE = "pytest-document-share"
PASSAGES = 4
PAIRS = 2


def _documents(count: int) -> list[Document]:
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
                for i in range(PASSAGES)
            ],
        )
        for n in range(count)
    ]


def _queues(
    documents: list[Document], per_document: int | None
) -> list[pipeline._Queue]:
    specs = list(GENERATORS.values())
    extractive = tuple(s.key for s in specs if s.key in EXTRACTIVE_KEYS)
    return pipeline._queues(
        SPACE,
        specs,
        extractive,
        documents,
        "c1",
        openrouter_settings(),
        GenerationReport(space=SPACE, cohort="c1"),
        per_document=per_document,
    )


def _per_unit(key: str) -> int:
    return 1 if GENERATORS[key].single_item else PAIRS


@pytest.mark.parametrize("count", [1, 3, 30])
@pytest.mark.parametrize("share", [1, 2])
def test_each_document_gives_every_queue_its_share(
    monkeypatch: pytest.MonkeyPatch, count: int, share: int
) -> None:
    monkeypatch.setattr(pipeline, "_processed_ids", lambda *a: set())
    documents = _documents(count)

    for queue in _queues(documents, share):
        per_doc = Counter(doc.doc_id for doc, _ in queue.units)
        assert set(per_doc) == {doc.doc_id for doc in documents}, queue.label
        wanted = 1 if queue.scope is Scope.DOCUMENT else share
        assert set(per_doc.values()) == {wanted}, queue.label


def test_a_document_gives_its_next_unparsed_passages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = _documents(2)

    def qa(parsed: set[str]) -> list[str]:
        monkeypatch.setattr(pipeline, "_processed_ids", lambda *a: set(parsed))
        (queue,) = (q for q in _queues(documents, 2) if q.label == "qa")
        return [chunk.chunk_id for _, chunk in queue.units]

    first = qa(set())
    again = qa(set(first))

    assert len(first) == len(again) == 2 * 2
    assert set(first) | set(again) == {
        chunk.chunk_id for doc in documents for chunk in doc.chunks
    }


# --- the budgets a build reports ---------------------------------------------


def _build(
    monkeypatch: pytest.MonkeyPatch, documents: list[Document], **kwargs: Any
) -> GenerationReport:
    """A build stopped before its first unit: the budgets, and nothing written."""
    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)
    monkeypatch.setattr(pipeline, "backfill", lambda *_: None)
    monkeypatch.setattr(pipeline, "_processed_ids", lambda *a: set())
    monkeypatch.setattr(cohorts, "current", lambda *_: "c1")
    settings: dict[str, Any] = {
        "pairs_per_chunk": PAIRS,
        "chunks_per_run": 3,
        "document_window_days": 0,
        "concurrency": 1,
    }
    settings.update(kwargs.pop("settings", {}))
    return pipeline.generate_for_space(
        SpaceConfig(key=SPACE, url="http://space", endpoint="ep"),
        generators=tuple(GENERATORS),
        settings=openrouter_settings(**settings),
        should_stop=lambda: True,
        **kwargs,
    )


@pytest.mark.parametrize("count", [1, 3, 30])
@pytest.mark.parametrize("share", [1, 2])
def test_a_scoped_budget_is_the_documents_share(
    monkeypatch: pytest.MonkeyPatch, count: int, share: int
) -> None:
    documents = _documents(count)

    report = _build(
        monkeypatch,
        documents,
        settings={"passages_per_document": share},
        doc_ids=frozenset(doc.doc_id for doc in documents),
    )

    for key, stats in report.kinds.items():
        units = count if GENERATORS[key].scope is Scope.DOCUMENT else count * share
        assert (stats.units_available, stats.budget) == (
            units,
            units * _per_unit(key),
        ), key


def test_limit_and_per_generator_cap_a_scoped_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = _documents(30)
    scope = frozenset(doc.doc_id for doc in documents)

    limited = _build(monkeypatch, documents, doc_ids=scope, limit=2)
    trial = _build(monkeypatch, documents, doc_ids=scope, per_generator=5)

    assert limited.kinds["qa"].budget == 2 * PAIRS
    assert limited.kinds["tiered_explanation"].budget == 2 * PAIRS
    assert {stats.budget for stats in trial.kinds.values()} == {5}


def test_a_window_run_keeps_chunks_per_run(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _build(monkeypatch, _documents(3), settings={"passages_per_document": 2})

    for key, stats in report.kinds.items():
        units = 3 if GENERATORS[key].scope is Scope.DOCUMENT else 3 * PASSAGES
        assert (stats.units_available, stats.budget) == (units, 3 * PAIRS), key
