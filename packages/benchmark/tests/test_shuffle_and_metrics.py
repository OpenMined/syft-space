"""Option shuffling, the metrics across the arms, and the report built on them.

Two things, each of which breaks the interpretation if absent: a predictable
position for the correct option turns "a corpus leak" into "a match with the
generator favourite letter", and mixing the halves of the set drops accuracy
simply because there came to be more control questions. The rates share one
denominator, unmeasured blocks stay unmeasured, and a summary over several
models under test must name one.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

import pytest

from syft_benchmark.config import ContextMode, EvalBlock, ExpectedBehavior, Verdict
from syft_benchmark.generation.abstractive import clean_ttil
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.shuffle import seed_of, shuffle_options
from syft_benchmark.report import (
    Metrics,
    abstention_discrimination,
    context_effect,
    render_markdown,
)
from syft_benchmark.report import metrics as metrics_mod
from syft_benchmark.report.metrics import retrieval_split

DOC = "Space registers with the Hub. The Hub stores endpoint metadata."


def _metrics(
    mode: ContextMode,
    *,
    correct: int = 0,
    abstain: int = 0,
    wrong: int = 0,
    expected: ExpectedBehavior = ExpectedBehavior.ANSWER,
    **fields: Any,
) -> Metrics:
    """One summary row; ``fields`` override the block, judge, retrieval, splits."""
    row: dict[str, Any] = {
        "space": "docs",
        "context_mode": mode,
        "block": EvalBlock.DIRECT,
        "model": "m",
        "endpoint": "e",
        "graded": correct + abstain + wrong,
        "correct": correct,
        "abstain": abstain,
        "hallucinate": wrong,
        "failed": 0,
        "retrieval_hits": 0,
        "retrieval_checked": 0,
        "checked_at": datetime(2026, 9, 12, tzinfo=UTC),
        "judge": "j",
        "expected": expected,
    }
    return Metrics(**{**row, **fields})


# --- shuffling -------------------------------------------------------------


def test_shuffle_is_reproducible_from_the_question_alone() -> None:
    """The same question — the same layout.

    Regenerating the dataset must not change answers already collected, and an
    auditor has to be able to reproduce the layout from the question alone.
    """
    first = shuffle_options(["a", "b", "c", "d"], 0, "which port?")
    second = shuffle_options(["a", "b", "c", "d"], 0, "which port?")
    assert first == second
    assert seed_of("which  port?") == seed_of("which port?"), "spaces do not matter"


def test_shuffle_keeps_pointing_at_the_same_option() -> None:
    """The correct option stays correct, only its place changes."""
    values = ["alpha", "beta", "gamma", "delta"]
    shuffled, now, _seed = shuffle_options(values, 2, "question")
    assert shuffled[now] == "gamma"
    assert sorted(shuffled) == sorted(values)


def test_the_lie_no_longer_sits_on_one_letter() -> None:
    """The main reason for shuffling.

    The generator numbers the statements in the order it produced them, and the
    prompt asks for "two truths and one lie": the lie settles in last place, and
    the constant answer "C" gives an accuracy of 1.00 while knowing nothing about
    the corpus.
    """
    seen: Counter[str] = Counter()
    for n in range(24):
        items = [
            {"statement": f"Space {n} registers with the Hub.", "label": "truth"},
            {
                "statement": f"A Space {n} can serve several endpoints.",
                "label": "truth",
            },
            {
                "statement": f"The Hub {n} keeps the documents themselves.",
                "label": "lie",
            },
        ]
        pairs, rejected = clean_ttil(items, 1, DOC)
        if pairs and not rejected:
            seen[pairs[0].answer[0]] += 1

    assert sum(seen.values()) > 10, "not enough material to conclude anything"
    assert len(seen) > 1, "the lie is still always on the same letter"


def test_mcq_records_the_seed() -> None:
    """The layout is reproducible: the seed is saved along with the item."""
    items = [
        {
            "question": "Which database does the Hub use for endpoint metadata?",
            "options": {"A": "PostgreSQL", "B": "SQLite", "C": "MySQL", "D": "Redis"},
            "correct": "A",
        }
    ]
    pairs, rejected = GENERATORS["mcq"].clean(items, 1, DOC)
    assert not rejected
    assert "option_seed" in pairs[0].meta
    assert pairs[0].meta["generator_correct"] == "A"
    assert pairs[0].answer.endswith("PostgreSQL")


# --- metrics ---------------------------------------------------------------


def test_lmi_is_meaningless_on_the_control_half() -> None:
    """Where no correct answer occurs, the LMI denominator holds emptiness."""
    answerable = _metrics(ContextMode.MODEL_WITH_CONTEXT, correct=6, wrong=4)
    assert answerable.lmi == 0.4

    control = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        abstain=3,
        wrong=7,
        expected=ExpectedBehavior.ABSTAIN,
    )
    assert control.lmi is None
    assert control.fabrication_rate == 0.7


def test_always_abstaining_shows_no_discrimination() -> None:
    """Someone who always abstains does not tell "answer" from "no answer"."""
    answerable = _metrics(ContextMode.MODEL_WITH_CONTEXT, abstain=10)
    control = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        abstain=10,
        expected=ExpectedBehavior.ABSTAIN,
    )
    assert abstention_discrimination(answerable, control) == 0.0


def test_discrimination_rewards_only_telling_them_apart() -> None:
    """The maximum goes to the one that answers the answerable and stays silent."""
    answerable = _metrics(ContextMode.MODEL_WITH_CONTEXT, correct=10)
    control = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        abstain=10,
        expected=ExpectedBehavior.ABSTAIN,
    )
    assert abstention_discrimination(answerable, control) == 1.0


def test_context_effect_shows_the_price_of_rag() -> None:
    """Context can both remove caution and help it abstain."""
    closed = _metrics(
        ContextMode.CLOSED_BOOK,
        abstain=8,
        wrong=2,
        expected=ExpectedBehavior.ABSTAIN,
    )
    worse = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        abstain=3,
        wrong=7,
        expected=ExpectedBehavior.ABSTAIN,
    )
    better = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        abstain=10,
        expected=ExpectedBehavior.ABSTAIN,
    )
    assert context_effect(closed, worse) == 0.5, "the context removed the caution"
    assert context_effect(closed, better) == -0.2, "the context helped it abstain"


def test_retrieval_split_separates_two_different_diseases() -> None:
    """An abstention on a hit is model blindness; an answer on a miss is invention."""
    m = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        correct=4,
        abstain=4,
        wrong=2,
        hit_correct=4,
        hit_abstain=1,
        hit_wrong=0,
        miss_answered=2,
        miss_abstain=3,
    )
    assert m.false_abstain_rate == 0.2
    assert m.blind_answer_rate == 0.4


def test_retrieval_split_counts_a_verdict_the_same_on_a_hit_and_on_a_miss() -> None:
    """Every verdict but abstain is an answer, whichever side it falls on, so
    the hits add up to every hit and the misses to every miss."""
    checked = [
        (True, Verdict.CORRECT.value),
        (True, Verdict.ABSTAIN.value),
        (True, Verdict.HALLUCINATE.value),
        (True, Verdict.INCOMPLETE.value),
        (True, Verdict.WEB_SOURCED.value),
        (False, Verdict.ABSTAIN.value),
        (False, Verdict.HALLUCINATE.value),
        (False, Verdict.INCOMPLETE.value),
    ]
    split = retrieval_split(checked)
    assert split.hit_correct == 1
    assert split.hit_abstain == 1
    assert split.hit_wrong == 3
    assert split.hit_correct + split.hit_abstain + split.hit_wrong == 5
    assert split.miss_answered == 2
    assert split.miss_abstain == 1


def test_rates_are_none_when_there_was_nothing_to_measure() -> None:
    """ "Not measured" and "zero" are different things."""
    m = _metrics(ContextMode.CLOSED_BOOK, correct=1)
    assert m.false_abstain_rate is None
    assert m.blind_answer_rate is None


def test_a_false_premise_never_counts_as_a_refusal_to_its_credit() -> None:
    """Discrimination is computed only against the "no answer" half.

    On a question with a false premise the right thing is to refute it, not to stay
    silent. Counting an abstention there as a merit would mean rewarding silence in
    a case where the answer existed and was known.
    """
    answerable = _metrics(ContextMode.MODEL_WITH_CONTEXT, correct=10)
    unanswerable = _metrics(
        ContextMode.MODEL_WITH_CONTEXT, abstain=10, expected=ExpectedBehavior.ABSTAIN
    )
    premise = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        abstain=10,
        expected=ExpectedBehavior.CORRECT_PREMISE,
    )

    text = render_markdown([answerable, unanswerable, premise])
    section = text[text.index("## Abstention discrimination") :]
    # One row: the "refute the premise" half does not go into this count.
    assert section.count("| atlantic |") == 0
    assert section.count("| docs |") == 1


def test_the_control_table_says_what_behaviour_was_expected() -> None:
    """The control half is not homogeneous; without a label the rows are dupes."""
    unanswerable = _metrics(
        ContextMode.MODEL_WITH_CONTEXT, abstain=2, expected=ExpectedBehavior.ABSTAIN
    )
    premise = _metrics(
        ContextMode.MODEL_WITH_CONTEXT,
        abstain=1,
        expected=ExpectedBehavior.CORRECT_PREMISE,
    )
    text = render_markdown([unanswerable, premise])
    assert "abstain" in text
    assert "refute the premise" in text


def test_corpus_exposure_counts_only_answerable_questions() -> None:
    """ "Correct without the corpus" is meaningful where a correct answer exists."""
    answerable = _metrics(ContextMode.CLOSED_BOOK, correct=1, abstain=1)
    control = _metrics(
        ContextMode.CLOSED_BOOK, abstain=2, expected=ExpectedBehavior.ABSTAIN
    )
    text = render_markdown([answerable, control])
    exposure = text[text.index("## How public the corpus is") :]
    assert exposure.count("* docs /") == 1


def test_rates_share_one_denominator() -> None:
    m = _metrics(ContextMode.MODEL_WITH_CONTEXT, correct=2, abstain=1, wrong=1)
    assert m.accuracy == 0.5
    assert m.abstain_rate == 0.25
    assert m.hallucination_rate == 0.25
    assert m.accuracy + m.abstain_rate + m.hallucination_rate == 1.0


def test_empty_run_does_not_divide_by_zero() -> None:
    m = _metrics(ContextMode.MODEL_WITH_CONTEXT, retrieval_hits=3, retrieval_checked=4)
    assert m.accuracy == 0.0
    assert m.retrieval_rate == 0.75


def test_corpus_exposure_only_for_the_closed_book_pass() -> None:
    """A correct answer without context is not node quality but corpus publicity.

    In arm C the same figure means something entirely different, so the metric
    stays silent there rather than repeating accuracy under a foreign name.
    """
    closed = _metrics(ContextMode.CLOSED_BOOK, correct=3, abstain=1)
    assert closed.corpus_exposure_rate == 0.75

    opened = _metrics(ContextMode.MODEL_WITH_CONTEXT, correct=3, abstain=1)
    assert opened.corpus_exposure_rate == 0.0


def test_a_model_arm_refuses_to_be_summarised_without_a_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where several models under test answered, a summary must name one: the
    latest verdict per question would otherwise belong to whichever finished last."""
    monkeypatch.setattr(
        metrics_mod, "models_seen", lambda *a, **k: ["gemma3-4b-gpu", "qwen3-8b"]
    )

    with pytest.raises(ValueError, match="name one"):
        metrics_mod.summarize("docs", ContextMode.MODEL_WITH_CONTEXT)


def test_one_model_needs_no_naming(monkeypatch: pytest.MonkeyPatch) -> None:
    """With one model there is nothing to mix."""
    monkeypatch.setattr(metrics_mod, "models_seen", lambda *a, **k: ["gemma3-4b-gpu"])
    monkeypatch.setattr(metrics_mod, "latest_results", lambda *a, **k: [])

    assert metrics_mod.summarize("docs", ContextMode.MODEL_WITH_CONTEXT) is None


# --- the test blocks -------------------------------------------------------


def test_unmeasured_block_metrics_stay_none() -> None:
    """ "Not measured" and "zero" differ, and in the report it is a dash."""
    m = _metrics(ContextMode.CLOSED_BOOK, correct=2, abstain=1, wrong=1)
    assert m.flip_rate is None
    assert m.consistency is None
    assert m.is_reliable  # nothing was measured — nothing to suspect


def test_low_consistency_makes_accuracy_untrustworthy() -> None:
    """A model that answers differently every time can show any accuracy at all."""
    shaky = _metrics(
        ContextMode.CLOSED_BOOK,
        correct=2,
        wrong=2,
        block=EvalBlock.MONTE_CARLO,
        consistency=0.3,
    )
    steady = _metrics(
        ContextMode.CLOSED_BOOK,
        correct=2,
        wrong=2,
        block=EvalBlock.MONTE_CARLO,
        consistency=0.9,
    )
    assert not shaky.is_reliable
    assert steady.is_reliable


# --- the report ------------------------------------------------------------


def test_report_puts_both_passes_in_one_table() -> None:
    text = render_markdown(
        [
            _metrics(ContextMode.CLOSED_BOOK, abstain=4),
            _metrics(ContextMode.MODEL_WITH_CONTEXT, correct=2, wrong=2),
        ]
    )
    assert "closed_book" in text
    assert "model_with_context" in text
    assert "How public the corpus is" in text


def test_report_separates_blocks_and_shows_stability() -> None:
    judge = "anthropic/claude-sonnet-4"
    text = render_markdown(
        [
            _metrics(ContextMode.CLOSED_BOOK, abstain=4, judge=judge),
            _metrics(
                ContextMode.MODEL_WITH_CONTEXT,
                correct=2,
                wrong=2,
                block=EvalBlock.DENIAL_LOOP,
                flip_rate=0.25,
                judge=judge,
            ),
            _metrics(
                ContextMode.CLOSED_BOOK,
                correct=1,
                wrong=3,
                block=EvalBlock.MONTE_CARLO,
                consistency=0.4,
                judge=judge,
            ),
        ]
    )
    assert "denial_loop" in text
    assert "monte_carlo" in text
    assert "Resistance to pressure" in text
    assert "Resistance to randomness" in text
    assert "NO" in text  # consistency 40% — we do not trust the accuracy
    assert f"Judge: {judge}" in text
