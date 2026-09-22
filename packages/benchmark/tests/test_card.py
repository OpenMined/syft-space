"""The endpoint card: what exactly the node shows the world.

What is tested is why the first version of publishing was unfit: a retrieval node
was left without numbers, the arm was not named, and nine models under test risked
merging into one quantity that means nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    ExpectedBehavior,
    get_settings,
)
from syft_benchmark.report import card as card_mod
from syft_benchmark.report import metrics as metrics_mod
from syft_benchmark.report.card import (
    ANSWERING,
    MIN_SAMPLES,
    RETRIEVAL,
    DatasetInfo,
    Instrument,
    Trust,
    build,
)
from syft_benchmark.report.metrics import Metrics
from syft_benchmark.report.slices import GeneratorSlice, JudgePair

_NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def _metrics(
    mode: ContextMode,
    *,
    model: str = "",
    graded: int = 40,
    correct: int = 28,
    abstain: int = 5,
    hallucinate: int = 7,
    expected: ExpectedBehavior = ExpectedBehavior.ANSWER,
    hits: int = 33,
    checked: int = 40,
) -> Metrics:
    return Metrics(
        space="docs",
        context_mode=mode,
        block=EvalBlock.DIRECT,
        model=model,
        endpoint="kb",
        graded=graded,
        correct=correct,
        abstain=abstain,
        hallucinate=hallucinate,
        failed=0,
        retrieval_hits=hits,
        retrieval_checked=checked,
        checked_at=_NOW,
        judge="gemma3-4b-gpu",
        expected=expected,
    )


def _quiet_surroundings(monkeypatch: Any) -> None:
    """Everything the card asks the database besides the metrics themselves."""
    monkeypatch.setattr(
        card_mod,
        "by_generator",
        lambda *a, **k: [
            GeneratorSlice(
                generator="mcq",
                graded=20,
                correct=18,
                abstain=1,
                hallucinate=1,
                failed=0,
            ),
            GeneratorSlice(
                generator="qa",
                graded=20,
                correct=10,
                abstain=4,
                hallucinate=6,
                failed=0,
            ),
        ],
    )
    monkeypatch.setattr(card_mod, "judge_agreement", lambda *a, **k: [])
    monkeypatch.setattr(card_mod, "judges_seen", lambda *a, **k: ["gemma3-4b-gpu"])
    monkeypatch.setattr(
        card_mod,
        "_dataset",
        lambda *a, **k: DatasetInfo(
            mode="incremental", window_days=0, cohort="", questions=50
        ),
    )
    monkeypatch.setattr(
        card_mod,
        "_instrument",
        lambda *a, **k: Instrument(
            version=2, profile="default", judge="gemma3-4b-gpu", judges=1, subjects=2
        ),
    )


# --- the kind of product ---------------------------------------------------


def test_a_retrieval_endpoint_is_not_left_without_a_badge(monkeypatch: Any) -> None:
    """The main thing the kind appeared for at all.

    An endpoint in raw mode has no arm B — it refuses to run, because such a node
    has nothing to formulate an answer with. While the published arm was set by a
    setting, such a node went out to the storefront empty despite excellent
    retrieval, and the user screened it out at the badge.
    """
    monkeypatch.setattr(card_mod, "endpoint_kind", lambda *a, **k: RETRIEVAL)
    monkeypatch.setattr(
        card_mod, "models_seen", lambda *a, **k: ["gemma3-4b-gpu", "qwen3-8b"]
    )
    _quiet_surroundings(monkeypatch)

    def fake_summarize(
        space: str,
        mode: ContextMode,
        *args: Any,
        expected: ExpectedBehavior = ExpectedBehavior.ANSWER,
        **kwargs: Any,
    ) -> Metrics | None:
        if mode is ContextMode.OPEN_BOOK:
            return None  # a raw node has no arm B
        if expected is ExpectedBehavior.ABSTAIN:
            return _metrics(mode, graded=10, correct=0, abstain=9, hallucinate=1)
        return _metrics(mode)

    monkeypatch.setattr(card_mod, "summarize", fake_summarize)

    got = build("docs", "kb")

    assert got is not None
    assert got.kind == RETRIEVAL
    # It is measured in arm C: there its chunks reach a foreign model.
    assert got.arm == ContextMode.MODEL_WITH_CONTEXT.value
    # The headline number is the retrieval hit, not the accuracy of the answer.
    assert got.score == pytest.approx(33 / 40)
    assert got.score_label == "finds"


def test_an_answering_endpoint_is_judged_by_its_own_answer(monkeypatch: Any) -> None:
    """A node that answers itself is judged by its answer, and in arm B."""
    monkeypatch.setattr(card_mod, "endpoint_kind", lambda *a, **k: ANSWERING)
    monkeypatch.setattr(card_mod, "models_seen", lambda *a, **k: [])
    _quiet_surroundings(monkeypatch)
    monkeypatch.setattr(
        card_mod,
        "summarize",
        lambda space, mode, *a, expected=ExpectedBehavior.ANSWER, **k: (
            _metrics(mode, graded=10, correct=0, abstain=9, hallucinate=1)
            if expected is ExpectedBehavior.ABSTAIN
            else _metrics(mode)
        ),
    )

    got = build("docs", "kb")

    assert got is not None
    assert got.kind == ANSWERING
    assert got.arm == ContextMode.OPEN_BOOK.value
    assert got.score == pytest.approx(28 / 40)
    assert got.score_label == "correct"
    # The control half — the very thing it was created for — is on the card.
    assert got.fabrication == pytest.approx(0.1)


# --- nine models -----------------------------------------------------------


def test_nine_models_go_out_by_name_and_never_as_an_average(
    monkeypatch: Any,
) -> None:
    """An average over nine would measure our config, not the node.

    Add a tenth model and the average moves, though nothing happened to the
    endpoint. So arm C goes out as a list, and the reader is shown the spread.
    """
    monkeypatch.setattr(card_mod, "endpoint_kind", lambda *a, **k: ANSWERING)
    monkeypatch.setattr(card_mod, "models_seen", lambda *a, **k: ["weak", "strong"])
    _quiet_surroundings(monkeypatch)

    scores = {"weak": 20, "strong": 36}

    def fake_summarize(
        space: str,
        mode: ContextMode,
        *args: Any,
        model: str | None = None,
        expected: ExpectedBehavior = ExpectedBehavior.ANSWER,
        **kwargs: Any,
    ) -> Metrics | None:
        if expected is ExpectedBehavior.ABSTAIN:
            return _metrics(mode, graded=10, correct=0, abstain=9, hallucinate=1)
        if model in scores:
            return _metrics(mode, model=model, correct=scores[model])
        return _metrics(mode)

    monkeypatch.setattr(card_mod, "summarize", fake_summarize)

    got = build("docs", "kb")

    assert got is not None
    assert [row.model for row in got.models] == ["strong", "weak"]
    assert got.spread == (pytest.approx(0.5), pytest.approx(0.9))


def test_a_model_arm_refuses_to_be_summarised_without_a_model(
    monkeypatch: Any,
) -> None:
    """The cut by model is mandatory where a model under test answers.

    Without it the latest verdict per question goes to whichever model finished
    last, and a "shared" share would mean not an average over nine but the opinion
    of a random one. This must not be passed over in silence: the quantity would
    look like an ordinary one.
    """
    monkeypatch.setattr(
        metrics_mod, "models_seen", lambda *a, **k: ["gemma3-4b-gpu", "qwen3-8b"]
    )

    with pytest.raises(ValueError, match="name one"):
        metrics_mod.summarize("docs", ContextMode.MODEL_WITH_CONTEXT)


def test_one_model_needs_no_naming(monkeypatch: Any) -> None:
    """While there is one model there is nothing to mix — a ban would be nitpicking."""
    monkeypatch.setattr(metrics_mod, "models_seen", lambda *a, **k: ["gemma3-4b-gpu"])
    monkeypatch.setattr(metrics_mod, "_latest_results", lambda *a, **k: [])

    assert metrics_mod.summarize("docs", ContextMode.MODEL_WITH_CONTEXT) is None


# --- trust -----------------------------------------------------------------


def test_a_share_over_too_few_questions_does_not_reach_the_badge() -> None:
    """A share nobody vouches for is worse than no share."""
    trust = Trust(
        samples=MIN_SAMPLES - 1,
        judges=1,
        agreement=None,
        consistency=None,
        even_coverage=True,
        failed=0,
        pending=0,
    )

    assert not trust.reliable
    assert trust.flags == ["few_samples"]


def test_disagreeing_judges_grey_the_badge_out() -> None:
    """Below the agreement floor the difference between nodes drowns in the spread."""
    trust = Trust(
        samples=200,
        judges=3,
        agreement=0.4,
        consistency=None,
        even_coverage=True,
        failed=0,
        pending=0,
    )

    assert not trust.reliable
    assert "judges_disagree" in trust.flags


def test_an_interrupted_run_is_visible_as_a_skewed_sample() -> None:
    """An interrupted run leaves coverage uneven.

    A share over such a state looks like an ordinary share — and should look
    otherwise.
    """
    trust = Trust(
        samples=200,
        judges=1,
        agreement=None,
        consistency=None,
        even_coverage=False,
        failed=0,
        pending=12,
    )

    assert not trust.reliable
    assert trust.flags == ["uneven_coverage", "pending_verdicts"]


def test_the_flags_carry_codes_and_not_our_prose() -> None:
    """The wording is written by the storefront: it has its own reader and language."""
    trust = Trust(
        samples=1,
        judges=2,
        agreement=0.1,
        consistency=None,
        even_coverage=False,
        failed=3,
        pending=4,
    )

    for code in trust.flags:
        assert " " not in code
        assert code.isascii()
    # The prose stays — but for our own console.
    assert any("too few questions" in note for note in trust.doubts)


# --- agreement with the settings -------------------------------------------


def test_the_judge_agreement_floor_is_the_one_the_report_uses() -> None:
    """The agreement floor is one for the report and the badge: otherwise they argue."""
    pairs = [JudgePair(left="a", right="b", shared=10, agreed=9)]
    from syft_benchmark.report.slices import average_agreement

    trust = Trust(
        samples=100,
        judges=2,
        agreement=average_agreement(pairs),
        consistency=None,
        even_coverage=True,
        failed=0,
        pending=0,
    )

    assert trust.reliable
    assert get_settings() is not None
