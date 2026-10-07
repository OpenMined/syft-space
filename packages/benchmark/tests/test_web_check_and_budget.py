"""The web check, web search in the client, and the question budget.

The web check drops a question a model answers with the web and without the
publisher's data; what survives is capped evenly across kinds. Generation
reads every passage in the window and stops on the question budget, not on a
passage count.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import delete, select

from syft_benchmark.config import (
    DatasetMode,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
)
from syft_benchmark.db import ProcessedUnit, QaPair, Result, Run, session_scope
from syft_benchmark.generation import filter_stage, pipeline, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.llm import LLMError, ollama
from syft_benchmark.runs import judge as run_judge
from syft_benchmark.sources import Chunk, Document

SPACE = "pytest-wp3-webcheck"
OPENROUTER = "https://openrouter.ai/api/v1"


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean() -> Iterator[None]:
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Result).where(Result.space == SPACE))
            session.execute(delete(Run).where(Run.space == SPACE))
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
            session.execute(delete(ProcessedUnit).where(ProcessedUnit.space == SPACE))

    wipe()
    yield
    wipe()


def _space() -> SpaceConfig:
    return SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep")


def _web_settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "filter_model": "openai/gpt-5.1",
        "subject_url": OPENROUTER,
        "subject_key": "sk-test",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
        "max_consecutive_failures": 3,
    }
    return Settings(**{**base, **kwargs})


# --- web search in the client ------------------------------------------------


class _Response:
    status_code = 200
    text = ""

    def json(self) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "Paris"}, "finish_reason": "stop"}]}


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    bodies: list[dict[str, Any]] = []

    def fake_post(url: str, *, json: dict[str, Any], **_: Any) -> _Response:
        bodies.append(json)
        return _Response()

    monkeypatch.setattr("syft_benchmark.llm.ollama.httpx.post", fake_post)
    return bodies


def _role(url: str) -> Any:
    from syft_benchmark.llm import Provider

    return Provider(role="subject", url=url, api_key="sk-test", model="openai/gpt-5.1")


def test_web_search_adds_the_openrouter_web_search_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies = _capture(monkeypatch)
    conf = _web_settings()
    _, usage = ollama.chat(
        "s", "q", provider=_role(OPENROUTER), settings=conf, web_search=True
    )
    assert [tool["type"] for tool in bodies[0]["tools"]] == ["openrouter:web_search"]
    assert "plugins" not in bodies[0]
    assert usage["web_search"] in ("native", "plugin")
    assert usage["web_search_via"] == "tool"


def test_no_web_search_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies = _capture(monkeypatch)
    ollama.chat("s", "q", provider=_role(OPENROUTER), settings=_web_settings())
    assert "plugins" not in bodies[0]
    assert "tools" not in bodies[0]


def test_a_local_model_is_asked_without_web_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies = _capture(monkeypatch)
    _, usage = ollama.chat(
        "s",
        "q",
        provider=_role("http://ollama:11434/v1"),
        settings=Settings(),
        web_search=True,
    )
    assert "plugins" not in bodies[0]
    assert usage["web_search"] is False


# --- the web check -----------------------------------------------------------


def _pair(
    pair_id: str,
    generator: str = "qa",
    *,
    doc_id: str = "d1",
    answer: str = "Harbourton lighthouse",
) -> QaPair:
    return QaPair(
        id=pair_id,
        space=SPACE,
        generator=generator,
        task_type=GENERATORS[generator].task_type,
        doc_id=doc_id,
        question=f"Question {pair_id}: which landmark was restored?",
        answer=answer,
        context=f"The council restored the {answer} this spring.",
        status=PairStatus.PENDING.value,
        model="test-model",
        question_hash=uuid.uuid4().hex,
    )


def _insert(*pairs: QaPair) -> None:
    with session_scope() as session:
        for pair in pairs:
            session.add(pair)


def _statuses() -> dict[str, tuple[str, str, str | None]]:
    with session_scope() as session:
        rows = session.execute(select(QaPair).where(QaPair.space == SPACE)).scalars()
        return {r.id: (r.status, r.status_note, r.status_reason) for r in rows}


def _stub_web(
    monkeypatch: pytest.MonkeyPatch, answerable: set[str], *, fail: bool = False
) -> list[dict[str, Any]]:
    """The web model answers every question; the judge says which were right."""
    calls: list[dict[str, Any]] = []

    def web_chat(system: str, user: str, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        calls.append({"user": user, **kwargs})
        if fail:
            raise LLMError("the provider is down")
        return f"An answer to: {user}", {}

    def judge_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        right = any(f"Question {pid}:" in user for pid in answerable)
        return f'{{"correct": {"true" if right else "false"}}}', {}

    monkeypatch.setattr(web_check, "chat", web_chat)
    monkeypatch.setattr(run_judge, "chat", judge_chat)
    return calls


@needs_db
def test_the_web_check_rejects_what_the_web_answers(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert(_pair("w1"), _pair("w2"), _pair("w3", "unanswerable_property"))
    calls = _stub_web(monkeypatch, answerable={"w1"})

    report = filter_stage.filter_pending(_space(), settings=_web_settings())

    final = _statuses()
    assert final["w1"] == (
        PairStatus.REJECTED.value,
        "web_answerable",
        StatusReason.WEB_ANSWERABLE.value,
    )
    assert final["w2"][0] == PairStatus.ACTIVE.value
    # A control question is not put to the web.
    assert final["w3"][2] == StatusReason.RETRIEVAL_GATE.value
    assert len(calls) == 2
    assert all(call["web_search"] is True for call in calls)
    assert report.web_answerable == 1
    assert report.active == 1


@needs_db
def test_no_filter_model_means_no_web_check(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert(_pair("w1"))
    calls = _stub_web(monkeypatch, answerable={"w1"})

    filter_stage.filter_pending(_space(), settings=_web_settings(filter_model=None))

    assert _statuses()["w1"][0] == PairStatus.ACTIVE.value
    assert calls == []


@needs_db
def test_a_failed_web_check_leaves_the_pair_pending(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert(*(_pair(f"w{i}") for i in range(5)))
    calls = _stub_web(monkeypatch, answerable=set(), fail=True)

    report = filter_stage.filter_pending(
        _space(), settings=_web_settings(concurrency=1)
    )

    assert {s for s, _, _ in _statuses().values()} == {PairStatus.PENDING.value}
    # Three failures in a row and the pass gives up.
    assert len(calls) == 3
    assert any("in a row failed" in note for note in report.notes)


@needs_db
def test_a_model_without_web_search_answers_from_its_training(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert(_pair("w1"))
    calls = _stub_web(monkeypatch, answerable={"w1"})

    report = filter_stage.filter_pending(
        _space(), settings=_web_settings(subject_url="http://ollama:11434/v1")
    )

    assert _statuses()["w1"][1] == "web_answerable"
    assert [call["web_search"] for call in calls] == [False]
    assert any("own training" in note for note in report.notes)


@needs_db
def test_the_cap_counts_only_what_survived_the_web_check(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    pairs = [_pair(f"q{i}", "qa", answer=f"Harbourton pier {i}") for i in range(4)]
    pairs += [
        _pair(f"m{i}", "multihop_synthesis", answer=f"Harbourton quay {i}")
        for i in range(4)
    ]
    _insert(*pairs)
    # Every qa pair but one, and no multihop pair, is answerable from the web.
    _stub_web(monkeypatch, answerable={"q0", "q1", "q2"})

    class _Chroma:
        def __init__(self, *_: Any) -> None: ...

        def collection_id(self, _name: str) -> str:
            return "cid"

    document = Document(
        doc_id="d1", title="T", url="", source="", file_name="t.md", chunks=[]
    )
    monkeypatch.setattr(pipeline, "ChromaClient", _Chroma)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: [document])

    report = pipeline.filter_and_rotate(
        _space(),
        settings=_web_settings(dataset_mode=DatasetMode.ROLLING, dataset_max_pairs=4),
    )

    final = _statuses()
    active = {pid for pid, (status, _, _) in final.items() if status == "active"}
    web = {pid for pid, (_, note, _) in final.items() if note == "web_answerable"}
    assert web == {"q0", "q1", "q2"}
    assert not active & web
    # Kept evenly across kinds: the one qa survivor, and multihop fills the rest.
    assert len(active) == 4
    assert "q3" in active
    assert report.rotation is not None
    assert report.rotation.over_cap == 1


# --- the question budget -----------------------------------------------------


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

    class _Chroma:
        def __init__(self, *_: Any) -> None: ...

        def collection_id(self, _name: str) -> str:
            return "cid"

    def fake_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        read.append(user)
        # A tag per unit keeps questions distinct when units run in parallel.
        item = f'{{"unit": "{uuid.uuid4().hex}"}}'
        # tiered answers with an object, the rest with an array.
        return (item if "Generate 1." in user else f"[{item}]"), {}

    def clean(items: Any, n: int, whole: str) -> tuple[list[Pair], list[str]]:
        unit = items[0]["unit"]
        made = [
            Pair(question=f"Q{unit}-{i}?", answer="A", distractors=[], meta={})
            for i in range(per_unit)
        ]
        return made, []

    monkeypatch.setattr(pipeline, "ChromaClient", _Chroma)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)
    monkeypatch.setattr(pipeline, "chat", fake_chat)
    for key in ("qa", "tiered_explanation"):
        spec = dataclasses.replace(GENERATORS[key], clean=clean)
        monkeypatch.setitem(GENERATORS, key, spec)
    return read


def _budget_settings(**kwargs: Any) -> Settings:
    return Settings(
        **{
            "document_window_days": 0,
            "pairs_per_chunk": 2,
            "max_consecutive_failures": 3,
            **kwargs,
        }
    )


@needs_db
def test_the_walk_stops_on_the_question_budget(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=2)
    report = pipeline.generate_for_space(
        _space(), generators=("qa",), settings=_budget_settings(chunks_per_run=3)
    )
    assert report.by_generator == {"qa": 6}
    assert len(read) == 3


@needs_db
def test_a_lean_passage_does_not_shrink_the_set(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Budget in questions: one pair per passage reads twice the passages."""
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=1)
    report = pipeline.generate_for_space(
        _space(), generators=("qa",), settings=_budget_settings(chunks_per_run=3)
    )
    assert report.by_generator == {"qa": 6}
    assert len(read) == 6


@needs_db
def test_every_passage_in_the_window_is_eligible(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=2)
    # One at a time, so the order the passages are read in is the walk's.
    report = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=_budget_settings(chunks_per_run=100, concurrency=1),
    )
    assert len(read) == 20
    assert report.by_generator == {"qa": 40}
    # Round-robin: the first pass touches every document before going deeper.
    assert all(f"Doc {d}" in read[d] for d in range(5))


@needs_db
def test_document_kinds_follow_the_same_budget(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tiered_explanation writes one per document, so it reads more documents."""
    read = _stub_generation(monkeypatch, _documents(6, 1), per_unit=1)
    report = pipeline.generate_for_space(
        _space(),
        generators=("tiered_explanation",),
        settings=_budget_settings(chunks_per_run=2),
    )
    assert report.by_generator == {"tiered_explanation": 4}
    assert len(read) == 4


@needs_db
def test_a_kind_that_writes_nothing_gives_up(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _stub_generation(monkeypatch, _documents(5, 4), per_unit=0)
    report = pipeline.generate_for_space(
        _space(), generators=("qa",), settings=_budget_settings(chunks_per_run=3)
    )
    assert len(read) == 3
    assert any("in a row wrote nothing" in note for note in report.notes)
