"""The frozen slice, selection by generator, and the text metrics.

Three different things about one: what exactly gets into the measurement, and
what an answer is measured by besides the judge verdict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from syft_benchmark.config import Settings, TextMetric
from syft_benchmark.runs import questionset
from syft_benchmark.runs.questionset import SliceMismatch, fingerprint
from syft_benchmark.runs.textmetrics import (
    applies_to,
    average,
    bleu,
    rouge_l,
    rouge_n,
    score_text,
)


class _Pair:
    """An item in the volume the slice needs."""

    def __init__(self, number: int, question: str = "", answer: str = "") -> None:
        self.id = f"p{number}"
        self.question = question or f"Question {number}?"
        self.answer = answer or f"Answer {number}"
        self.generator = "cloze"
        self.expected_behavior = "answer"


def _settings(**kwargs: object) -> Settings:
    return Settings(**kwargs)  # type: ignore[arg-type]


def _slice(pairs: list[_Pair], space: str = "docs") -> dict[str, Any]:
    return questionset.build(space, pairs)  # type: ignore[arg-type]


# --- the slice --------------------------------------------------------------


def test_the_slice_pins_the_exact_questions_in_order() -> None:
    """A slice is the WHOLE selection, and its order belongs to it too."""
    pairs = [_Pair(i) for i in range(5)]
    selected = questionset.apply(_slice(pairs), list(reversed(pairs)))  # type: ignore[arg-type]
    assert [p.id for p in selected] == [p.id for p in pairs]


def test_a_changed_question_is_a_refusal_not_a_silent_swap() -> None:
    """The main thing the fingerprint is in the slice for.

    A pair survives regeneration, its text does not. The gold answer was
    refined, the question reworded: the identifier is the same, the item is
    different, and the answers collected relate to the previous one.
    """
    pairs = [_Pair(0), _Pair(1)]
    frozen = _slice(pairs)
    pairs[1].answer = "An entirely different gold answer"

    with pytest.raises(SliceMismatch, match="changed"):
        questionset.apply(frozen, pairs)  # type: ignore[arg-type]


def test_a_vanished_question_is_a_refusal_too() -> None:
    """Screening took a pair out of the active ones — the set is not the same."""
    pairs = [_Pair(0), _Pair(1)]
    frozen = _slice(pairs)

    with pytest.raises(SliceMismatch, match="no longer among"):
        questionset.apply(frozen, pairs[:1])  # type: ignore[arg-type]


def test_the_strict_check_can_be_lowered_to_a_warning() -> None:
    """Sometimes diverged items just have to be thrown out so work can go on."""
    pairs = [_Pair(0), _Pair(1)]
    frozen = _slice(pairs)
    selected = questionset.apply(frozen, pairs[:1], strict=False)  # type: ignore[arg-type]
    assert [p.id for p in selected] == ["p0"]


def test_a_slice_from_another_space_is_never_applied() -> None:
    """This is not a soft divergence but a wholly different set of questions."""
    frozen = _slice([_Pair(0)], space="other")
    with pytest.raises(SliceMismatch, match="different sets"):
        questionset.apply(frozen, [_Pair(0)], space="docs")  # type: ignore[arg-type]


def test_the_answer_is_part_of_the_fingerprint() -> None:
    """A refined gold answer changes the item no less than a new question does.

    The judge compares the answer against precisely the gold answer, and a
    fingerprint over the question alone would let through a substitution of the
    thing being compared against.
    """
    assert fingerprint("Question?", "A") != fingerprint("Question?", "B")


def test_a_written_slice_reads_back(tmp_path: Path) -> None:
    """A slice goes into the repository and is read by eye."""
    path = tmp_path / "slice.json"
    questionset.write(path, _slice([_Pair(0), _Pair(1)]))
    data = questionset.load(path)

    assert data["space"] == "docs"
    assert data["count"] == 2
    assert json.loads(path.read_text(encoding="utf-8"))["questions"][0]["id"] == "p0"


def test_a_missing_slice_says_so(tmp_path: Path) -> None:
    with pytest.raises(SliceMismatch, match="no frozen slice"):
        questionset.load(tmp_path / "nope.json")


def test_a_future_slice_version_is_refused(tmp_path: Path) -> None:
    """The format survives code edits, and an old file says so itself."""
    path = tmp_path / "slice.json"
    data = _slice([_Pair(0)])
    data["slice_version"] = 99
    questionset.write(path, data)

    with pytest.raises(SliceMismatch, match="slice version"):
        questionset.load(path)


# --- the text metrics -------------------------------------------------------


def test_an_identical_answer_scores_one() -> None:
    """The upper bound is checkable: a verbatim match is a full match."""
    text = "the benchmark publishes its port as five four four two"
    assert bleu(text, text) == pytest.approx(1.0, abs=1e-3)
    assert rouge_n(text, text, 1) == pytest.approx(1.0)
    assert rouge_l(text, text) == pytest.approx(1.0)


def test_nothing_in_common_scores_zero() -> None:
    assert rouge_n("something else entirely", "the port is 5442", 1) == 0.0
    assert rouge_l("something else entirely", "the port is 5442") == 0.0


def test_rouge_l_survives_reordering_and_rouge_2_does_not() -> None:
    """Exactly what both of them are computed for.

    ROUGE-L looks at the longest common subsequence and does not zero out a
    reordered but substantively correct answer; ROUGE-2 demands that the words
    run consecutively.
    """
    reference = "the port is published as 5442"
    reordered = "5442 is the published port"
    assert rouge_l(reordered, reference) > rouge_n(reordered, reference, 2)


def test_a_short_answer_is_penalised() -> None:
    """The brevity penalty: a stub of the gold answer is not a retelling of it."""
    reference = "the port is published as 5442 in the setup document"
    assert bleu("the port", reference) < bleu(reference, reference)


def test_smoothing_keeps_short_answers_from_collapsing_to_zero() -> None:
    """Without smoothing the metric would silently become a constant zero.

    The answers here are short, and 4-grams almost never match: a single missed
    order would zero out the whole score.
    """
    assert bleu("the port is 5443", "the port is 5442") > 0.0


def test_text_metrics_are_off_unless_asked() -> None:
    """The headline assessment is the judge verdict; this is a second view."""
    assert score_text("answer", "gold answer", _settings()) == {}


def test_each_metric_is_switched_on_by_name() -> None:
    conf = _settings(text_metrics=[TextMetric.ROUGE])
    scores = score_text("the port is 5442", "the port is 5442", conf)
    assert set(scores) == {"rouge1_f", "rouge2_f", "rougeL_f"}
    assert "bleu" not in scores

    conf = _settings(text_metrics=[TextMetric.BLEU])
    assert set(score_text("a b c d", "a b c d", conf)) == {"bleu"}


def test_only_prose_generators_are_measured() -> None:
    """Masking has a one-word gold answer, and word overlap there degenerates
    into "matched or not" — which the judge has already measured."""
    assert applies_to("multihop_synthesis")
    assert applies_to("tiered_explanation")
    assert not applies_to("numeric_masking")
    assert not applies_to("mcq")


def test_an_empty_side_is_not_scored() -> None:
    conf = _settings(text_metrics=[TextMetric.BLEU, TextMetric.ROUGE])
    assert score_text("", "gold answer", conf) == {}
    assert score_text("answer", "   ", conf) == {}


def test_each_metric_averages_over_its_own_records() -> None:
    """BERTScore may have been switched on later than the rest.

    Dividing its sum by all the rows would understate it by exactly the factor
    by which it was not computed.
    """
    averaged = average(
        [
            {"bleu": 0.2},
            {"bleu": 0.4, "bertscore_f1": 0.9},
        ]
    )
    assert averaged["bleu"] == pytest.approx(0.3)
    assert averaged["bertscore_f1"] == pytest.approx(0.9)
