"""The top-up: more of each kind the checks left short of its target.

After the build's questions are checked, a kind below its target gets more
written and checked the same way, sized by its survival rate on the target,
for at most ``TOP_UP_ROUNDS`` rounds and ``top_up_max_usd``.
"""

from __future__ import annotations

import dataclasses
import itertools
import uuid
from collections import Counter
from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import PairStatus, Settings, SpaceConfig, StatusReason
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.generation import pipeline, top_up, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Dropped, Pair
from syft_benchmark.llm import cost
from syft_benchmark.runs import judge as run_judge
from syft_benchmark.sources import Chunk, Document

from fakes import OPENROUTER, ChromaStub, openrouter_settings

SPACE = "pytest-top-up"
ANSWER = "Harbourton lighthouse"
# The web check model answers these correctly: they never survive.
EASY = "Which council restored"


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "judge_url": OPENROUTER,
        "judge_key": "sk-test",
        "judge_model": "anthropic/claude-opus-5",
        "judge_models": ["anthropic/claude-opus-5"],
        "filter_model": "openai/gpt-5.1",
        "document_window_days": 0,
        "pairs_per_chunk": 2,
        "chunks_per_run": 2,
        "concurrency": 1,
    }
    return openrouter_settings(**{**base, **kwargs})


def _space() -> SpaceConfig:
    return SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep")


def _documents(count: int, chunks: int) -> list[Document]:
    return [
        Document(
            doc_id=f"doc{d}",
            title=f"Doc {d}",
            url="",
            source="",
            file_name=f"doc{d}.md",
            chunks=[
                Chunk(
                    chunk_id=f"doc{d}_{c}",
                    doc_id=f"doc{d}",
                    chunk_index=c,
                    text=f"The council restored the {ANSWER} this spring ({d}/{c}).",
                    file_name=f"doc{d}.md",
                    headings="",
                )
                for c in range(chunks)
            ],
        )
        for d in range(count)
    ]


class _Build:
    """Stubbed writer and web check: ``qa`` questions are easy, ``multihop``
    ones are not. Each writer call costs ``usd``."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, usd: float = 0.0) -> None:
        self.usd = usd
        self.calls = 0
        self._ids = itertools.count()

        monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
        monkeypatch.setattr(pipeline, "load_documents", lambda *_: _documents(4, 4))
        monkeypatch.setattr(pipeline, "chat", self.chat)
        monkeypatch.setattr(web_check, "chat", self.web)
        monkeypatch.setattr(run_judge, "chat", self.judge)
        for key, opening in (
            ("qa", EASY),
            ("multihop_synthesis", "Why did the council restore"),
        ):
            spec = dataclasses.replace(GENERATORS[key], clean=self._clean(opening))
            monkeypatch.setitem(GENERATORS, key, spec)

    def chat(self, _system: str, _user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        self.calls += 1
        cost.charge(self.usd, cost.WRITER)
        return '[{"unit": 1}]', {}

    def _clean(self, opening: str) -> Any:
        def clean(_items: Any, n: int, _whole: str) -> tuple[list[Pair], list[Dropped]]:
            return [
                Pair(
                    question=f"{opening} the {ANSWER} in spring {next(self._ids)}?",
                    answer=ANSWER,
                    distractors=[],
                    meta={},
                )
                for _ in range(n)
            ], []

        return clean

    def web(self, _system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        return f"An answer to: {user}", {}

    def judge(self, _system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        return f'{{"correct": {"true" if EASY in user else "false"}}}', {}


def _active() -> dict[str, int]:
    with session_scope() as session:
        rows = session.execute(
            select(QaPair.generator).where(
                QaPair.space == SPACE, QaPair.status == PairStatus.ACTIVE.value
            )
        ).scalars()
        counts: dict[str, int] = {}
        for generator in rows:
            counts[generator] = counts.get(generator, 0) + 1
    return counts


KINDS = ("qa", "multihop_synthesis")


# --- targets and sizing --------------------------------------------------------


def test_a_kind_targets_its_budget_or_an_even_share_of_the_cap() -> None:
    keys = ["qa", "mcq", "unanswerable_property"]
    budgets = dict.fromkeys(keys, 10)
    assert top_up.kind_targets(budgets, Settings()) == budgets
    capped = Settings(dataset_max_pairs=10)
    assert top_up.kind_targets(budgets, capped) == dict.fromkeys(keys, 4)
    assert top_up.kind_targets(dict.fromkeys(keys, 2), capped) == dict.fromkeys(keys, 2)
    assert top_up.kind_targets({"qa": 6, "mcq": 2}, Settings()) == {"qa": 6, "mcq": 2}


def test_the_plan_writes_more_of_a_kind_that_usually_gets_filtered() -> None:
    plan = top_up.top_up_plan(
        {"qa": 10, "mcq": 10, "hop": 10, "tiered": 10},
        {"qa": 4, "mcq": 4, "hop": 10},
        {"qa": 0.5, "mcq": 0.01, "hop": 0.5},
        cap=50,
    )
    # qa: 6 short at one half; mcq: 6 short at the floor, held to the cap;
    # hop: at its target;
    # tiered: nothing survived and no history reads as one half.
    assert plan == {"qa": 12, "mcq": 50, "tiered": 20}
    assert top_up.top_up_plan({"qa": 10}, {}, {"qa": 0.1}, cap=50) == {"qa": 50}


@pytest.mark.needs_db
def test_survival_is_read_per_kind_from_the_target(clean: None) -> None:
    def pair(generator: str, status: str, reason: str | None = None) -> QaPair:
        return QaPair(
            id=uuid.uuid4().hex,
            space=SPACE,
            generator=generator,
            task_type="abstractive",
            doc_id="d1",
            question=uuid.uuid4().hex,
            answer=ANSWER,
            context=ANSWER,
            meta={},
            status=status,
            status_reason=reason,
            model="gen/model",
            question_hash=uuid.uuid4().hex,
        )

    WEB = StatusReason.WEB_ANSWERABLE.value
    with session_scope() as session:
        session.add_all(
            [
                pair("qa", PairStatus.ACTIVE.value),
                pair("qa", PairStatus.RETIRED.value, StatusReason.ROTATION.value),
                *(pair("qa", PairStatus.REJECTED.value, WEB) for _ in range(4)),
                # Neither counts: the owner's word, and not yet decided.
                pair("qa", PairStatus.REJECTED.value, StatusReason.OWNER.value),
                pair("qa", PairStatus.PENDING.value),
            ]
        )

    rates = top_up.survival_rates(SPACE, ["qa", "mcq"], _settings())

    assert rates == {"qa": pytest.approx(3 / 8), "mcq": 0.5}


# --- the build -----------------------------------------------------------------


@pytest.mark.needs_db
def test_a_short_kind_is_written_again_and_checked(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Build(monkeypatch)

    report = pipeline.generate_for_space(
        _space(), generators=KINDS, settings=_settings(), screen=True
    )

    qa, hop = report.kinds["qa"], report.kinds["multihop_synthesis"]
    # Each round adds the kind's whole budget: nothing of it survives.
    assert (qa.written, qa.topped_up) == (4 * (1 + top_up.TOP_UP_ROUNDS), 8)
    assert (hop.written, hop.topped_up) == (4, 0)
    assert any(note.startswith("top-up round 2: qa +4") for note in report.notes)
    assert _active() == {"multihop_synthesis": 4}
    assert report.screened is not None
    assert report.screened.web_answerable == qa.written


@pytest.mark.needs_db
def test_the_top_up_stops_at_its_cost_limit(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Build(monkeypatch, usd=1.0)

    report = pipeline.generate_for_space(
        _space(),
        generators=KINDS,
        settings=_settings(top_up_max_usd=0.5),
        screen=True,
    )

    qa = report.kinds["qa"]
    assert (qa.written, qa.topped_up) == (6, 2)
    assert qa.stopped == pipeline.COST_LIMIT
    assert "top-up stopped at its cost limit, $0.5" in report.notes


@pytest.mark.needs_db
@pytest.mark.parametrize("off", ["limit", "screening"])
def test_no_top_up_without_screening_or_a_limit(
    clean: None, monkeypatch: pytest.MonkeyPatch, off: str
) -> None:
    _Build(monkeypatch)

    report = pipeline.generate_for_space(
        _space(),
        generators=KINDS,
        settings=_settings(top_up_max_usd=0.0 if off == "limit" else 5.0),
        screen=off == "limit",
    )

    assert report.kinds["qa"].written == 4
    assert not any(note.startswith("top-up") for note in report.notes)


@pytest.mark.needs_db
@pytest.mark.parametrize("share", [1, 2])
def test_a_scoped_top_up_takes_no_passage_beyond_a_documents_share(
    clean: None, monkeypatch: pytest.MonkeyPatch, share: int
) -> None:
    _Build(monkeypatch)
    scope = frozenset(f"doc{d}" for d in range(4))

    report = pipeline.generate_for_space(
        _space(),
        generators=KINDS,
        settings=_settings(passages_per_document=share),
        screen=True,
        doc_ids=scope,
    )

    qa, hop = report.kinds["qa"], report.kinds["multihop_synthesis"]
    # qa never survives, yet its share is spent: nothing is left to top up.
    assert (qa.budget, qa.units_read, qa.written, qa.topped_up) == (
        4 * share * 2,
        4 * share,
        4 * share * 2,
        0,
    )
    assert (hop.budget, hop.units_read) == (4 * 2, 4)
    assert not any(note.startswith("top-up round") for note in report.notes)


@pytest.mark.needs_db
def test_a_capped_scoped_top_up_stays_within_the_share(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Build(monkeypatch)
    scope = frozenset(f"doc{d}" for d in range(4))

    report = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=_settings(passages_per_document=1),
        screen=True,
        doc_ids=scope,
        per_generator=2,
    )

    qa = report.kinds["qa"]
    # One passage for the budget, one per top-up round: each from a document
    # whose share is still unread.
    assert (qa.budget, qa.topped_up) == (2, 2 * top_up.TOP_UP_ROUNDS)
    assert qa.units_read == 1 + top_up.TOP_UP_ROUNDS
    with session_scope() as session:
        per_doc = Counter(
            session.execute(
                select(QaPair.doc_id).where(QaPair.space == SPACE)
            ).scalars()
        )
    assert len(per_doc) == qa.units_read
    assert set(per_doc.values()) == {2}


# --- extra passages in a scoped run ------------------------------------------


def _chunks_per_doc(generator: str) -> Counter[str]:
    with session_scope() as session:
        rows = session.execute(
            select(QaPair.doc_id, QaPair.chunk_id).where(
                QaPair.space == SPACE, QaPair.generator == generator
            )
        ).all()
    return Counter(doc for doc, _ in set(rows))


@pytest.mark.needs_db
def test_a_scoped_top_up_takes_extra_passages_of_each_document(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Build(monkeypatch)
    scope = frozenset(f"doc{d}" for d in range(4))

    report = pipeline.generate_for_space(
        _space(),
        generators=KINDS,
        settings=_settings(passages_per_document=1, top_up_passages_per_document=2),
        screen=True,
        doc_ids=scope,
    )

    qa, hop = report.kinds["qa"], report.kinds["multihop_synthesis"]
    # One passage of each document, then two more of each over two rounds.
    assert (qa.budget, qa.units_read, qa.topped_up) == (8, 4 + 8, 16)
    assert _chunks_per_doc("qa") == dict.fromkeys(scope, 3)
    # An article kind has one unit per document and takes nothing extra.
    assert (hop.units_read, hop.topped_up) == (4, 0)
    assert any(note.startswith("top-up: qa takes up to 2") for note in report.notes)


@pytest.mark.needs_db
def test_extra_passages_stay_within_the_top_up_cost_limit(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Build(monkeypatch, usd=1.0)
    scope = frozenset(f"doc{d}" for d in range(4))

    report = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=_settings(
            passages_per_document=1,
            top_up_passages_per_document=2,
            top_up_max_usd=0.5,
        ),
        screen=True,
        doc_ids=scope,
    )

    qa = report.kinds["qa"]
    assert (qa.units_read, qa.topped_up) == (5, 2)
    assert qa.stopped == pipeline.COST_LIMIT


def test_control_and_article_kinds_get_no_reserve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "_processed_ids", lambda *a: set())
    specs = list(GENERATORS.values())
    extractive = tuple(s.key for s in specs if s.key in pipeline.EXTRACTIVE_KEYS)
    queues = pipeline._queues(
        SPACE,
        specs,
        extractive,
        _documents(3, 4),
        "c1",
        _settings(),
        pipeline.GenerationReport(space=SPACE, cohort="c1"),
        per_document=1,
        extra=2,
    )

    for queue in queues:
        units = Counter(doc.doc_id for doc, _ in queue.units)
        reserve = Counter(doc.doc_id for doc, _ in queue.reserve)
        assert set(units.values()) == {1}, queue.label
        spec = queue.spec
        if spec is not None and (spec.is_control or spec.scope.value == "document"):
            assert not reserve, queue.label
        else:
            assert set(reserve.values()) == {2}, queue.label
            assert not {c for _, c in queue.units} & {c for _, c in queue.reserve}


@pytest.mark.needs_db
def test_extra_passages_off_by_default(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Build(monkeypatch)
    assert Settings().top_up_passages_per_document == 0

    report = pipeline.generate_for_space(
        _space(),
        generators=("qa",),
        settings=_settings(passages_per_document=1),
        screen=True,
        doc_ids=frozenset(f"doc{d}" for d in range(4)),
    )

    assert (report.kinds["qa"].units_read, report.kinds["qa"].topped_up) == (4, 0)
    assert _chunks_per_doc("qa") == dict.fromkeys((f"doc{d}" for d in range(4)), 1)


@pytest.mark.needs_db
def test_extra_passages_and_the_control_share_together(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Build(monkeypatch)
    scope = frozenset(f"doc{d}" for d in range(4))
    conf = _settings(passages_per_document=1, top_up_passages_per_document=1)

    report = pipeline.generate_for_space(
        _space(), generators=KINDS, settings=conf, screen=True, doc_ids=scope
    )
    assert report.kinds["qa"].topped_up == 8
    # Trick questions on the same documents, as a control kind would leave them.
    with session_scope() as session:
        for n in range(8):
            session.add(
                QaPair(
                    id=f"trick-{n}",
                    space=SPACE,
                    generator="unanswerable_property",
                    task_type="negative",
                    doc_id=f"doc{n % 4}",
                    question=f"Trick {n}?",
                    answer="",
                    context="",
                    meta={"grading": "behavior"},
                    status=PairStatus.ACTIVE.value,
                    model="gen/model",
                    question_hash=f"trick-{n}",
                )
            )

    filtered = pipeline.filter_and_rotate(
        _space(), settings=conf, rotate_anyway=True, doc_ids=scope
    )

    # Eight multihop questions are asked: two trick questions fit under 25%.
    assert _active() == {"multihop_synthesis": 8, "unanswerable_property": 2}
    assert filtered.control_share == 6
