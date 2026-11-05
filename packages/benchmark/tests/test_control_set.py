"""The control set: questions with no answer, and checking their labelling.

What is checked is what this set is more dangerous without than without the set
at all: an unchecked negative does not enter the measurement.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import PairStatus, Settings, StatusReason
from syft_benchmark.db import QaPair
from syft_benchmark.generation import control, filter_stage, gate_unanswerable
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.negative import clean_false_premise, clean_unanswerable
from syft_benchmark.llm import LLMError, judge_provider

from fakes import JudgeRecorder

DOC = (
    "Space registers with the Hub. The Hub stores endpoint metadata in "
    "PostgreSQL. The benchmark database listens on port 5442."
)


def _no_hits(_question: str) -> list[str]:
    return []


def _broken(_question: str) -> list[str]:
    raise RuntimeError("the endpoint is unavailable")


# --- parsing the generator's answer ----------------------------------------


def test_unanswerable_keeps_what_is_missing() -> None:
    """There is no reference answer, only a description of what is missing.

    That description is kept.
    """
    pairs, rejected = clean_unanswerable(
        [
            {
                "question": "What TLS version does the Hub require?",
                "subject": "Hub",
                "missing": "TLS version",
            }
        ],
        1,
        DOC,
    )
    assert not rejected
    assert pairs[0].meta["missing"] == "TLS version"
    assert pairs[0].meta["grading"] == "behavior"
    assert "TLS version" in pairs[0].answer


def test_unanswerable_without_the_missing_part_is_rejected() -> None:
    """A negative that did not say what is missing cannot be checked."""
    _pairs, rejected = clean_unanswerable(
        [{"question": "What TLS version does the Hub require?"}], 1, DOC
    )
    assert rejected


def test_false_premise_checks_the_grounds_not_the_correction() -> None:
    """The correction is reworded; it is the grounds that must follow from the chunk.

    The same reason as for "two truths and a lie": checking the reference answer
    itself for grounding here would reject exactly what the item was created for.
    """
    pairs, rejected = clean_false_premise(
        [
            {
                "question": "Why did the Hub move its metadata to SQLite?",
                "premise": "the Hub moved to SQLite",
                "correction": "No such migration happened.",
                "grounds": ["The Hub stores endpoint metadata in PostgreSQL"],
            }
        ],
        1,
        DOC,
    )
    assert not rejected
    assert pairs[0].meta["claims"] == ["The Hub stores endpoint metadata in PostgreSQL"]
    assert pairs[0].meta["grading"] == "judge"


def test_false_premise_needs_a_correction() -> None:
    """Without a correction the right behaviour is undefined."""
    _pairs, rejected = clean_false_premise(
        [{"question": "Why did the Hub move to SQLite?", "premise": "moved"}], 1, DOC
    )
    assert rejected


# --- the gate --------------------------------------------------------------


def test_empty_retrieval_means_the_question_is_unanswerable() -> None:
    """Retrieval returned nothing: this endpoint certainly cannot answer."""
    gate = gate_unanswerable(
        "What TLS version?", _no_hits, judge=judge_provider(_settings())
    )
    assert gate.clear
    assert gate.fragments == 0


def test_a_broken_search_never_admits_a_candidate() -> None:
    """Not knowing is not fitness.

    A candidate it cannot be said of whether it is answerable does not enter the
    measurement: otherwise the benchmark would charge fabrication where an
    answer could have existed.
    """
    gate = gate_unanswerable(
        "What TLS version?", _broken, judge=judge_provider(_settings())
    )
    assert not gate.clear
    assert not gate.checked


# --- the false-premise gate --------------------------------------------------

CORRECTION_HIT = "The Hub stores endpoint metadata in PostgreSQL."


def _settings() -> Settings:
    return Settings(judge_model="judge/model", judge_models=["judge/model"])


def _premise_row() -> QaPair:
    return QaPair(
        id="fp-1",
        space="pytest-control-set",
        generator="false_premise",
        task_type="negative",
        doc_id="doc-1",
        question="Why did the Hub move its endpoint metadata to SQLite?",
        answer="The Hub stores endpoint metadata in PostgreSQL, not SQLite.",
        context=DOC,
        status=PairStatus.PENDING.value,
        model="gen/model",
        question_hash="fp-1",
        meta={
            "premise": "the Hub moved its metadata to SQLite",
            "claims": ["The Hub stores endpoint metadata in PostgreSQL."],
            "grading": "judge",
        },
    )


def _screen(row: QaPair, retrieve: Any) -> tuple[Any, ...]:
    conf = _settings()
    return filter_stage._screen_pair(
        row, GENERATORS[row.generator], retrieve, conf, judge_provider(conf)
    )


def test_a_false_premise_with_its_correction_found_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge = JudgeRecorder(
        '{"answered": true, "where": "stores endpoint metadata in PostgreSQL"}'
    )
    monkeypatch.setattr(control, "chat", judge)

    status, reason, note, meta = _screen(_premise_row(), lambda _q: [CORRECTION_HIT])

    assert status is PairStatus.ACTIVE
    assert reason is None
    assert note.startswith("correction found in the archive")
    assert meta["gate_checked"] is True
    system, user = judge.prompts[0]
    assert system == control._ANSWERABLE_SYSTEM
    assert "the Hub moved its metadata to SQLite" in user
    assert "not SQLite" in user  # the correction
    assert "- The Hub stores endpoint metadata in PostgreSQL." in user  # claims
    assert CORRECTION_HIT in user
    assert meta[filter_stage.GATE_CALL]["user"] == user


def test_a_false_premise_without_its_correction_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        control, "chat", JudgeRecorder('{"answered": false, "where": ""}')
    )

    status, reason, note, meta = _screen(
        _premise_row(), lambda _q: ["The Hub has a web interface."]
    )

    assert status is PairStatus.REJECTED
    assert reason is StatusReason.RETRIEVAL_GATE
    assert note.startswith("correction not found in the archive")
    assert meta["gate_checked"] is True


def test_a_false_premise_with_nothing_retrieved_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge = JudgeRecorder('{"answered": true}')
    monkeypatch.setattr(control, "chat", judge)

    status, reason, note, _ = _screen(_premise_row(), _no_hits)

    assert status is PairStatus.REJECTED
    assert reason is StatusReason.RETRIEVAL_GATE
    assert note.startswith("correction not found in the archive")
    assert judge.prompts == []


def test_a_false_premise_whose_search_fails_is_not_checked() -> None:
    status, reason, note, meta = _screen(_premise_row(), _broken)

    assert status is PairStatus.REJECTED
    assert reason is StatusReason.RETRIEVAL_GATE
    assert note.startswith("retrieval unreachable")
    assert meta["gate_checked"] is False


def test_a_false_premise_whose_judge_fails_is_not_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(*_a: Any, **_k: Any) -> tuple[str, dict[str, Any]]:
        raise LLMError("the judge is down")

    monkeypatch.setattr(control, "chat", failing)

    status, _, note, meta = _screen(_premise_row(), lambda _q: [CORRECTION_HIT])

    assert status is PairStatus.REJECTED
    assert note.startswith("the gate did not run")
    assert meta["gate_checked"] is False


def test_a_trick_question_still_goes_through_the_unanswerable_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge = JudgeRecorder('{"answered": true, "where": "port 5442"}')
    monkeypatch.setattr(control, "chat", judge)
    row = _premise_row()
    row.generator = "unanswerable_property"
    row.question = "What port does the benchmark database listen on?"
    row.meta = {"missing": "the port", "grading": "behavior"}

    status, reason, note, _ = _screen(row, lambda _q: [DOC])

    assert status is PairStatus.REJECTED
    assert reason is StatusReason.RETRIEVAL_GATE
    assert note.startswith("retrieval answers the question")
    assert judge.prompts[0][0] == control._GATE_SYSTEM
