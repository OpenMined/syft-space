"""The control share of a document-scoped run.

After a scoped run's filter pass, false premise and trick questions together
take at most ``control_max_share`` of what it asks; the rest are retired with
the reason ``control_share``, spread over the articles and both kinds, and
never come back.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import (
    DatasetMode,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
)
from syft_benchmark.db import Job, QaPair, session_scope
from syft_benchmark.generation import pipeline
from syft_benchmark.generation.rotation import control_allowance, rotate
from syft_benchmark.report import job_params
from syft_benchmark.report.run_view import _funnel
from syft_benchmark.runs import evaluation_gate
from syft_benchmark.runs.execute import _active_pairs
from syft_benchmark.sources import Document

from fakes import ChromaStub, openrouter_settings
from support import WEB_CHECK_MODEL, add_rows

KEY = "pytest-control-share"
JOB = "pytest-control-share-job"
T0 = datetime(2026, 10, 1, tzinfo=UTC)
DOCS = [f"doc-{n}" for n in range(10)]
SCOPE = frozenset(DOCS)
CONTROL = {"false_premise", "unanswerable_property"}
# The rig's combination of four runs: 55 main questions, 19 trick ones.
MIX = {
    "false_premise": 23,
    "multihop_synthesis": 19,
    "qa": 9,
    "mcq": 4,
    "unanswerable_property": 19,
}
TASK = {
    "false_premise": "negative",
    "unanswerable_property": "negative",
    "multihop_synthesis": "abstractive",
    "qa": "abstractive",
    "mcq": "choice",
}


def _row(pair_id: str, generator: str, doc_id: str, n: int) -> QaPair:
    control = generator in CONTROL
    return QaPair(
        id=pair_id,
        space=KEY,
        job_id=JOB,
        generator=generator,
        task_type=TASK[generator],
        doc_id=doc_id,
        question=f"Question {pair_id}?",
        answer="",
        context="",
        status=PairStatus.ACTIVE.value,
        model="gen/model",
        question_hash=pair_id,
        meta=(
            {}
            if control
            else {"web_check": {"model": WEB_CHECK_MODEL, "verdict": "hallucinate"}}
        ),
        created_at=T0 + timedelta(seconds=n),
    )


def _seed(mix: dict[str, int] = MIX) -> None:
    add_rows(Job(id=JOB, target=KEY, state="succeeded", params={}))
    rows = []
    n = 0
    for generator, count in mix.items():
        for i in range(count):
            rows.append(_row(f"{generator}-{i}", generator, DOCS[i % len(DOCS)], n))
            n += 1
    add_rows(*rows)


def _settings(**kwargs: Any) -> Settings:
    return openrouter_settings(filter_model=WEB_CHECK_MODEL, **kwargs)


def _space() -> SpaceConfig:
    return SpaceConfig(key=KEY, url="http://space", endpoint="ep")


def _rows() -> list[QaPair]:
    with session_scope() as session:
        rows = list(session.scalars(select(QaPair).where(QaPair.space == KEY)))
        for row in rows:
            session.expunge(row)
    return rows


def _asked(conf: Settings) -> Counter[str]:
    return Counter(
        row.generator for row in _active_pairs(KEY, None, conf, doc_ids=SCOPE)
    )


@pytest.mark.parametrize(
    ("ordinary", "control", "share", "kept"),
    [
        (32, 42, 0.25, 10),  # 10 of 42 asked: 23.8%
        (30, 20, 0.25, 10),  # exactly a quarter
        (100, 3, 0.25, 3),  # under the share: all stay
        (0, 5, 0.25, 1),  # nothing else to ask: one stays
        (2, 5, 0.25, 1),
        (32, 42, 0.0, 42),  # off
        (4, 0, 0.25, 0),
    ],
)
def test_the_allowance_keeps_control_within_the_share(
    ordinary: int, control: int, share: float, kept: int
) -> None:
    assert control_allowance(ordinary, control, share) == kept


def test_the_share_is_on_by_default_and_methodology() -> None:
    assert Settings().control_max_share == 0.25
    assert "control_max_share" not in job_params.HASH_EXCLUDED
    assert "top_up_passages_per_document" not in job_params.HASH_EXCLUDED
    base = job_params.settings_snapshot(Settings())
    for key, value in (
        ("control_max_share", 0.0),
        ("top_up_passages_per_document", 2),
    ):
        assert job_params.settings_hash({**base, key: value}) != (
            job_params.settings_hash(base)
        )


@pytest.mark.needs_db
@pytest.mark.parametrize("rotate_anyway", [False, True])
def test_a_scoped_run_retires_the_control_questions_over_the_share(
    clean: Any, rotate_anyway: bool
) -> None:
    _seed()
    conf = _settings()  # control_max_share unset: the default quarter

    report = pipeline.filter_and_rotate(
        _space(), settings=conf, rotate_anyway=rotate_anyway, doc_ids=SCOPE
    )

    asked = _asked(conf)
    assert sum(asked[k] for k in CONTROL) == 10
    assert sum(asked.values()) == 42
    # Spread over the articles and the two kinds.
    assert (asked["false_premise"], asked["unanswerable_property"]) == (5, 5)
    kept = [r for r in _rows() if r.generator in CONTROL and r.status == "active"]
    assert Counter(r.doc_id for r in kept) == dict.fromkeys(DOCS, 1)
    retired = [r for r in _rows() if r.status_reason == "control_share"]
    assert len(retired) == 32
    assert {r.status for r in retired} == {PairStatus.RETIRED.value}
    assert report.control_share == 32
    assert "32 over the control share" in report.line()
    if report.rotation is not None:
        assert report.rotation.active == 42
    assert evaluation_gate(KEY, conf, doc_ids=SCOPE) == ""

    # The funnel counts the main questions retired (trick ones are counted apart).
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        funnel = _funnel(session, job, set(), 0, 0)
    assert funnel["removed"] == {StatusReason.CONTROL_SHARE.value: 18}


@pytest.mark.needs_db
def test_retired_control_questions_never_come_back(clean: Any) -> None:
    _seed()
    conf = _settings()
    pipeline.filter_and_rotate(_space(), settings=conf, doc_ids=SCOPE)
    retired = {r.id for r in _rows() if r.status_reason == "control_share"}

    # Again over the same scope: nothing more leaves, nothing returns.
    again = pipeline.filter_and_rotate(_space(), settings=conf, doc_ids=SCOPE)
    assert again.control_share == 0
    # A scoped recompute, and a window recompute in every mode.
    rotate(KEY, {}, settings=conf, scope=SCOPE)
    for mode in DatasetMode:
        rotate(
            KEY,
            dict.fromkeys(DOCS, T0),
            settings=conf.model_copy(update={"dataset_mode": mode}),
        )
    assert {r.id for r in _rows() if r.status_reason == "control_share"} == retired
    assert {r.status for r in _rows() if r.id in retired} == {"retired"}
    assert sum(_asked(conf)[k] for k in CONTROL) == 10


@pytest.mark.needs_db
def test_zero_turns_the_share_off(clean: Any) -> None:
    _seed()
    conf = _settings(control_max_share=0.0)

    report = pipeline.filter_and_rotate(_space(), settings=conf, doc_ids=SCOPE)

    assert report.control_share == 0
    assert sum(_asked(conf)[k] for k in CONTROL) == 42


@pytest.mark.needs_db
def test_one_control_question_stays_when_nothing_else_is_asked(clean: Any) -> None:
    _seed({"false_premise": 3, "unanswerable_property": 2})

    pipeline.filter_and_rotate(_space(), settings=_settings(), doc_ids=SCOPE)

    assert sum(_asked(_settings()).values()) == 1


@pytest.mark.needs_db
def test_a_window_run_keeps_its_control_questions(
    clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed()
    documents = [
        Document(doc_id=doc, title=doc, url="", source="", file_name="", chunks=[])
        for doc in DOCS
    ]
    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: documents)

    report = pipeline.filter_and_rotate(
        _space(), settings=_settings(), rotate_anyway=True
    )

    assert report.control_share == 0
    assert not [r for r in _rows() if r.status_reason == "control_share"]
