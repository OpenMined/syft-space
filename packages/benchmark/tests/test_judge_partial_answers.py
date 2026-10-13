"""Incomplete answers are not hallucinations; only a false claim is.

No database and no model: the judge call is replaced by a canned reply.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import Settings, Verdict
from syft_benchmark.runs import execute
from syft_benchmark.runs import judge as judge_module


def _reply(monkeypatch: pytest.MonkeyPatch, raw: str) -> list[str]:
    systems: list[str] = []

    def fake_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        systems.append(system)
        return raw, {}

    monkeypatch.setattr(judge_module, "chat", fake_chat)
    return systems


def _grade(answer: str = "Lyon, I think it was founded in 1990.") -> Any:
    return judge_module.grade(
        "Where is the company based, and when was it founded?",
        "Paris, in 1990.",
        answer,
        settings=Settings(),
    )


def test_the_judge_is_asked_for_false_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    systems = _reply(monkeypatch, '{"correct": true, "false_claims": false}')
    assert _grade().verdict is Verdict.CORRECT
    assert '"false_claims"' in systems[0]


@pytest.mark.parametrize(
    ("raw", "verdict"),
    [
        ('{"correct": false, "false_claims": true, "reasoning": "Lyon"}', "H"),
        ('{"correct": false, "false_claims": false, "reasoning": "partial"}', "A"),
        ('{"correct": false, "false_claims": "false", "reasoning": "partial"}', "A"),
        ('{"correct": false, "false_claims": "yes", "reasoning": "Lyon"}', "H"),
        # A true correct wins over the second field.
        ('{"correct": true, "false_claims": true, "reasoning": "same"}', "C"),
        # The string "false" is not a correct answer.
        ('{"correct": "false", "false_claims": false, "reasoning": "x"}', "A"),
    ],
)
def test_not_correct_is_a_hallucination_only_with_a_false_claim(
    monkeypatch: pytest.MonkeyPatch, raw: str, verdict: str
) -> None:
    _reply(monkeypatch, raw)
    expected = {"C": Verdict.CORRECT, "A": Verdict.ABSTAIN, "H": Verdict.HALLUCINATE}
    assert _grade().verdict is expected[verdict]


def test_an_incomplete_answer_says_why_it_is_not_a_hallucination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reply(
        monkeypatch,
        '{"correct": false, "false_claims": false, "reasoning": "misses the year"}',
    )
    graded = _grade("I don't know the city, but it was founded in 1990.")
    assert graded.verdict is Verdict.ABSTAIN
    assert graded.reasoning.startswith("misses the year")
    assert "nothing false" in graded.reasoning


@pytest.mark.parametrize(
    "raw",
    [
        '{"correct": false, "reasoning": "wrong city"}',
        '{"correct": false, "false_claims": "maybe", "reasoning": "wrong city"}',
        '{"correct": false, "false_claims": null, "reasoning": "wrong city"}',
    ],
)
def test_a_missing_false_claims_counts_as_did_not_know(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    _reply(monkeypatch, raw)
    graded = _grade()
    assert graded.verdict is Verdict.ABSTAIN
    assert graded.reasoning.startswith("wrong city")
    assert "did not say whether anything is false" in graded.reasoning


def test_a_wrong_option_letter_stays_a_hallucination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    systems = _reply(monkeypatch, "{}")
    graded = judge_module.grade(
        "Which city?",
        "B) Paris",
        "The answer is C) Lyon.",
        is_mcq=True,
        settings=Settings(),
    )
    assert graded.verdict is Verdict.HALLUCINATE
    assert systems == []  # matched by the letter, no judge called


@pytest.mark.parametrize(
    ("covered", "verdict"),
    [
        ("[true, true, true, true]", Verdict.CORRECT),
        ("[true, false, false, false]", Verdict.INCOMPLETE),
    ],
)
def test_key_facts_below_the_bar_count_as_incomplete(
    monkeypatch: pytest.MonkeyPatch, covered: str, verdict: Verdict
) -> None:
    _reply(monkeypatch, f'{{"covered": {covered}, "reasoning": "x"}}')
    graded = judge_module.grade_key_facts(
        "Goldman Sachs named a new technology banking co-head.",
        ["fact one", "fact two", "fact three", "fact four"],
        settings=Settings(key_facts_threshold=0.75),
    )
    assert graded.verdict is verdict


def _replies(monkeypatch: pytest.MonkeyPatch, *raws: str) -> list[str]:
    """The judge answers the calls in order, one canned reply each."""
    systems: list[str] = []
    queue = list(raws)

    def fake_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        systems.append(system)
        return queue.pop(0), {"cost_usd": 0.01, "latency_s": 1.0}

    monkeypatch.setattr(judge_module, "chat", fake_chat)
    return systems


@pytest.mark.parametrize(
    ("covered", "grounded", "verdict"),
    [
        ("[true, true, true, true]", "true", Verdict.CORRECT),
        ("[true, false, false, false]", "true", Verdict.INCOMPLETE),
        ("[true, true, true, true]", "false", Verdict.HALLUCINATE),
        ("[true, false, false, false]", "false", Verdict.HALLUCINATE),
        # A dropped field hides no invention.
        ("[true, true, true, true]", "null", Verdict.HALLUCINATE),
    ],
)
def test_key_facts_check_the_article(
    monkeypatch: pytest.MonkeyPatch, covered: str, grounded: str, verdict: Verdict
) -> None:
    systems = _replies(
        monkeypatch,
        f'{{"covered": {covered}, "reasoning": "x"}}',
        f'{{"grounded": {grounded}, "reasoning": "adds a founding year"}}',
    )
    graded = judge_module.grade_key_facts(
        "Goldman Sachs named a new technology banking co-head.",
        ["fact one", "fact two", "fact three", "fact four"],
        article="Goldman Sachs named Jane Doe co-head of technology banking.",
        settings=Settings(key_facts_threshold=0.75),
    )
    assert graded.verdict is verdict
    assert systems == [
        judge_module.dated(judge_module._KEY_FACTS_SYSTEM),
        judge_module.dated(judge_module._GROUNDED_SYSTEM),
    ]
    # Both calls are in the audit trail and the cost.
    assert judge_module._GROUNDED_SYSTEM in graded.judge_system
    assert "Jane Doe" in graded.judge_user
    assert graded.cost_usd == pytest.approx(0.02)


def test_a_failed_article_check_measures_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise judge_module.LLMError("timeout")
        return '{"covered": [true], "reasoning": "x"}', {}

    monkeypatch.setattr(judge_module, "chat", fake_chat)
    graded = judge_module.grade_key_facts(
        "An answer.", ["fact"], article="The article.", settings=Settings()
    )
    assert graded.verdict is Verdict.TECHNICAL


def test_grade_item_hands_key_facts_the_article(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    systems = _replies(
        monkeypatch,
        '{"covered": [true], "reasoning": "x"}',
        '{"grounded": false, "reasoning": "invented"}',
    )
    item = judge_module.Gradable(
        question="Explain this simply.\n\nTopic: a banker",
        expected="...",
        generator="tiered_explanation",
        task_type="abstractive",
        meta={"grading": "key_facts", "key_facts": ["fact"]},
        context="The article.",
    )
    graded = judge_module.grade_item(item, "An answer.", settings=Settings())
    assert graded.verdict is Verdict.HALLUCINATE
    assert len(systems) == 2


def test_a_made_up_trick_answer_stays_a_hallucination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trick questions have their own judge; the free-text change does not reach it."""
    _reply(monkeypatch, '{"behavior": "made_up", "reasoning": "invented a founder"}')
    case = judge_module.ControlCase(
        kind=judge_module.UNANSWERABLE, question="Who founded it?", missing="founder"
    )
    graded = judge_module.grade_control(
        case, "John Smith founded it.", settings=Settings()
    )
    assert graded.verdict is Verdict.HALLUCINATE


@pytest.mark.parametrize(
    ("system", "premise"),
    [
        (execute.CLOSED_BOOK_SYSTEM, "assumes something that isn't true"),
        (execute._WITH_CONTEXT_SYSTEM, "assumes something the material contradicts"),
    ],
)
def test_both_arms_correct_a_false_premise_before_abstaining(
    system: str, premise: str
) -> None:
    """The premise line comes first; "I don't know" is only the otherwise."""
    assert premise in system
    assert system.index(premise) < system.index("respond with ONLY: I don't know")
    assert "Otherwise, if" in system
