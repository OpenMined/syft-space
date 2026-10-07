"""The web check end to end over one pair of every kind, with the models stubbed.

The web check model gets the bare question and nothing of the publisher's;
its answer is graded the way the main run grades that kind; a right answer
removes the question, a failed grading leaves it pending for the next pass,
and the set cap counts only what is left.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.generation import filter_stage, pipeline, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.llm import LLMError, Provider
from syft_benchmark.runs import judge as run_judge
from syft_benchmark.sources import Document

SPACE = "pytest-wp3-webkinds"
OPENROUTER = "https://openrouter.ai/api/v1"
SECRET = "Only-in-the-archive"


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean() -> Iterator[None]:
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))

    wipe()
    yield
    wipe()


def _space() -> SpaceConfig:
    return SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep")


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "filter_model": "openai/gpt-5.1",
        "subject_url": OPENROUTER,
        "subject_key": "sk-test",
        "judge_url": OPENROUTER,
        "judge_key": "sk-test",
        "judge_model": "anthropic/claude-opus-5",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
        "max_consecutive_failures": 0,
        "concurrency": 2,
    }
    return Settings(**{**base, **kwargs})


OPTIONS = "\n  A) The pier\n  B) The lighthouse\n  C) The quay\n  D) The mill"

# generator -> (question, gold answer, extra meta)
KINDS: dict[str, tuple[str, str, dict[str, Any]]] = {
    "named_entity_masking": (
        "Fill in the blank: ______ restored the lighthouse.",
        "Harbourton council",
        {},
    ),
    "numeric_masking": (
        "Fill in the blank: the repair cost ______ pounds.",
        "42000",
        {},
    ),
    "temporal_masking": (
        "Fill in the blank: the lighthouse reopened in ______.",
        "March 2026",
        {},
    ),
    "mcq": ("Which landmark was restored?" + OPTIONS, "B) The lighthouse", {}),
    "two_truths_one_lie": (
        "Which statement is false?" + OPTIONS,
        "D) The mill",
        {},
    ),
    "multihop_synthesis": (
        "Why did the council restore the lighthouse after the storm?",
        "The storm damaged the lighthouse and the council funded repairs.",
        {},
    ),
    "tiered_explanation": (
        "Explain it to a child.\n\nTopic: the lighthouse repair",
        "The council fixed the lighthouse damaged by the storm.",
        {
            "grading": "key_facts",
            "key_facts": ["the storm damaged the lighthouse", "the council fixed it"],
            "claims": ["the storm damaged the lighthouse", "the council fixed it"],
        },
    ),
    "qa": ("Who restored the lighthouse?", "Harbourton council", {}),
    "unanswerable_property": (
        "What colour is the lighthouse keeper's car?",
        "",
        {"grading": "behavior"},
    ),
    "false_premise": (
        "Why did the council demolish the lighthouse?",
        "",
        {"grading": "judge"},
    ),
}

# The web model answers these right.
RIGHT = {"mcq", "qa", "tiered_explanation", "numeric_masking"}


def _pairs() -> list[QaPair]:
    rows = []
    for generator, (question, answer, meta) in KINDS.items():
        facts = " ".join(meta.get("key_facts", []))
        rows.append(
            QaPair(
                id=generator,
                space=SPACE,
                generator=generator,
                task_type=GENERATORS[generator].task_type,
                doc_id="d1",
                question=question,
                answer=answer,
                context=f"{SECRET}. {answer}. {facts}",
                meta={"grading": GENERATORS[generator].grading, **meta},
                status=PairStatus.PENDING.value,
                model="test-model",
                question_hash=uuid.uuid4().hex,
            )
        )
    return rows


def _rows() -> dict[str, QaPair]:
    with session_scope() as session:
        rows = list(
            session.execute(select(QaPair).where(QaPair.space == SPACE)).scalars()
        )
        for row in rows:
            session.expunge(row)
    return {row.id: row for row in rows}


class _Models:
    """The web check model and the judge, stubbed."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.web: list[dict[str, Any]] = []
        self.judged: list[str] = []
        self.judges: set[str] = set()
        self.judge_down_for: set[str] = set()
        monkeypatch.setattr(web_check, "chat", self.web_chat)
        monkeypatch.setattr(run_judge, "chat", self.judge_chat)

    def _kind(self, question: str) -> str:
        return next(k for k, (q, _, _) in KINDS.items() if q == question)

    def web_chat(
        self, system: str, user: str, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        self.web.append({"system": system, "user": user, **kwargs})
        kind = self._kind(user)
        if kind == "mcq":
            answer = "The answer is B) The lighthouse"
        elif kind == "two_truths_one_lie":
            answer = "A) The pier"
        elif kind == "temporal_masking":
            answer = "I don't know"
        else:
            answer = f"web answer for {kind}"
        citations = [{"url": f"https://example.org/{kind}", "title": kind}]
        usage = {
            "web_search": "native" if kwargs.get("web_search") else False,
            "citations": citations if kind != "qa" else [],
        }
        return answer, usage

    def judge_chat(
        self, system: str, user: str, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        provider: Provider | None = kwargs.get("provider")
        self.judges.add(provider.model if provider else "")
        if "Facts:" in user:
            self.judged.append("tiered_explanation")
            return '{"covered": [true, true]}', {}
        kind = next(k for k in KINDS if f"web answer for {k}" in user)
        self.judged.append(kind)
        if kind in self.judge_down_for:
            raise LLMError("the judge is down")
        right = "true" if kind in RIGHT else "false"
        return f'{{"correct": {right}, "reasoning": "stub"}}', {}


def test_every_kind_goes_through_the_web_check(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope() as session:
        session.add_all(_pairs())
    models = _Models(monkeypatch)
    models.judge_down_for = {"multihop_synthesis"}
    conf = _settings(filter_judge_model="google/gemini-3.1-pro-preview")

    report = filter_stage.filter_pending(
        _space(), settings=conf, retrieve=lambda _q: []
    )
    rows = _rows()

    # The bare question, nothing of the publisher's, search on.
    asked = {call["user"] for call in models.web}
    controls = {"unanswerable_property", "false_premise"}
    assert asked == {q for k, (q, _, _) in KINDS.items() if k not in controls}
    for call in models.web:
        assert SECRET not in call["user"] and SECRET not in call["system"]
        assert call["web_search"] is True
        assert "Search the web" in call["system"]
        assert call["provider"].model == "openai/gpt-5.1"

    # Grading as the main run: letters without a judge, key facts, judge.
    assert "mcq" not in models.judged
    assert "two_truths_one_lie" not in models.judged
    assert "tiered_explanation" in models.judged
    assert "temporal_masking" not in models.judged  # an abstention needs no judge
    assert models.judges == {"google/gemini-3.1-pro-preview"}

    removed = {k for k, r in rows.items() if r.status_note == "web_answerable"}
    assert removed == RIGHT
    for kind in removed:
        assert rows[kind].status == PairStatus.REJECTED.value
        assert rows[kind].status_reason == StatusReason.WEB_ANSWERABLE.value
    kept = {"named_entity_masking", "temporal_masking", "two_truths_one_lie"}
    assert {k for k, r in rows.items() if r.status == "active"} == kept | controls

    # The record on the pair.
    qa = rows["qa"].meta["web_check"]
    assert qa["verdict"] == "correct"
    assert qa["answer"] == "web answer for qa"
    assert qa["judge"] == "google/gemini-3.1-pro-preview"
    assert qa["citations"] == [] and qa["web_search_unused"] is True
    mcq = rows["mcq"].meta["web_check"]
    assert mcq["citations"] == [{"url": "https://example.org/mcq", "title": "mcq"}]
    assert "web_search_unused" not in mcq
    for kind in controls:
        assert rows[kind].meta["web_check"] == {"skipped": web_check.CONTROL_NOTE}

    # A judge failure decides nothing: pending, with a note, retried next pass.
    multihop = rows["multihop_synthesis"]
    assert multihop.status == PairStatus.PENDING.value
    assert multihop.status_note.startswith("web check not graded, will retry")
    assert multihop.meta["web_check"]["attempts"] == 1

    assert report.web is not None
    assert (report.web.checked, report.web.removed) == (8, 4)
    assert (report.web.kept, report.web.failed) == (3, 1)
    assert "web check: checked 8, removed 4, kept 3, failed 1" in report.line()

    models.judge_down_for = set()
    again = filter_stage.filter_pending(_space(), settings=conf, retrieve=lambda _q: [])
    retried = _rows()["multihop_synthesis"]
    assert retried.status == PairStatus.ACTIVE.value
    assert retried.meta["web_check"]["attempts"] == 2
    assert "error" not in retried.meta["web_check"]
    assert again.web is not None and again.web.checked == 1


def test_without_web_search_it_answers_from_its_own_training(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope() as session:
        session.add_all([p for p in _pairs() if p.id in {"qa", "mcq"}])
    models = _Models(monkeypatch)

    report = filter_stage.filter_pending(
        _space(), settings=_settings(subject_url="http://ollama:11434/v1")
    )

    assert all(call["web_search"] is False for call in models.web)
    assert all("own knowledge" in call["system"] for call in models.web)
    rows = _rows()
    for row in rows.values():
        assert row.status_note == "web_answerable"
        assert row.meta["web_check"]["search"] == "none"
        assert row.meta["web_check"]["note"] == web_check.NO_SEARCH_NOTE
    assert report.web is not None and report.web.own_training_only
    assert "own training only" in report.line()
    # The judge is Judge 1 when no web check judge is set.
    assert models.judges == {"anthropic/claude-opus-5"}


def test_a_failed_answer_call_stays_pending_with_a_note(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope() as session:
        session.add_all([p for p in _pairs() if p.id == "qa"])
    _Models(monkeypatch)

    def down(*_: Any, **__: Any) -> tuple[str, dict[str, Any]]:
        raise LLMError("search provider timed out")

    monkeypatch.setattr(web_check, "chat", down)
    report = filter_stage.filter_pending(_space(), settings=_settings())

    row = _rows()["qa"]
    assert row.status == PairStatus.PENDING.value
    assert row.status_note == "web check failed, will retry: search provider timed out"
    assert row.meta["web_check"]["error"] == "search provider timed out"
    assert report.web is not None and report.web.failed == 1


def test_a_key_facts_pair_without_facts_is_not_kept_unchecked(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = next(p for p in _pairs() if p.id == "tiered_explanation")
    pair.meta = {"grading": "key_facts", "key_facts": []}
    with session_scope() as session:
        session.add(pair)
    models = _Models(monkeypatch)

    filter_stage.filter_pending(_space(), settings=_settings())

    row = _rows()["tiered_explanation"]
    assert row.status == PairStatus.REJECTED.value
    assert row.status_reason == StatusReason.OTHER.value
    assert row.status_note == web_check.NO_FACTS_NOTE
    assert models.web == []


def test_the_cap_spreads_across_kinds_after_the_check(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope() as session:
        session.add_all(_pairs())
    _Models(monkeypatch)

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
        settings=_settings(dataset_mode=DatasetMode.ROLLING, dataset_max_pairs=4),
        retrieve=lambda _q: [],
    )

    rows = _rows()
    active = {k for k, r in rows.items() if r.status == "active"}
    retired = {k for k, r in rows.items() if r.status == "retired"}
    # 6 survive the check (4 removed); the cap keeps 4, one per kind.
    assert len(active) == 4
    assert len(retired) == 2
    assert not active & RIGHT
    assert all(rows[k].status_note == "over the set cap" for k in retired)
    assert report.rotation is not None and report.rotation.over_cap == 2


# --- the set already in the measurement -------------------------------------


def _in_set(
    pair_id: str,
    generator: str = "qa",
    *,
    status: str = PairStatus.ACTIVE.value,
    note: str = "",
    doc_id: str = "d1",
    checked_by: str = "",
    age_days: int = 10,
) -> QaPair:
    question, answer, meta = KINDS[generator]
    meta = {"grading": GENERATORS[generator].grading, **meta}
    if checked_by:
        meta["web_check"] = {"model": checked_by, "verdict": "hallucinate"}
    return QaPair(
        id=pair_id,
        space=SPACE,
        generator=generator,
        task_type=GENERATORS[generator].task_type,
        doc_id=doc_id,
        # The stub tells the kinds apart by the question text.
        question=question,
        answer=answer,
        context=answer,
        meta=meta,
        status=status,
        status_note=note,
        status_reason=None if status == "active" else StatusReason.ROTATION.value,
        model="test-model",
        question_hash=uuid.uuid4().hex,
        created_at=datetime.now(UTC) - timedelta(days=age_days),
    )


def _corpus(monkeypatch: pytest.MonkeyPatch, dates: dict[str, datetime]) -> None:
    class _Chroma:
        def __init__(self, *_: Any) -> None: ...

        def collection_id(self, _name: str) -> str:
            return "cid"

    docs = []
    for doc_id, at in dates.items():
        docs.append(
            Document(
                doc_id=doc_id,
                title="T",
                url="",
                source="",
                file_name="t.md",
                chunks=[],
                published_at=at,
            )
        )
    monkeypatch.setattr(pipeline, "ChromaClient", _Chroma)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: docs)


def test_pairs_already_in_the_set_are_web_checked(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    _corpus(monkeypatch, {"d1": now, "old": now - timedelta(days=30)})
    with session_scope() as session:
        session.add_all(
            [
                # Never checked: qa is answerable, multihop is not.
                _in_set("a-qa", "qa"),
                _in_set("a-multihop", "multihop_synthesis"),
                # Checked by another model: checked again.
                _in_set("a-other", "named_entity_masking", checked_by="old/model"),
                # Checked by this model: left alone.
                _in_set("a-done", "temporal_masking", checked_by="openai/gpt-5.1"),
                # A control question: exempt.
                _in_set("a-control", "unanswerable_property"),
                # Held back by the cap, in the window: checked.
                _in_set(
                    "r-cap",
                    "numeric_masking",
                    status="retired",
                    note="over the set cap",
                ),
                # Out of the window: not worth a call.
                _in_set(
                    "r-old",
                    "mcq",
                    status="retired",
                    note="over the set cap",
                    doc_id="old",
                ),
            ]
        )
    models = _Models(monkeypatch)

    report = pipeline.filter_and_rotate(
        _space(),
        settings=_settings(dataset_mode=DatasetMode.ROLLING, document_window_days=7),
    )

    asked = {models._kind(call["user"]) for call in models.web}
    assert asked == {
        "qa",
        "multihop_synthesis",
        "named_entity_masking",
        "numeric_masking",
    }
    rows = _rows()
    assert rows["a-qa"].status_reason == StatusReason.WEB_ANSWERABLE.value
    assert rows["r-cap"].status_reason == StatusReason.WEB_ANSWERABLE.value
    assert rows["a-multihop"].status == PairStatus.ACTIVE.value
    assert rows["a-multihop"].meta["web_check"]["model"] == "openai/gpt-5.1"
    assert rows["a-other"].meta["web_check"]["model"] == "openai/gpt-5.1"
    assert report.web is not None and report.web.rechecked == 4
    assert "4 of them already in the set" in report.line()
    assert report.rotation is not None


def test_the_cap_takes_checked_pairs_before_unchecked_ones(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from syft_benchmark.generation.rotation import rotate

    model = "openai/gpt-5.1"
    with session_scope() as session:
        session.add_all(
            [
                *(_in_set(f"u{i}", "mcq", age_days=1) for i in range(3)),
                *(
                    _in_set(f"c{i}", "qa", checked_by=model, age_days=5)
                    for i in range(2)
                ),
            ]
        )
    report = rotate(
        SPACE,
        {"d1": datetime.now(UTC)},
        settings=_settings(dataset_mode=DatasetMode.ROLLING, dataset_max_pairs=2),
    )

    active = {k for k, r in _rows().items() if r.status == "active"}
    assert active == {"c0", "c1"}
    assert report.over_cap == 3


def test_a_rolling_cap_follows_the_newest_articles(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from syft_benchmark.generation.rotation import rotate

    now = datetime.now(UTC)
    with session_scope() as session:
        session.add_all(
            [
                _in_set("old-active", "qa", doc_id="d-old", age_days=20),
                _in_set(
                    "new-held",
                    "qa",
                    status="retired",
                    note="over the set cap",
                    doc_id="d-new",
                    age_days=1,
                ),
            ]
        )
    conf = _settings(
        filter_model=None, dataset_mode=DatasetMode.ROLLING, dataset_max_pairs=1
    )
    dated = {"d-old": now - timedelta(days=3), "d-new": now}
    rotate(SPACE, dated, settings=conf)
    first = {k for k, r in _rows().items() if r.status == "active"}
    rotate(SPACE, dated, settings=conf)

    assert first == {"new-held"}
    assert {k for k, r in _rows().items() if r.status == "active"} == first


def test_the_job_message_carries_the_stage_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from syft_benchmark import scheduler
    from syft_benchmark.generation.filter_stage import FilterSummary

    made = SimpleNamespace(pairs_made=20, failures=0, failure_sample="")
    filtered = FilterSummary(space=SPACE, checked=15, active=6, rejected=9)
    monkeypatch.setattr(scheduler, "generate_for_space", lambda *_, **__: made)
    monkeypatch.setattr(scheduler, "filter_and_rotate", lambda *_, **__: filtered)
    monkeypatch.setattr(scheduler, "endpoint_retriever", lambda *_: None)

    done = scheduler.measure(
        _space(), _settings(), generate=True, filter=True, evaluate=False
    )

    assert done.notes[:2] == ["wrote 20 questions", f"filter: {filtered.line()}"]
