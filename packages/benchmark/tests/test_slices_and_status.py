"""The report cuts, the state of a measurement and console judging.

What is tested is what tells a useful report from a summary: where exactly the
model errs, whether the judges can be trusted, what is left to finish and how to
judge answers without an API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from syft_benchmark.config import ContextMode, EvalBlock, Verdict
from syft_benchmark.report import slices as slices_mod
from syft_benchmark.report.slices import (
    AGREEMENT_FLOOR,
    GeneratorSlice,
    JudgePair,
    agreement_lines,
    average_agreement,
    by_generator,
    corpus_exposure,
    judge_agreement,
)
from syft_benchmark.runs.console import parse_verdicts
from syft_benchmark.runs.status import (
    GeneratorCoverage,
    PassStatus,
    SpaceStatus,
    collect,
)

_NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


class _Row:
    """A result row in the volume the cuts need."""

    def __init__(
        self,
        qa_id: str,
        verdict: str = Verdict.CORRECT.value,
        answer: str = "Port 5442.",
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.qa_id = qa_id
        self.verdict = verdict
        self.answer = answer
        self.extra = extra or {}


class _Pair:
    def __init__(self, qa_id: str, generator: str) -> None:
        self.id = qa_id
        self.generator = generator


class _Store:
    """A database in the volume of the two queries the cut makes."""

    def __init__(self, pairs: list[_Pair]) -> None:
        self.pairs = pairs

    def __call__(self, *args: Any, **kwargs: Any) -> _Store:
        return self

    def __enter__(self) -> _Store:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def execute(self, stmt: Any) -> _Store:
        return self

    def all(self) -> list[Any]:
        return self.pairs


# --- the cut by generator --------------------------------------------------


def test_the_generator_slice_splits_one_share_into_the_real_ones(
    monkeypatch: Any,
) -> None:
    """The main thing the cut exists for.

    The model holds dates confidently and falls apart on connecting facts; in the
    summary that will be one share, by which there is nothing to fix.
    """
    rows = [
        _Row("a1"),
        _Row("a2"),
        _Row("b1", Verdict.HALLUCINATE.value),
        _Row("b2", Verdict.HALLUCINATE.value),
    ]
    monkeypatch.setattr(slices_mod, "_latest_results", lambda *a, **k: rows)
    monkeypatch.setattr(
        slices_mod,
        "session_scope",
        _Store(
            [
                _Pair("a1", "temporal_masking"),
                _Pair("a2", "temporal_masking"),
                _Pair("b1", "multihop_synthesis"),
                _Pair("b2", "multihop_synthesis"),
            ]
        ),
    )

    got = by_generator("docs", ContextMode.CLOSED_BOOK)
    by_key = {entry.generator: entry for entry in got}

    assert by_key["temporal_masking"].accuracy == 1.0
    assert by_key["multihop_synthesis"].accuracy == 0.0
    # Worst first: a report is read for what is broken.
    assert got[0].generator == "multihop_synthesis"


def test_a_failed_call_never_lands_in_a_generator_share(monkeypatch: Any) -> None:
    """A failed call speaks about the rig, not about the item type."""
    rows = [_Row("a1"), _Row("a2", answer="ERROR: timeout")]
    monkeypatch.setattr(slices_mod, "_latest_results", lambda *a, **k: rows)
    monkeypatch.setattr(
        slices_mod,
        "session_scope",
        _Store([_Pair("a1", "mcq"), _Pair("a2", "mcq")]),
    )

    entry = by_generator("docs", ContextMode.CLOSED_BOOK)[0]
    assert entry.graded == 1
    assert entry.failed == 1
    assert entry.accuracy == 1.0


# --- judge agreement -------------------------------------------------------


def _judged(monkeypatch: Any, verdicts: dict[str, dict[str, str]]) -> None:
    monkeypatch.setattr(slices_mod, "judges_seen", lambda *a, **k: sorted(verdicts))

    def latest(space: Any, mode: Any, block: Any, model: Any, judge: Any, exp: Any):
        return [_Row(qa, v) for qa, v in verdicts[judge].items()]

    monkeypatch.setattr(slices_mod, "_latest_results", latest)


def test_judges_that_never_disagree_score_one(monkeypatch: Any) -> None:
    _judged(
        monkeypatch,
        {
            "judge/a": {"q1": "correct", "q2": "abstain"},
            "judge/b": {"q1": "correct", "q2": "abstain"},
        },
    )
    pair = judge_agreement("docs", ContextMode.CLOSED_BOOK)[0]
    assert pair.shared == 2
    assert pair.rate == 1.0


def test_agreement_counts_only_what_both_judges_saw(monkeypatch: Any) -> None:
    """A recusal and an interrupted run leave the judges with different sets.

    Dividing agreement by the full set would mean recording someone else gap as a
    disagreement — and the panel would look split where it was simply not asked.
    """
    _judged(
        monkeypatch,
        {
            "judge/a": {"q1": "correct", "q2": "correct", "q3": "correct"},
            "judge/b": {"q1": "correct"},
        },
    )
    pair = judge_agreement("docs", ContextMode.CLOSED_BOOK)[0]
    assert pair.shared == 1
    assert pair.rate == 1.0


def test_one_judge_is_no_collegium(monkeypatch: Any) -> None:
    monkeypatch.setattr(slices_mod, "judges_seen", lambda *a, **k: ["judge/a"])
    assert judge_agreement("docs", ContextMode.CLOSED_BOOK) == []


def test_the_average_is_weighted_by_shared_questions() -> None:
    """A pair that agreed on three questions is not a pair that agreed on a hundred."""
    pairs = [
        JudgePair("a", "b", shared=100, agreed=100),
        JudgePair("a", "c", shared=2, agreed=0),
    ]
    average = average_agreement(pairs)
    assert average is not None
    assert average > 0.9


def test_low_agreement_is_called_out_in_the_report(monkeypatch: Any) -> None:
    """The reader must not be silently left with percentages that mean nothing."""
    monkeypatch.setattr(
        slices_mod,
        "_combos",
        lambda results: [("docs", ContextMode.CLOSED_BOOK, EvalBlock.DIRECT, "m")],
    )
    monkeypatch.setattr(
        slices_mod,
        "judge_agreement",
        lambda *a, **k: [JudgePair("a", "b", shared=100, agreed=40)],
    )

    text = "\n".join(agreement_lines([]))
    assert "40%" in text
    assert "noise" in text
    assert f"{AGREEMENT_FLOOR:.0%}" in text


# --- the state of a measurement --------------------------------------------


def _pass(**kwargs: Any) -> PassStatus:
    base: dict[str, Any] = {
        "space": "docs",
        "context_mode": ContextMode.CLOSED_BOOK,
        "context_source": "none",
        "block": EvalBlock.DIRECT,
        "model": "vendor/m",
        "judge": "judge/a",
        "total": 50,
        "graded": 50,
        "failed": 0,
        "pending": 0,
        "last_at": _NOW,
    }
    base.update(kwargs)
    return PassStatus(**base)


def test_missing_is_what_was_never_asked() -> None:
    entry = _pass(graded=30, failed=2, pending=3)
    assert entry.missing == 15
    assert not entry.done


def test_a_finished_pass_says_so() -> None:
    assert _pass().done


def test_each_state_gets_its_own_cure() -> None:
    """A failure is cured by rerunning, an awaited verdict by judging.

    A command unable to say what to do next saves not time but letters.
    """
    holes = SpaceStatus("docs", 50, "", [_pass(graded=40, failed=10)])
    assert any("--resume" in step for step in holes.advice())

    waiting = SpaceStatus("docs", 50, "", [_pass(graded=40, pending=10)])
    advice = " ".join(waiting.advice())
    assert "export-judging" in advice
    assert "--resume" not in advice

    done = SpaceStatus("docs", 50, "", [_pass()])
    assert any("report" in step for step in done.advice())


def test_nothing_collected_is_not_a_crash(monkeypatch: Any) -> None:
    class _Empty:
        def __call__(self, *a: Any, **k: Any) -> _Empty:
            return self

        def __enter__(self) -> _Empty:
            return self

        def __exit__(self, *exc: Any) -> bool:
            return False

        def execute(self, stmt: Any) -> _Empty:
            return self

        def all(self) -> list[Any]:
            return []

    import syft_benchmark.runs.status as status_mod

    monkeypatch.setattr(status_mod, "session_scope", _Empty())
    state = collect("docs", total=50)
    assert state.passes == []
    assert state.total == 50


# --- console verdicts ------------------------------------------------------


def test_a_json_array_of_verdicts_is_read() -> None:
    parsed = parse_verdicts(
        'Here are the verdicts: [{"id": "abc123", "correct": true, '
        '"reasoning": "matched"},'
        ' {"id": "def456", "correct": false, "reasoning": "missed"}]'
    )
    assert parsed["abc123"] == (True, "matched")
    assert parsed["def456"][0] is False


def test_a_line_per_verdict_is_read_too() -> None:
    """The form is set by the chat, not by us: demanding one would break the work."""
    parsed = parse_verdicts(
        "abc123: correct — matches the gold answer\ndef456: incorrect — another port"
    )
    assert parsed["abc123"][0] is True
    assert parsed["def456"] == (False, "another port")


def test_english_verdicts_are_read() -> None:
    parsed = parse_verdicts("abc123: correct - matches\ndef456: wrong - no")
    assert parsed["abc123"][0] is True
    assert parsed["def456"][0] is False


def test_an_empty_file_yields_nothing() -> None:
    assert parse_verdicts("did not judge at all") == {}


def test_an_item_without_a_verdict_is_skipped() -> None:
    """A missing verdict is not "incorrect": it is a missing verdict."""
    parsed = parse_verdicts(
        '[{"id": "abc123", "reasoning": "did not understand the question"}]'
    )
    assert parsed == {}


def test_a_generator_slice_reports_its_own_shares() -> None:
    entry = GeneratorSlice(
        generator="mcq", graded=10, correct=6, abstain=1, hallucinate=3, failed=2
    )
    assert entry.accuracy == 0.6
    assert entry.abstain_rate == 0.1
    assert entry.hallucination_rate == 0.3


def test_paths_in_advice_name_the_space() -> None:
    """The advice has to be executable as it stands, not "a command like this"."""
    state = SpaceStatus("docs", 10, "", [_pass(graded=5, failed=5)])
    assert any("evaluate docs" in step for step in state.advice())


def test_a_frozen_slice_is_named_in_the_status() -> None:
    state = SpaceStatus("docs", 10, str(Path("config/slice.json")), [])
    assert "slice.json" in state.frozen


def test_an_empty_status_does_not_claim_everything_is_done() -> None:
    """ "Everything is done" on an empty measurement is an untruth of exactly the
    kind the command exists to prevent."""
    advice = " ".join(SpaceStatus("docs", 50, "", []).advice())
    assert "nothing has been collected" in advice
    assert "report" not in advice


# --- what goes to a console judge ------------------------------------------


def test_only_the_direct_block_goes_to_a_console_judge() -> None:
    """Pressure and repeats issue their verdicts AS THEY GO.

    `denial_loop` judges every round in order to work out at which one the model
    gave in, `monte_carlo` every trial. A console judge sees one recorded answer
    and knows nothing of the rounds: its verdict, placed into such a block row,
    would carry off someone else decision about the surrender and pass it off as
    its own.
    """
    import inspect

    from syft_benchmark.runs import console

    source = inspect.getsource(console._judging_tasks)
    assert "Run.block == EvalBlock.DIRECT.value" in source


def test_a_reused_answer_is_marked_in_the_audit() -> None:
    """The call described by the neighbouring fields did not happen in this run.

    For an auditor this is no trifle: otherwise the log would show a model that
    answered in zero seconds, and a call that never took place.
    """
    from syft_benchmark.config import ContextSource, Settings
    from syft_benchmark.runs import Asked, Grade, audit_record

    asked = Asked(
        answer="Port 5442.",
        latency=12.5,
        system="s",
        user="u",
        retrieval={"retrieval_hit": None, "retrieval_rank": None, "retrieved": []},
        context_source=ContextSource.NONE,
        usage={"finish_reason": "stop", "reused": True, "elapsed": 12.5},
    )
    record = audit_record(
        asked,
        Grade(Verdict.CORRECT, "ok"),
        Settings(),  # type: ignore[call-arg]
    )
    assert record["call"]["reused"] is True


def test_a_reused_answer_keeps_the_time_it_actually_cost() -> None:
    """Otherwise the log would hold a model that answers in zero seconds."""
    from syft_benchmark.runs.execute import _elapsed

    assert _elapsed({"elapsed": 12.5}, started=0.0) == 12.5
    # Without a recorded time we count as before — by the caller clock.
    assert _elapsed({}, started=0.0) > 0


# --- coverage by item type -------------------------------------------------


def _coverage(**kwargs: Any) -> GeneratorCoverage:
    base: dict[str, Any] = {
        "generator": "mcq",
        "in_set": 10,
        "graded": 10,
        "expected": 10,
    }
    base.update(kwargs)
    return GeneratorCoverage(**base)


def test_an_interrupted_run_leaves_coverage_uneven() -> None:
    """What the cut exists for.

    Questions go in a batch: by the moment of interruption some generators have
    been got through entirely and others not started. A report over such a state
    will compute shares over a skewed sample and will show nothing of it — the
    share will look like an ordinary share.
    """
    state = SpaceStatus(
        "docs",
        30,
        "",
        [_pass(graded=20)],
        coverage=[
            _coverage(generator="mcq", graded=10, expected=10),
            _coverage(generator="multihop", graded=10, expected=10),
            _coverage(generator="tiered", graded=1, expected=10),
        ],
    )
    assert [entry.generator for entry in state.uneven] == ["tiered"]
    assert any("uneven" in step for step in state.advice())


def test_even_coverage_raises_nothing() -> None:
    """While the run is in progress everything lags at once — normal, not a skew."""
    state = SpaceStatus(
        "docs",
        30,
        "",
        [_pass(graded=9)],
        coverage=[
            _coverage(generator="mcq", graded=3, expected=10),
            _coverage(generator="multihop", graded=3, expected=10),
            _coverage(generator="tiered", graded=3, expected=10),
        ],
    )
    assert state.uneven == []
    assert not any("uneven" in step for step in state.advice())


def test_coverage_counts_a_verdict_per_pass() -> None:
    """A verdict is needed from every run, not one for all of them.

    Otherwise coverage would look complete as soon as one model out of nine got
    through its item type.
    """
    entry = _coverage(in_set=10, graded=10, expected=30)
    assert entry.share == pytest.approx(1 / 3)


def test_a_single_generator_is_never_uneven() -> None:
    """There is nothing to compare with: a skew is a lag BEHIND someone."""
    state = SpaceStatus(
        "docs", 10, "", [_pass()], coverage=[_coverage(graded=1, expected=10)]
    )
    assert state.uneven == []


# --- how public the corpus is ----------------------------------------------


def _exposure_rows(monkeypatch: Any, slices: list[GeneratorSlice]) -> None:
    monkeypatch.setattr(slices_mod, "by_generator", lambda *a, **k: slices)


def test_guessing_never_counts_as_a_public_corpus(monkeypatch: Any) -> None:
    """The main thing the cut exists for.

    A correct answer in arm A is read as the model being acquainted with the
    corpus. On a four-option item a quarter of such answers comes from blind
    guessing — and counting that as publicity means recording the arithmetic of
    the number of options there rather than knowledge.
    """
    _exposure_rows(
        monkeypatch,
        [
            GeneratorSlice(
                generator="mcq",
                graded=40,
                correct=10,
                abstain=0,
                hallucinate=30,
                failed=0,
            ),
            GeneratorSlice(
                generator="qa",
                graded=40,
                correct=0,
                abstain=40,
                hallucinate=0,
                failed=0,
            ),
        ],
    )

    got = corpus_exposure("docs")

    # With a free answer the model guessed nothing — the corpus is unfamiliar to it.
    assert got.free_form == 0.0
    # The choice gave exactly the guessing floor, that is, zero knowledge.
    assert got.choice == pytest.approx(0.25)
    assert got.above_guessing == pytest.approx(0.0)


def test_a_free_form_hit_is_real_exposure(monkeypatch: Any) -> None:
    """A free answer has no floor: the span either matched or it did not."""
    _exposure_rows(
        monkeypatch,
        [
            GeneratorSlice(
                generator="numeric_masking",
                graded=10,
                correct=7,
                abstain=1,
                hallucinate=2,
                failed=0,
            )
        ],
    )

    got = corpus_exposure("docs")

    assert got.free_form == pytest.approx(0.7)
    assert got.free_form_graded == 10
    assert got.choice is None


def test_choice_above_the_floor_is_reported_as_such(monkeypatch: Any) -> None:
    """Beating the guessing floor is already a signal, but of a different size."""
    _exposure_rows(
        monkeypatch,
        [
            GeneratorSlice(
                generator="two_truths_one_lie",
                graded=30,
                correct=24,
                abstain=0,
                hallucinate=6,
                failed=0,
            )
        ],
    )

    got = corpus_exposure("docs")

    assert got.choice == pytest.approx(0.8)
    assert got.choice_floor == pytest.approx(1 / 3)
    assert got.above_guessing == pytest.approx(0.8 - 1 / 3)


def test_a_set_of_only_choice_tasks_cannot_measure_exposure(monkeypatch: Any) -> None:
    """There is nothing to measure with — and that is more honest than a number
    with a floor inside it."""
    _exposure_rows(
        monkeypatch,
        [
            GeneratorSlice(
                generator="mcq",
                graded=20,
                correct=20,
                abstain=0,
                hallucinate=0,
                failed=0,
            )
        ],
    )

    got = corpus_exposure("docs")

    assert got.free_form is None
    assert got.choice == 1.0
