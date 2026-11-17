"""The question budget: generation walks the window and stops on questions.

Every passage in the window is eligible; the walk goes round-robin across the
documents and stops when the budget in questions is met, not after a passage
count, so a lean passage reads more of them and a kind that writes nothing
gives up.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

import pytest

from syft_benchmark.config import Settings, SpaceConfig
from syft_benchmark.generation import pipeline
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.sources import Chunk, Document

from fakes import ChromaStub

SPACE = "pytest-question-budget"


def _space() -> SpaceConfig:
    return SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep")


def _documents(count: int, chunks: int) -> list[Document]:
    docs = []
    for d in range(count):
        doc_id = f"doc{d}"
        docs.append(
            Document(
                doc_id=doc_id,
                title=f"Doc {d}",
                url="",
                source="",
                file_name=f"{doc_id}.md",
                chunks=[
                    Chunk(
                        chunk_id=f"{doc_id}_{c}",
                        doc_id=doc_id,
                        chunk_index=c,
                        text=f"Passage {c} of document {d}.",
                        file_name=f"{doc_id}.md",
                        headings="",
                    )
                    for c in range(chunks)
                ],
            )
        )
    return docs


def _stub_generation(
    monkeypatch: pytest.MonkeyPatch,
    documents: list[Document],
    *,
    per_unit: int,
) -> list[str]:
    """Each unit yields ``per_unit`` distinct pairs; returns the units read."""
    read: list[str] = []

    def fake_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        read.append(user)
        # A tag per unit keeps questions distinct when units run in parallel.
        # Digits only: hex letters read as words to the language check.
        item = f'{{"unit": "{uuid.uuid4().int}"}}'
        # tiered answers with an object, the rest with an array.
        return (item if "Generate 1." in user else f"[{item}]"), {}

    def clean(items: Any, n: int, whole: str) -> tuple[list[Pair], list[Dropped]]:
        unit = items[0]["unit"]
        made = [
            Pair(question=f"Q{unit}-{i}?", answer="A", distractors=[], meta={})
            for i in range(per_unit)
        ]
        return made, []

    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)
    monkeypatch.setattr(pipeline, "chat", fake_chat)
    for key in ("qa", "tiered_explanation"):
        spec = dataclasses.replace(GENERATORS[key], clean=clean)
        monkeypatch.setitem(GENERATORS, key, spec)
    return read


def _settings(**kwargs: Any) -> Settings:
    return Settings(
        **{
            "document_window_days": 0,
            "pairs_per_chunk": 2,
            "max_consecutive_failures": 3,
            # The entity check is a writer call of its own: test_entity_check.py.
            "entity_check": False,
            **kwargs,
        }
    )


@pytest.mark.needs_db
def test_the_walk_stops_on_the_question_budget(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=2)
    report = pipeline.generate_for_space(
        _space(), generators=("qa",), settings=_settings(chunks_per_run=3)
    )
    assert report.by_generator == {"qa": 6}
    assert len(read) == 3


@pytest.mark.needs_db
def test_a_lean_passage_does_not_shrink_the_set(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Budget in questions: one pair per passage reads twice the passages."""
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=1)
    report = pipeline.generate_for_space(
        _space(), generators=("qa",), settings=_settings(chunks_per_run=3)
    )
    assert report.by_generator == {"qa": 6}
    assert len(read) == 6


@pytest.mark.needs_db
def test_every_passage_in_the_window_is_eligible(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=2)
    # One at a time, so the order the passages are read in is the walk's.
    report = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=_settings(chunks_per_run=100, concurrency=1),
    )
    assert len(read) == 20
    assert report.by_generator == {"qa": 40}
    # Round-robin: the first pass touches every document before going deeper.
    assert all(any(f"Doc {d}" in unit for unit in read[:5]) for d in range(5))


@pytest.mark.needs_db
def test_document_kinds_follow_the_same_budget(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tiered_explanation writes one per document, so it reads more documents."""
    read = _stub_generation(monkeypatch, _documents(6, 1), per_unit=1)
    report = pipeline.generate_for_space(
        _space(),
        generators=("tiered_explanation",),
        settings=_settings(chunks_per_run=2),
    )
    assert report.by_generator == {"tiered_explanation": 4}
    assert len(read) == 4


@pytest.mark.needs_db
def test_a_kind_that_writes_nothing_gives_up(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=0)
    report = pipeline.generate_for_space(
        _space(), generators=("qa",), settings=_settings(chunks_per_run=3)
    )
    assert len(read) == 3
    assert any("in a row wrote nothing" in note for note in report.notes)
