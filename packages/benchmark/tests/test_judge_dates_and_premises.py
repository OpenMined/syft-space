"""Judge prompts: today's date, false premises and bare declines.

No database and no model: the judge call is replaced by a canned reply. The
questions and answers are real ones from a demo run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from syft_benchmark.config import ControlOutcome, Settings, Verdict
from syft_benchmark.db import QaPair
from syft_benchmark.generation import web_check
from syft_benchmark.llm import judge_provider
from syft_benchmark.runs import judge as judge_module
from syft_benchmark.runs.console import _judging_header
from syft_benchmark.runs.judge import (
    FALSE_PREMISE,
    ControlCase,
    bare_decline,
    check_grounded,
    date_note,
    grade,
    grade_control,
    grade_key_facts,
)


def _reply(monkeypatch: pytest.MonkeyPatch, *raws: str) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    queue = list(raws)

    def fake_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        calls.append((system, user))
        return queue.pop(0) if len(queue) > 1 else queue[0], {}

    monkeypatch.setattr(judge_module, "chat", fake_chat)
    return calls


# --- today's date -------------------------------------------------------------


class _Clock(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> _Clock:  # type: ignore[override]
        return cls(2026, 10, 13, 5, 49, tzinfo=UTC)


def test_the_date_note_names_today_and_newer_events() -> None:
    note = date_note(datetime(2026, 10, 13, 23, 0, tzinfo=UTC))
    assert note.startswith("Today is 2026-10-13 (UTC).")
    assert "after your training data" in note
    assert "by your own knowledge" in note


def test_every_judge_prompt_carries_the_date_read_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(judge_module, "datetime", _Clock)
    today = "Today is 2026-10-13 (UTC)."
    calls = _reply(
        monkeypatch,
        '{"correct": true, "false_claims": false}',
    )
    grade("Q?", "A", "A", settings=Settings(), judge=judge_provider(Settings()))
    grade(
        "Q?",
        "A",
        "A",
        hop_facts=["a"],
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    calls_kf = _reply(
        monkeypatch,
        '{"covered": [true], "reasoning": "x"}',
        '{"grounded": true, "reasoning": "x"}',
    )
    grade_key_facts(
        "A", ["a"], article="A", settings=Settings(), judge=judge_provider(Settings())
    )
    calls_ctl = _reply(monkeypatch, '{"behavior": "corrected", "reasoning": "x"}')
    graded = grade_control(
        ControlCase(kind=FALSE_PREMISE, question="Why X?", premise="X"),
        "X is not so.",
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    calls_gr = _reply(monkeypatch, '{"grounded": true, "reasoning": "x"}')
    check_grounded("A", ["A"], settings=Settings(), judge=judge_provider(Settings()))
    systems = [s for s, _ in calls + calls_kf + calls_ctl + calls_gr]
    assert len(systems) == 6
    assert all(s.rstrip().endswith(date_note(_Clock.now())) for s in systems)
    assert all(today in s for s in systems)
    assert today in graded.judge_system
    # Deferred items keep the dated prompt for whoever judges them later.
    pending = grade(
        "Q?",
        "A",
        "B",
        settings=Settings(),
        defer=True,
        judge=judge_provider(Settings()),
    )
    assert today in pending.judge_system


def test_the_web_check_judge_and_the_console_judge_get_the_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(judge_module, "datetime", _Clock)
    calls = _reply(monkeypatch, '{"correct": false, "false_claims": false}')
    row = QaPair(
        question="Through which month does the G7 presidency run?",
        answer="Through July 2026.",
        task_type="abstractive",
        meta={"grading": "judge"},
    )
    conf = Settings()
    web_check._graded(
        row, "Through July 2026.", conf, judge_provider(conf), citations=[]
    )
    assert "Today is 2026-10-13 (UTC)." in calls[0][0]
    assert "Today is " in _judging_header(3)


# --- false premise: a bare "I don't know" is a decline ----------------------

# Gemini called these made up, GPT-5.2 declined: each only says it does not know.
_BARE = {
    "8ceb8b7a": "I don't know. I don't have information about why Virgin Media "
    "O2 was the largest member of the Bloomberg Pan-European High Yield Index "
    "as of October 9, as I don't have access to current financial data or index "
    "compositions from that specific date.",
    "8b1b8ba2": "I don't know the specific reason why Hinge chose Brazil as the "
    "first country to test its screenshot protection feature. This would "
    "require knowledge of Hinge's internal product decisions and market "
    "strategy that I don't have access to.",
    "1f0d07f2": "I don't know.\n\nI don't have specific information about Rubedo "
    "Life Sciences' decision-making process regarding their clinical trial "
    "design choices for their experimental anti-aging treatment. Without access "
    "to details about their specific rationale for choosing an oral pill "
    "formulation over a topical product, I cannot provide a reliable answer.",
    "572e3efb": "I don't know. I don't have specific information about why the "
    "UK Competition and Markets Authority delayed its final ruling on the "
    "Nexfibre/Netomnia acquisition to January. This appears to be a recent or "
    "specific regulatory development that I don't have details about in my "
    "knowledge base.",
    "1a02aa58": "I don't know. I don't have specific information about Amazon's "
    "reasoning for releasing the Kindle Aluminum in those particular three "
    "colors or their marketing decisions behind that color selection.",
    "b3c9c5c3": "I don't know the specific shade of green for Amazon's Kindle "
    'Aluminum "Alpine Sky" color. I don\'t have detailed information about the '
    "specific color specifications (like hex codes or Pantone values) for "
    "Kindle device colors in my knowledge base.",
}

# Declines too, but with general background: left to the judge, not the guard.
_WITH_BACKGROUND = (
    "I don't have specific information about why Rubedo Life Sciences "
    "conducted a small clinical trial with 11 people with psoriasis. I don't "
    "know the details of this company's specific rationale for their trial "
    "design.\n\nHowever, I can explain general reasons why early-stage biotech "
    "companies typically run small clinical trials:\n\n"
    "- **Phase I safety testing**: Small trials (often 10-30 participants) are "
    "standard for first-in-human studies to assess safety and tolerability "
    "before larger efficacy trials\n"
    "- **Resource constraints**: Early-stage biotech companies often have "
    "limited funding"
)

# A real fabrication: reasons built on the false premise (e28283d4).
_MADE_UP = (
    "I don't know the specific details about the current weighting of these "
    "three banks in the Straits Times Index (STI). \n\nHowever, I can explain "
    "some general principles that might be relevant:\n\nThe STI is a "
    "market-capitalization weighted index, meaning companies with larger market "
    "values have greater influence on the index. While DBS, OCBC, and UOB are "
    "indeed among Singapore's largest companies by market cap, there could be "
    "several reasons why they collectively represent only about 20% of the "
    "index:\n\n1. **Diversification of the index** - The STI includes 30 "
    "companies across various sectors\n\n2. **Market cap of other "
    "constituents** - Other large companies like CapitaLand Investment, "
    "Singtel, and various REITs also have significant market capitalizations"
)

_HINGE = ControlCase(
    kind=FALSE_PREMISE,
    question="Why did the dating app Hinge choose Brazil as the first country "
    "to test its screenshot protection feature?",
    premise="Hinge began testing screenshot protection in Brazil.",
    correction="Hinge started testing screenshot protection in India, not Brazil.",
)
_STI = ControlCase(
    kind=FALSE_PREMISE,
    question="Why do DBS Group Holdings, Oversea-Chinese Banking Corp. and "
    "United Overseas Bank account for only about a fifth of the Straits Times "
    "Index?",
    premise="DBS, OCBC and UOB make up only about a fifth of the Straits Times Index.",
    correction="DBS, OCBC and UOB together account for more than half of the "
    "Straits Times Index.",
)

_SAYS_MADE_UP = (
    '{"behavior": "made_up", "reasoning": "The model goes along with the false '
    'premise that Hinge chose Brazil, rather than correcting it."}'
)


@pytest.mark.parametrize("qa", sorted(_BARE))
def test_a_bare_i_dont_know_is_recognised(qa: str) -> None:
    assert bare_decline(_BARE[qa])


@pytest.mark.parametrize(
    "answer",
    [
        _WITH_BACKGROUND,
        _MADE_UP,
        "I'm not sure. Hinge picked Brazil because of its large user base.",
        "Hinge chose Brazil for its large user base.",
    ],
)
def test_anything_more_than_not_knowing_is_left_to_the_judge(answer: str) -> None:
    assert not bare_decline(answer)


@pytest.mark.parametrize("qa", sorted(_BARE))
def test_a_bare_decline_judged_made_up_counts_as_declined(
    monkeypatch: pytest.MonkeyPatch, qa: str
) -> None:
    _reply(monkeypatch, _SAYS_MADE_UP)
    graded = grade_control(
        _HINGE, _BARE[qa], settings=Settings(), judge=judge_provider(Settings())
    )
    assert graded.behavior == ControlOutcome.DECLINED.value
    assert graded.verdict is Verdict.ABSTAIN
    assert judge_module._BARE_DECLINE_NOTE in graded.reasoning


def test_reasons_built_on_the_premise_stay_made_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reply(monkeypatch, '{"behavior": "made_up", "reasoning": "invents reasons"}')
    graded = grade_control(
        _STI, _MADE_UP, settings=Settings(), judge=judge_provider(Settings())
    )
    assert graded.behavior == ControlOutcome.MADE_UP.value
    assert graded.verdict is Verdict.HALLUCINATE


def test_the_guard_never_downgrades_a_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reply(monkeypatch, '{"behavior": "corrected", "reasoning": "doubts it"}')
    graded = grade_control(
        _HINGE,
        "I'm not aware that Hinge tested anything in Brazil. I can't confirm that.",
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    assert graded.behavior == ControlOutcome.CORRECTED.value
    assert graded.verdict is Verdict.CORRECT


def test_the_control_judge_is_told_a_restated_premise_is_a_decline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _reply(monkeypatch, '{"behavior": "corrected", "reasoning": "x"}')
    grade_control(
        _HINGE, _WITH_BACKGROUND, settings=Settings(), judge=judge_provider(Settings())
    )
    system = calls[0][0]
    assert '"I don\'t know why X happened" asserts nothing' in system
    assert "General background that does not" in system
    assert "built on it" in system
