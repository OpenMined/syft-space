"""Answers graded without a judge, and connect-the-facts held to every hop fact.

Fill-ins are matched to the expected span, multiple choice by its letter, and a
bare abstention is spotted by its wording, none of them at the cost of a judge
call. A connect-the-facts answer is correct only when it states every hop fact
the question does not already state. No database and no model: the judge call
is replaced by a canned reply; the demo questions are real ones from a run.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import Settings, Verdict
from syft_benchmark.db import QaPair
from syft_benchmark.generation import web_check
from syft_benchmark.llm import judge_provider
from syft_benchmark.runs import detect_abstain, grade_mcq, is_error
from syft_benchmark.runs import judge as judge_module
from syft_benchmark.runs.fill_in import match_fill_in
from syft_benchmark.runs.judge import Gradable, grade, grade_item

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
        judge=judge_provider(Settings()),
    )
    assert graded.verdict is Verdict.CORRECT
    assert graded.reasoning == "matched the expected answer"
    assert not calls
    assert not graded.judge_user and graded.cost_usd is None


def test_a_matched_fill_in_is_not_deferred() -> None:
    graded = grade_item(
        _item(task_type="extractive"),
        "Microsoft",
        settings=Settings(),
        defer=True,
        judge=judge_provider(Settings()),
    )
    assert graded.verdict is Verdict.CORRECT


def test_an_unmatched_fill_in_goes_to_the_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _reply(monkeypatch, '{"correct": true, "false_claims": false}')
    graded = grade_item(
        _item(task_type="extractive"),
        "Microsoft Corp",
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    assert graded.verdict is Verdict.CORRECT
    assert len(calls) == 1


def test_only_fill_ins_are_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _reply(monkeypatch, '{"correct": true, "false_claims": false}')
    grade_item(
        _item(task_type="abstractive"),
        "Microsoft",
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
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
        judge=judge_provider(Settings()),
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


def test_a_pair_without_hop_facts_is_judged_on_correct_alone(
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
    judge = judge_provider(conf)
    assert web_check._graded(fill_in, "Microsoft", conf, judge).verdict is (
        Verdict.CORRECT
    )
    assert calls == []

    multihop = QaPair(
        question="How large was HubSpot, and what changed?",
        answer="About 7,000 staff; two units merged.",
        task_type="abstractive",
        meta={"grading": "judge", "hop_facts": _HOPS},
    )
    web_check._graded(multihop, "About 7,000 staff.", conf, judge)
    assert "Required facts" in calls[0][1]


# --- connect the facts: facts the question already states ------------------

_DEMO_HOPS = {
    "1f0567d3": (
        "Chad Franklin, the dating coach who posts on TikTok as @DefundSimping, "
        "says he obscures identifying details when he shares client screenshots. "
        "Roughly how much revenue does his current client roster represent at "
        "his minimum fee?",
        "Franklin's clients pay upwards of $5,000 each, and he says he has 20 "
        "clients on his roster. At the minimum fee that comes to at least about "
        "$100,000, all from clients whose private communications he sometimes "
        "posts after blocking names, faces and other features.",
        [
            "Franklin's clients pay upwards of $5,000 for his services",
            "Franklin says he has 20 clients on his roster and tries to block "
            "every name, lip, face, and eye when posting screenshots",
        ],
        "Based on the material provided:\n\n"
        "- Chad Franklin has **20 clients on his roster** [2]\n"
        "- Clients pay **upwards of $5,000** for his services [1]\n\n"
        "At his minimum fee of $5,000, his current client roster represents "
        "approximately **$100,000** in revenue (20 clients × $5,000).",
    ),
    "dfec8276": (
        "Amazon's 2026 Kindle Aluminum costs $190. What price range would a "
        "buyer pay for the plastic Ube-colored 2026 Kindle instead, and what "
        "storage would they give up?",
        "The plastic Ube Kindle costs $20 to $40 less, so roughly $150 to $170 "
        "depending on whether it has lock-screen ads. It has 16 GB of storage, "
        "half the Kindle Aluminum's 32 GB.",
        [
            "The Kindle Aluminum is priced at $190 and has 32 GB of storage with "
            "no lock screen ads",
            "The plastic Ube version costs $20 to $40 less depending on ads and "
            "has half the storage, 16 GB",
        ],
        "Based on the material, if the 2026 Kindle Aluminum costs $190, the "
        "plastic Ube-colored 2026 Kindle would cost **$150–$170** (between $20 "
        "and $40 less).\n\nThe buyer would give up **half the storage**, going "
        "from **32 GB to 16 GB**.",
    ),
    "39d795e3": (
        "Rubedo Life Sciences' drug clears senescent cells by transiently "
        "inhibiting the protein GPX4. Why did Memorial Sloan Kettering "
        "dermatologist Anthony Rossi warn that eliminating such cells is not "
        "purely beneficial?",
        "Inhibiting GPX4 makes senescent cells more susceptible to ferroptosis, "
        "a regulated form of cell death, so the drug removes them. Rossi warned "
        "that some senescent cells are useful because they shut down harmful "
        "processes such as cancer progression, and senescent cells also play a "
        "role in normal tumor suppression and wound healing.",
        [
            "Rubedo's drug transiently turns off GPX4 so senescent cells undergo "
            "ferroptosis",
            "Anthony Rossi said some senescent cells are good because they turn "
            "off things like cancer progression, and senescent cells are "
            "involved in tumor suppression and wound healing",
        ],
        "According to the material, Memorial Sloan Kettering dermatologist "
        "Anthony Rossi warned that eliminating senescent cells is not purely "
        "beneficial because **some senescent cells are good because they turn "
        "things off, like cancer progression**.",
    ),
}


@pytest.mark.parametrize("qa", sorted(_DEMO_HOPS))
def test_hop_facts_go_to_the_judge_with_the_question(
    monkeypatch: pytest.MonkeyPatch, qa: str
) -> None:
    question, expected, facts, answer = _DEMO_HOPS[qa]
    calls = _reply(
        monkeypatch, '{"correct": true, "false_claims": false, "covered": [true, true]}'
    )
    graded = grade_item(
        Gradable(
            question=question,
            expected=expected,
            generator="multihop_synthesis",
            task_type="abstractive",
            meta={"hop_facts": facts},
        ),
        answer,
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    system, user = calls[0]
    # A fact the question states counts as stated: in the rules and the hops.
    assert "that the question does not already state" in system
    assert "question itself already" in system
    assert "answer or by the question" in system
    assert user.startswith(f"Question:\n{question}\n")
    assert f"1. {facts[0]}\n2. {facts[1]}\n" in user
    assert "that the question already states counts as covered" in user
    # Covered keeps its meaning: the judge's covered list decides.
    assert graded.verdict is Verdict.CORRECT


def test_a_fact_neither_stated_nor_given_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    question, expected, facts, answer = _DEMO_HOPS["39d795e3"]
    _reply(
        monkeypatch,
        '{"correct": true, "false_claims": false, "covered": [true, false]}',
    )
    graded = grade(
        question,
        expected,
        answer,
        hop_facts=facts,
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    assert graded.verdict is Verdict.ABSTAIN
    assert "a required fact is missing" in graded.reasoning


# --- letters, abstentions and errors: no judge call ------------------------


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
