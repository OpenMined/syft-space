"""``technical``: the verdict for a row that measured nothing.

The endpoint unreachable, the provider refusing, the key out, the judge
silent — the row says something about the rig and nothing about the model.

Such a row says so in its verdict; a failed judge call and a failed answer
are told apart, neither enters a share, and the verdict cannot be set by hand.
"""

from __future__ import annotations

import pytest

from syft_benchmark.config import ContextMode, EvalBlock, Settings, Verdict
from syft_benchmark.control.schemas import VerdictOverride
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.llm import judge_provider
from syft_benchmark.report.slices import by_generator
from syft_benchmark.runs.judge import (
    ERROR_PREFIX,
    Grade,
    grade,
    grade_key_facts,
    is_error,
    is_technical,
)
from syft_benchmark.runs.result_views import list_results

SPACE = "pytest-technical"


def test_a_call_that_did_not_happen_is_not_a_hallucination() -> None:
    """Every cheap path that reaches a verdict without calling a judge."""
    broken = f"{ERROR_PREFIX} the endpoint returned an empty answer"
    conf = Settings()

    assert (
        grade("q", "a", broken, settings=conf, judge=judge_provider(conf)).verdict
        is Verdict.TECHNICAL
    )
    assert (
        grade_key_facts(
            broken, ["a fact"], settings=conf, judge=judge_provider(conf)
        ).verdict
        is Verdict.TECHNICAL
    )
    # No facts to check against is the same kind of fact about the rig: the
    # item was built wrong, and grading it would invent a measurement.
    assert (
        grade_key_facts(
            "an answer", [], settings=conf, judge=judge_provider(conf)
        ).verdict
        is Verdict.TECHNICAL
    )


def test_failed_is_derived_from_the_verdict() -> None:
    """One source of truth, and it is the one the database keeps."""
    assert Grade(Verdict.TECHNICAL, "").failed is True
    assert Grade(Verdict.ABSTAIN, "").failed is False


def test_a_failed_judge_call_and_a_failed_answer_are_told_apart() -> None:
    """A technical verdict is the judge's failure, an `ERROR:` answer the
    answerer's; neither enters a share."""
    assert is_technical(Verdict.TECHNICAL.value) is True
    assert is_technical(Verdict.HALLUCINATE.value) is False
    assert is_error(f"{ERROR_PREFIX} boom") is True
    assert is_error("Paris, probably") is False


@pytest.mark.needs_db
def test_a_failed_judge_call_does_not_enter_a_share(clean: None) -> None:
    """Three rows, one of them a failed judge call, one share of 50%."""
    with session_scope() as session:
        for number in range(1, 4):
            session.add(
                QaPair(
                    id=f"p-tech-{number}",
                    space=SPACE,
                    generator="qa",
                    question="q",
                    answer="a",
                    status="active",
                    model="m",
                    question_hash=f"h-tech-{number}",
                )
            )
        session.add(
            Run(id="run-tech", space=SPACE, context_mode="closed_book", model="m")
        )
        rows = [
            ("correct", "5442"),
            ("hallucinate", "1234"),
            ("technical", f"{ERROR_PREFIX} unreachable"),
        ]
        for number, (verdict, answer) in enumerate(rows, start=1):
            session.add(
                Result(
                    id=f"r-tech-{number}",
                    run_id="run-tech",
                    qa_id=f"p-tech-{number}",
                    space=SPACE,
                    verdict=verdict,
                    answer=answer,
                )
            )

    (slice_,) = by_generator(
        SPACE, ContextMode.CLOSED_BOOK, EvalBlock.DIRECT, model="m"
    )
    assert slice_.failed == 1
    assert slice_.graded == 2
    assert slice_.correct == 1
    assert slice_.hallucinate == 1
    assert slice_.accuracy == 0.5


@pytest.mark.needs_db
def test_a_technical_row_is_visible_as_itself_in_the_console(clean: None) -> None:
    """The row says what happened, rather than naming an invention."""
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-tech-one",
                space=SPACE,
                generator="qa",
                question="q",
                answer="a",
                status="active",
                model="m",
                question_hash="h-tech-one",
            )
        )
        session.add(
            Run(id="run-tech-one", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="r-tech-one",
                run_id="run-tech-one",
                qa_id="p-tech-one",
                space=SPACE,
                verdict=Verdict.TECHNICAL.value,
                answer=f"{ERROR_PREFIX} unreachable",
            )
        )

    views, total = list_results(SPACE)
    assert total == 1
    assert views[0].verdict == "technical"


def test_a_state_of_the_machinery_cannot_be_issued_by_hand() -> None:
    """An override is the owner disagreeing, not the owner editing the rig.

    `technical` would also take the row out of the shares, which is a way to
    make a verdict disappear rather than argue with it.
    """
    assert VerdictOverride(verdict=Verdict.CORRECT).verdict is Verdict.CORRECT
    for state in (Verdict.TECHNICAL, Verdict.PENDING):
        with pytest.raises(ValueError, match="not a verdict"):
            VerdictOverride(verdict=state)
