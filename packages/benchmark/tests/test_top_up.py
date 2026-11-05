"""The top-up: more of each kind the checks left short of its target.

After the build's questions are checked, a kind below its target gets more
written and checked the same way, sized by its survival rate on the target,
for at most ``TOP_UP_ROUNDS`` rounds and ``top_up_max_usd``.
"""

from __future__ import annotations

import dataclasses
import itertools
import uuid
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
    assert top_up.kind_targets(keys, 10, Settings()) == dict.fromkeys(keys, 10)
    capped = Settings(dataset_max_pairs=10)
    assert top_up.kind_targets(keys, 10, capped) == dict.fromkeys(keys, 4)
    assert top_up.kind_targets(keys, 2, capped) == dict.fromkeys(keys, 2)


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
