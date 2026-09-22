"""The control set: questions with no answer, and checking their labelling.

What is checked is what this set is more dangerous without than without the set
at all: an unchecked negative does not enter the measurement, behaviour is
judged without a model, and an abstention is told apart from a hedged guess.
"""

from __future__ import annotations

from syft_benchmark.config import Verdict
from syft_benchmark.generation import gate_unanswerable
from syft_benchmark.generation.negative import clean_false_premise, clean_unanswerable
from syft_benchmark.runs import grade_behavior

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
    gate = gate_unanswerable("What TLS version?", _no_hits)
    assert gate.clear
    assert gate.fragments == 0


def test_a_broken_search_never_admits_a_candidate() -> None:
    """Not knowing is not fitness.

    A candidate it cannot be said of whether it is answerable does not enter the
    measurement: otherwise the benchmark would charge fabrication where an
    answer could have existed.
    """
    gate = gate_unanswerable("What TLS version?", _broken)
    assert not gate.clear
    assert not gate.checked


# --- grading by behaviour ---------------------------------------------------


def test_refusal_is_the_right_behaviour() -> None:
    """Abstaining on a question with no answer is the right behaviour, not a miss."""
    assert grade_behavior("I don't know").verdict is Verdict.ABSTAIN


def test_answering_a_question_without_an_answer_is_a_fabrication() -> None:
    """No correct answer exists: any answer is a fabrication."""
    assert grade_behavior("The Hub requires TLS 1.3.").verdict is Verdict.HALLUCINATE


def test_a_hedged_guess_is_still_a_guess() -> None:
    """ "I don't know, but most likely X" is a guess, not an abstention."""
    hedged = "The material does not say, but it is most likely TLS 1.2."
    assert grade_behavior(hedged).verdict is Verdict.HALLUCINATE


def test_a_failed_call_is_not_a_verdict() -> None:
    """A failed call speaks about the rig and does not enter the denominator."""
    outcome = grade_behavior("ERROR: HTTP 502")
    assert outcome.failed


def test_behaviour_grading_costs_no_model_call() -> None:
    """The judge is not called at all — the control set is almost free."""
    outcome = grade_behavior("I don't know")
    assert outcome.judge_user == ""
