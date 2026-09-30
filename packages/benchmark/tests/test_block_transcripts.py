"""The exchange behind a block's verdict, kept round by round and trial by trial.

Both blocks used to record their number and throw the conversation away, which
is enough to publish a figure and not enough to check one: whether round 3 was
really a surrender or the judge misread a hedge, whether the repeats differ in
substance or only in wording, is a question about what was said.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import Settings, Verdict
from syft_benchmark.llm import Provider
from syft_benchmark.runs import blocks
from syft_benchmark.runs.blocks import (
    DENIAL_PHRASES,
    TRANSCRIPT_CHARS,
    run_denial_loop,
    run_monte_carlo,
)
from syft_benchmark.runs.judge import Grade


def _settings(**kwargs: object) -> Settings:
    return Settings(spaces_file="config/spaces.json", **kwargs)  # type: ignore[arg-type]


def _subject() -> Provider:
    return Provider(role="subject", url="http://localhost:11434", api_key="", model="m")


def _verdict(which: Verdict) -> Grade:
    return Grade(which, "because")


# --- pressure ----------------------------------------------------------------


def test_the_denial_loop_keeps_what_was_said_in_each_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    said = ["Still the same.", "I stand by it.", "Fine, I was wrong."]
    calls = iter(said)

    monkeypatch.setattr(blocks, "chat", lambda *a, **k: (next(calls), None))
    monkeypatch.setattr(blocks, "detect_abstain", lambda _answer: False)
    # Correct twice, then not — the model gives in on the third objection.
    grades = iter([Verdict.CORRECT, Verdict.CORRECT, Verdict.HALLUCINATE])
    monkeypatch.setattr(blocks, "grade", lambda *a, **k: _verdict(next(grades)))

    outcome = run_denial_loop(
        "What port?",
        "5442",
        "5442",
        subject=_subject(),
        settings=_settings(denial_rounds=5),
    )

    assert outcome.flipped is True
    assert outcome.flip_round == 3
    # Held two of the five it was configured to put, which is what the page says.
    assert (outcome.rounds, outcome.limit) == (3, 5)
    assert [entry["round"] for entry in outcome.log] == [1, 2, 3]
    assert [entry["answer"] for entry in outcome.log] == said
    assert outcome.log[0]["objection"] == DENIAL_PHRASES[0]


def test_a_model_that_holds_records_every_round_it_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(blocks, "chat", lambda *a, **k: ("5442, still.", None))
    monkeypatch.setattr(blocks, "detect_abstain", lambda _answer: False)
    monkeypatch.setattr(blocks, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    outcome = run_denial_loop(
        "What port?",
        "5442",
        "5442",
        subject=_subject(),
        settings=_settings(denial_rounds=4),
    )

    assert outcome.flipped is False
    assert (outcome.rounds, outcome.limit) == (4, 4)
    assert len(outcome.log) == 4


def test_a_transcript_does_not_carry_the_whole_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evidence, not a second copy of the corpus."""
    monkeypatch.setattr(blocks, "chat", lambda *a, **k: ("x" * 9000, None))
    monkeypatch.setattr(blocks, "detect_abstain", lambda _answer: False)
    monkeypatch.setattr(blocks, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    outcome = run_denial_loop(
        "What port?",
        "5442",
        "5442",
        subject=_subject(),
        settings=_settings(denial_rounds=1),
    )

    assert len(outcome.log[0]["answer"]) == TRANSCRIPT_CHARS


# --- repeats -----------------------------------------------------------------


def test_the_repeats_keep_every_trial_with_its_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grades = iter(
        [Verdict.CORRECT, Verdict.HALLUCINATE, Verdict.CORRECT, Verdict.CORRECT]
    )
    monkeypatch.setattr(blocks, "grade", lambda *a, **k: _verdict(next(grades)))

    asked: list[float] = []

    def ask(_question: str, temperature: float) -> str:
        asked.append(temperature)
        return f"answer at {temperature}"

    outcome = run_monte_carlo(
        "What port?",
        "5442",
        ask=ask,
        settings=_settings(monte_carlo_temperatures=[0.3, 0.9], monte_carlo_trials=2),
    )

    assert outcome.trials == 4
    assert [entry["trial"] for entry in outcome.log] == [1, 2, 3, 4]
    assert [entry["temperature"] for entry in outcome.log] == [0.3, 0.3, 0.9, 0.9]
    assert [entry["correct"] for entry in outcome.log] == [True, False, True, True]
    assert outcome.log[0]["answer"] == "answer at 0.3"


def test_a_failed_repeat_leaves_no_trial_behind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A call that never came back is not an answer the model gave."""
    monkeypatch.setattr(blocks, "grade", lambda *a, **k: _verdict(Verdict.CORRECT))

    answers = iter(["fine", f"{blocks.ERROR_PREFIX} the provider refused"])

    def ask(_question: str, _temperature: float) -> str:
        return next(answers)

    outcome = run_monte_carlo(
        "What port?",
        "5442",
        ask=ask,
        settings=_settings(monte_carlo_temperatures=[0.3], monte_carlo_trials=2),
    )

    assert outcome.trials == 1
    assert len(outcome.log) == 1
    assert outcome.note.startswith("failed attempts")


def test_the_views_carry_the_transcript_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """What the run's own page reads, straight off a stored row's `extra`."""
    from syft_benchmark.runs.judge_stage import _denial_of, _repeats_of

    extra: dict[str, Any] = {
        "denial": {
            "rounds": 3,
            "flipped": True,
            "flip_round": 3,
            "limit": 5,
            "log": [{"round": 1, "objection": "Are you sure?", "answer": "yes"}],
        },
        "monte_carlo": {
            "trials": 2,
            "consistency": 0.5,
            "log": [{"trial": 1, "temperature": 0.3, "answer": "a", "correct": True}],
        },
    }

    denial = _denial_of(extra)
    assert denial is not None
    assert denial.limit == 5
    assert denial.log[0]["objection"] == "Are you sure?"

    repeats = _repeats_of(extra)
    assert repeats is not None
    assert repeats.log[0]["temperature"] == 0.3


def test_a_row_measured_before_transcripts_reads_as_having_none() -> None:
    """An exchange that was never recorded cannot be reconstructed, and the
    reader has to be able to tell that from one that was empty."""
    from syft_benchmark.runs.judge_stage import _denial_of

    denial = _denial_of({"denial": {"rounds": 2, "flipped": False}})
    assert denial is not None
    assert denial.log == []
    assert denial.limit == 0
