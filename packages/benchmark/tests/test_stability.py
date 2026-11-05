"""Comparing cohorts: same material, different questions — same numbers?

The benchmark measures a model with questions it composed itself. What is tested
is the thing the comparison exists for: a divergence of numbers over the same
material is said out loud, and a repeat by one generator is not passed off as an
independent check.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from syft_benchmark.config import ContextMode, EvalBlock, ExpectedBehavior
from syft_benchmark.generation.cohort import Cohort
from syft_benchmark.report import stability
from syft_benchmark.report.metrics import Metrics
from syft_benchmark.report.stability import (
    DIVERGENCE_LIMIT,
    CohortRun,
    Comparison,
    compare,
    lines,
)

_NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def _cohort(
    label: str, built: tuple[str, ...] = ("gemma3",), rejected: int = 0
) -> Cohort:
    return Cohort(
        label=label,
        space="docs",
        pairs=100,
        active=100,
        rejected=rejected,
        built_by=built,
        first_seen=_NOW,
        last_seen=_NOW,
    )


def _metrics(correct: int, wrong: int, abstain: int = 0) -> Metrics:
    return Metrics(
        space="docs",
        context_mode=ContextMode.CLOSED_BOOK,
        block=EvalBlock.DIRECT,
        model="vendor/m",
        endpoint="",
        graded=correct + wrong + abstain,
        correct=correct,
        abstain=abstain,
        hallucinate=wrong,
        failed=0,
        retrieval_hits=0,
        retrieval_checked=0,
        checked_at=_NOW,
        judge="judge/a",
        expected=ExpectedBehavior.ANSWER,
    )


def _comparison(*runs: CohortRun) -> Comparison:
    return Comparison(
        space="docs",
        context_mode=ContextMode.CLOSED_BOOK,
        block=EvalBlock.DIRECT,
        model="vendor/m",
        judge="judge/a",
        runs=list(runs),
    )


def test_matching_cohorts_mean_the_questions_are_not_the_story() -> None:
    """The numbers matched — the difference between models speaks about models."""
    got = _comparison(
        CohortRun(_cohort("20260914-0300"), _metrics(70, 30)),
        CohortRun(_cohort("20260907-0300"), _metrics(72, 28)),
    )
    assert got.spread < DIVERGENCE_LIMIT
    assert not got.suspect


def test_a_wide_spread_points_at_the_questions() -> None:
    """The material is one and the same, and the numbers diverged.

    So the divergence speaks not about the model under test but about the
    questions and the gold answers — and that has to be said outright.
    """
    got = _comparison(
        CohortRun(_cohort("20260914-0300"), _metrics(70, 30)),
        CohortRun(_cohort("20260907-0300"), _metrics(45, 55)),
    )
    assert got.suspect
    text = "\n".join(lines(got))
    assert "questions and the gold answers" in text
    assert "25%" in text


def test_hallucinations_alone_are_enough_to_look_suspect() -> None:
    """A set whose accuracy matched but whose share of inventions diverged
    twofold is a diverged set too."""
    got = _comparison(
        CohortRun(_cohort("a"), _metrics(50, 10, abstain=40)),
        CohortRun(_cohort("b"), _metrics(50, 45, abstain=5)),
    )
    assert got.spread == 0.0
    assert got.hallucination_spread > DIVERGENCE_LIMIT
    assert got.suspect


def test_one_generator_is_a_repeat_not_an_independent_check() -> None:
    """Two passes of one model over one prompt reproduce its errors.

    A match then means the reproducibility of the decisions, not their
    correctness, and it must not be passed off as a check on question quality.
    """
    same = _comparison(
        CohortRun(_cohort("a", ("gemma3",)), _metrics(70, 30)),
        CohortRun(_cohort("b", ("gemma3",)), _metrics(71, 29)),
    )
    assert not same.built_by_different_generators
    assert "DIFFERENT" in "\n".join(lines(same))

    different = _comparison(
        CohortRun(_cohort("a", ("gemma3",)), _metrics(70, 30)),
        CohortRun(_cohort("b", ("qwen3",)), _metrics(71, 29)),
    )
    assert different.built_by_different_generators
    assert "DIFFERENT" not in "\n".join(lines(different))


def test_the_rejection_share_is_shown_next_to_the_numbers() -> None:
    """The first thing to look at when cohorts diverge.

    A generator that had a third of its gold answers rejected probably did not
    build the other two thirds any better.
    """
    got = _comparison(
        CohortRun(_cohort("a", rejected=40), _metrics(70, 30)),
        CohortRun(_cohort("b", rejected=2), _metrics(45, 55)),
    )
    text = "\n".join(lines(got))
    assert "40%" in text
    assert "Screened out" in text


def test_one_cohort_is_nothing_to_compare(monkeypatch: Any) -> None:
    """It is too early to speak of the set's stability from a single build."""
    monkeypatch.setattr(
        stability, "cohort_listing", lambda space: [_cohort("20260914-0300")]
    )
    monkeypatch.setattr(stability, "summarize", lambda *a, **k: _metrics(70, 30))
    assert compare("docs", ContextMode.CLOSED_BOOK) is None


def test_a_cohort_without_verdicts_does_not_count(monkeypatch: Any) -> None:
    """A cohort that was built but never run is not fit for comparison."""
    monkeypatch.setattr(
        stability,
        "cohort_listing",
        lambda space: [_cohort("new"), _cohort("old")],
    )
    monkeypatch.setattr(
        stability,
        "summarize",
        lambda space, mode, block, model, judge, expected, cohort=None: (
            _metrics(70, 30) if cohort == "old" else None
        ),
    )
    assert compare("docs", ContextMode.CLOSED_BOOK) is None


def test_two_measured_cohorts_are_compared(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        stability,
        "cohort_listing",
        lambda space: [_cohort("new"), _cohort("old")],
    )
    monkeypatch.setattr(
        stability,
        "summarize",
        lambda space, mode, block, model, judge, expected, cohort=None: (
            _metrics(70, 30) if cohort == "new" else _metrics(50, 50)
        ),
    )
    got = compare("docs", ContextMode.CLOSED_BOOK)
    assert got is not None
    assert [run.cohort.label for run in got.runs] == ["new", "old"]
    assert got.spread == pytest.approx(0.2)


def test_nothing_to_compare_renders_nothing() -> None:
    assert lines(None) == []
