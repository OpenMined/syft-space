"""Metrics, the report and the schedule — without touching the database or network."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from syft_benchmark.config import ContextMode, EvalBlock
from syft_benchmark.report import Metrics, render_markdown
from syft_benchmark.runs import detect_abstain, grade_mcq, is_error
from syft_benchmark.scheduler import next_fire, parse_interval


def _metrics(
    mode: ContextMode,
    correct: int,
    abstain: int,
    wrong: int,
    *,
    block: EvalBlock = EvalBlock.DIRECT,
    flip_rate: float | None = None,
    consistency: float | None = None,
) -> Metrics:
    return Metrics(
        space="docs",
        context_mode=mode,
        block=block,
        model="gemma3-4b-gpu",
        endpoint="syft-knowledge-base",
        graded=correct + abstain + wrong,
        correct=correct,
        abstain=abstain,
        hallucinate=wrong,
        failed=0,
        retrieval_hits=3,
        retrieval_checked=4,
        checked_at=datetime(2026, 9, 9, tzinfo=UTC),
        judge="anthropic/claude-sonnet-4",
        flip_rate=flip_rate,
        consistency=consistency,
    )


def test_rates_share_one_denominator() -> None:
    m = _metrics(ContextMode.OPEN_BOOK, correct=2, abstain=1, wrong=1)
    assert m.accuracy == 0.5
    assert m.abstain_rate == 0.25
    assert m.hallucination_rate == 0.25
    assert m.accuracy + m.abstain_rate + m.hallucination_rate == 1.0


def test_empty_run_does_not_divide_by_zero() -> None:
    m = _metrics(ContextMode.OPEN_BOOK, 0, 0, 0)
    assert m.accuracy == 0.0
    assert m.retrieval_rate == 0.75


def test_corpus_exposure_only_for_the_closed_book_pass() -> None:
    """A correct answer without context is not node quality but corpus publicity.

    In run B the same figure means something entirely different, so the metric
    stays silent there rather than repeating accuracy under a foreign name.
    """
    closed = _metrics(ContextMode.CLOSED_BOOK, correct=3, abstain=1, wrong=0)
    assert closed.corpus_exposure_rate == 0.75

    opened = _metrics(ContextMode.OPEN_BOOK, correct=3, abstain=1, wrong=0)
    assert opened.corpus_exposure_rate == 0.0


def test_report_puts_both_passes_in_one_table() -> None:
    text = render_markdown(
        [
            _metrics(ContextMode.CLOSED_BOOK, 0, 4, 0),
            _metrics(ContextMode.OPEN_BOOK, 2, 0, 2),
        ]
    )
    assert "closed_book" in text
    assert "open_book" in text
    assert "How public the corpus is" in text


# --- the judge --------------------------------------------------------------


def test_silence_counts_as_abstain() -> None:
    assert detect_abstain("")
    assert detect_abstain("I don't know")
    assert detect_abstain("There is not enough information in the context")


def test_hedged_answer_is_an_answer_not_an_abstain() -> None:
    """A hedge plus an answer is a guess, and it has to be judged as an answer."""
    assert not detect_abstain("I'm not sure, but the answer is PostgreSQL")


def test_word_boundary_keeps_an_honest_refusal_honest() -> None:
    """A word boundary is needed: otherwise an honest abstention is lost.

    Without it the hedge "though" is found inside "Although", and a refusal that
    merely opens with a subordinate clause is scored as an answer.
    """
    assert detect_abstain("Although the context was provided, I don't know.")


def test_error_prefix_is_not_a_verdict() -> None:
    assert is_error("ERROR: HTTP 502")
    assert not is_error("The answer is PostgreSQL")


def test_mcq_letter_is_read_from_prose() -> None:
    assert grade_mcq("The correct answer is C) Three", "C) Three") is True
    assert grade_mcq("I would pick A) One", "C) Three") is False


def test_several_letters_go_to_the_judge() -> None:
    """Several letters named — they cannot be decided on."""
    assert grade_mcq("Either A) One or C) Three", "C) Three") is None


# --- the schedule -----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("24h", 86400.0), ("90m", 5400.0), ("30s", 30.0), ("2d", 172800.0)],
)
def test_interval_parsing(text: str, seconds: float) -> None:
    assert parse_interval(text) == seconds


def test_empty_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty interval"):
        parse_interval("")


def test_daily_step_lands_on_the_wall_clock_time() -> None:
    """The cycle should land at night, not at the moment of the first launch."""
    now = datetime(2026, 9, 9, 14, 30)
    assert next_fire(86400, "03:00", now=now) == datetime(2026, 9, 10, 3, 0)


def test_daily_step_today_when_the_hour_is_still_ahead() -> None:
    now = datetime(2026, 9, 9, 1, 15)
    assert next_fire(86400, "03:00", now=now) == datetime(2026, 9, 9, 3, 0)


def test_sub_daily_interval_ignores_the_wall_clock() -> None:
    now = datetime(2026, 9, 9, 14, 30)
    assert next_fire(3600, "03:00", now=now) == datetime(2026, 9, 9, 15, 30)


# --- the test blocks --------------------------------------------------------


def test_unmeasured_block_metrics_stay_none() -> None:
    """ "Not measured" and "zero" differ, and in the report it is a dash."""
    m = _metrics(ContextMode.CLOSED_BOOK, 2, 1, 1)
    assert m.flip_rate is None
    assert m.consistency is None
    assert m.is_reliable  # nothing was measured — nothing to suspect


def test_low_consistency_makes_accuracy_untrustworthy() -> None:
    """A model that answers differently every time can show any accuracy at all."""
    shaky = _metrics(
        ContextMode.CLOSED_BOOK, 2, 0, 2, block=EvalBlock.MONTE_CARLO, consistency=0.3
    )
    steady = _metrics(
        ContextMode.CLOSED_BOOK, 2, 0, 2, block=EvalBlock.MONTE_CARLO, consistency=0.9
    )
    assert not shaky.is_reliable
    assert steady.is_reliable


def test_report_separates_blocks_and_shows_stability() -> None:
    text = render_markdown(
        [
            _metrics(ContextMode.CLOSED_BOOK, 0, 4, 0),
            _metrics(
                ContextMode.OPEN_BOOK,
                2,
                0,
                2,
                block=EvalBlock.DENIAL_LOOP,
                flip_rate=0.25,
            ),
            _metrics(
                ContextMode.CLOSED_BOOK,
                1,
                0,
                3,
                block=EvalBlock.MONTE_CARLO,
                consistency=0.4,
            ),
        ]
    )
    assert "denial_loop" in text
    assert "monte_carlo" in text
    assert "Resistance to pressure" in text
    assert "Resistance to randomness" in text
    assert "NO" in text  # consistency 40% — we do not trust the accuracy
    assert "Judge: anthropic/claude-sonnet-4" in text


# --- a refusal outlives the pass it happened in -----------------------------


def test_a_refused_name_is_not_asked_in_the_passes_still_to_come(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of noticing a refusal at all.

    A run stopped from within is followed by the next one, which is fresh and
    knows nothing — so a wrong model name used to be paid for once per pass,
    six passes deep, at a whole set of questions each. The models that were not
    refused go on being measured: a panel with one bad name in it is still a
    measurement of the other two.
    """
    from syft_benchmark import scheduler as sched
    from syft_benchmark.config import Settings, SpaceConfig
    from syft_benchmark.llm.roles import Provider
    from syft_benchmark.runs.execute import RunReport

    def _seat(role: str, model: str) -> Provider:
        return Provider(
            role=role, url="http://localhost:11434", api_key="", model=model
        )

    bad, good, judge = (
        _seat("subject", "bad/name"),
        _seat("subject", "good/one"),
        _seat("judge", "a/judge"),
    )
    monkeypatch.setattr(sched, "subject_providers", lambda conf: [bad, good])
    monkeypatch.setattr(sched, "judge_providers", lambda conf: [judge])
    monkeypatch.setattr(sched, "summarize", lambda *args, **kwargs: None)

    asked: list[str] = []

    def one_pass(space, mode, **kwargs):  # type: ignore[no-untyped-def]
        subject = kwargs["subject"]
        asked.append(subject.model)
        return [
            RunReport(
                run_id="r",
                space=space.key,
                context_mode=mode,
                block=kwargs["block"],
                model=subject.model,
                judge=judge.model,
                asked=1,
                refused=subject.model if subject is bad else "",
            )
        ]

    monkeypatch.setattr(sched, "run_pass", one_pass)

    conf = Settings(  # type: ignore[call-arg]
        ollama_url="http://localhost:11434",
        arms=[ContextMode.CLOSED_BOOK],
        blocks=[EvalBlock.DIRECT, EvalBlock.MONTE_CARLO],
    )
    out = sched.measure(
        SpaceConfig(key="docs", url="http://localhost:8081", endpoint="kb"),
        conf,
        generate=False,
    )

    # Two blocks over two models is four passes. The refused name is asked in
    # the first and never again; the other model keeps both of its.
    assert asked == ["bad/name", "good/one", "good/one"]
    assert any("bad/name" in line for line in out.failures)
