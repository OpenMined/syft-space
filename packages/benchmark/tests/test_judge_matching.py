"""Fill-ins matched without a judge; connect-the-facts held to every hop fact.

No database and no model: the judge call is replaced by a canned reply.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import Settings, Verdict
from syft_benchmark.db import QaPair
from syft_benchmark.generation import web_check
from syft_benchmark.runs import judge as judge_module
from syft_benchmark.runs.fill_in import match_fill_in
from syft_benchmark.runs.judge import Gradable, grade_item

_SENTENCE = "Fill in the blank: The deal was signed by ______ in Paris."


def _reply(monkeypatch: pytest.MonkeyPatch, raw: str) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def fake_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        calls.append((system, user))
        return raw, {}

    monkeypatch.setattr(judge_module, "chat", fake_chat)
    return calls


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("Microsoft", "microsoft"),
        ("Microsoft", "**Microsoft.**"),
        ("Microsoft", "The answer is Microsoft."),
        ("Microsoft", "Answer: Microsoft"),
        ("the United States", "United States"),
        ("U.S.", "US"),
        ("O’Brien", "O'Brien"),
        ("Coca–Cola", "Coca-Cola"),
        ("1,200", "1200"),
        ("12", "twelve"),
        ("1.50", "1.5"),
        ("5%", "5 percent"),
        ("March 3, 2024", "3 March 2024"),
        ("March 3rd, 2024", "2024-03-03"),
        ("Feb 29", "29 February"),
        ("Microsoft", "The deal was signed by Microsoft in Paris."),
    ],
)
def test_equivalent_spans_match(expected: str, answer: str) -> None:
    assert match_fill_in(_SENTENCE, expected, answer)


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("Microsoft", "Google"),
        ("Microsoft", "Not Microsoft but Google"),
        ("Series A", "Series"),
        ("1.5", "15"),
        ("1,5", "15"),
        ("-5", "5"),
        ("March 3, 2024", "March 2024"),
        ("March 3", "March 3, 2024"),
        ("Microsoft", "Microsoft\nor maybe Google"),
        ("Microsoft", ""),
    ],
)
def test_other_answers_do_not_match(expected: str, answer: str) -> None:
    assert not match_fill_in(_SENTENCE, expected, answer)


def _item(**kwargs: Any) -> Gradable:
    return Gradable(question=_SENTENCE, expected="Microsoft", **kwargs)


def test_a_matched_fill_in_costs_no_judge_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _reply(monkeypatch, '{"correct": false, "false_claims": true}')
    graded = grade_item(
        _item(generator="named_entity_masking", task_type="extractive"),
        "Microsoft.",
        settings=Settings(),
    )
    assert graded.verdict is Verdict.CORRECT
    assert graded.reasoning == "matched the expected answer"
    assert not calls
    assert not graded.judge_user and graded.cost_usd is None


def test_a_matched_fill_in_is_not_deferred() -> None:
    graded = grade_item(
        _item(task_type="extractive"), "Microsoft", settings=Settings(), defer=True
    )
    assert graded.verdict is Verdict.CORRECT


def test_an_unmatched_fill_in_goes_to_the_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _reply(monkeypatch, '{"correct": true, "false_claims": false}')
    graded = grade_item(
        _item(task_type="extractive"), "Microsoft Corp", settings=Settings()
    )
    assert graded.verdict is Verdict.CORRECT
    assert len(calls) == 1


def test_only_fill_ins_are_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _reply(monkeypatch, '{"correct": true, "false_claims": false}')
    grade_item(_item(task_type="abstractive"), "Microsoft", settings=Settings())
    assert len(calls) == 1


_HOPS = ["HubSpot had about 7,000 staff", "it merged two business units"]


def _multihop(monkeypatch: pytest.MonkeyPatch, raw: str, meta: Any) -> Any:
    calls = _reply(monkeypatch, raw)
    graded = grade_item(
        Gradable(
            question="How large was HubSpot and what changed?",
            expected="About 7,000 staff; two units merged.",
            generator="multihop_synthesis",
            task_type="abstractive",
            meta=meta,
        ),
        "Around 7,000 people.",
        settings=Settings(),
    )
    return graded, calls


def test_hop_facts_reach_the_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    graded, calls = _multihop(
        monkeypatch,
        '{"correct": true, "false_claims": false, "covered": [true, true]}',
        {"hop_facts": _HOPS},
    )
    system, user = calls[0]
    assert '"covered"' in system
    assert "Required facts:\n1. HubSpot had about 7,000 staff\n2. it merged" in user
    assert graded.verdict is Verdict.CORRECT
    assert graded.judge_system == system


@pytest.mark.parametrize(
    ("raw", "verdict"),
    [
        ('{"correct": true, "false_claims": false, "covered": [true, false]}', "A"),
        ('{"correct": true, "false_claims": true, "covered": [true, false]}', "H"),
        ('{"correct": true, "covered": [true, "no"]}', "A"),
        ('{"correct": false, "false_claims": false, "covered": [true, true]}', "A"),
        # No "covered" from the judge: its "correct" stands.
        ('{"correct": true, "false_claims": false}', "C"),
    ],
)
def test_correct_needs_every_hop_fact(
    monkeypatch: pytest.MonkeyPatch, raw: str, verdict: str
) -> None:
    graded, _ = _multihop(monkeypatch, raw, {"hop_facts": _HOPS})
    expected = {"C": Verdict.CORRECT, "A": Verdict.ABSTAIN, "H": Verdict.HALLUCINATE}
    assert graded.verdict is expected[verdict]


def test_a_missing_hop_fact_is_noted(monkeypatch: pytest.MonkeyPatch) -> None:
    graded, _ = _multihop(
        monkeypatch,
        '{"correct": true, "false_claims": false, "covered": [true, false],'
        ' "reasoning": "no merger"}',
        {"hop_facts": _HOPS},
    )
    assert graded.reasoning.startswith("no merger")
    assert "a required fact is missing" in graded.reasoning
    assert "nothing false" in graded.reasoning


def test_a_pair_without_hop_facts_is_judged_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graded, calls = _multihop(
        monkeypatch, '{"correct": true, "false_claims": false}', {}
    )
    system, user = calls[0]
    assert '"covered"' not in system
    assert "Required facts" not in user
    assert graded.verdict is Verdict.CORRECT


def test_the_web_check_grades_fill_ins_and_hop_facts_as_a_run_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _reply(monkeypatch, '{"correct": true, "false_claims": false}')
    conf = Settings()
    fill_in = QaPair(
        question=_SENTENCE,
        answer="Microsoft",
        task_type="extractive",
        meta={"grading": "judge"},
    )
    assert web_check._graded(fill_in, "Microsoft", conf, None).verdict is (
        Verdict.CORRECT
    )
    assert calls == []

    multihop = QaPair(
        question="How large was HubSpot, and what changed?",
        answer="About 7,000 staff; two units merged.",
        task_type="abstractive",
        meta={"grading": "judge", "hop_facts": _HOPS},
    )
    web_check._graded(multihop, "About 7,000 staff.", conf, None)
    assert "Required facts" in calls[0][1]
