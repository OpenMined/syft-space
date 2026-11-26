"""The refusal rule, option letters, empty answers, and re-grading verdicts
the old refusal rule gave without a judge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import syft_benchmark.runs.judge as judge
from syft_benchmark.config import JobState, Settings, Verdict
from syft_benchmark.db import Job, QaPair, Result, Run, session_scope
from syft_benchmark.llm import judge_provider
from syft_benchmark.report import run_view
from syft_benchmark.runs import refusal_regrade
from syft_benchmark.runs.judge import Gradable, grade_item, names_several_options
from syft_benchmark.runs.refusal import detect_abstain

SPACE = "pytest-refusal-regrade"
JOB = "pytest-refusal-regrade-job"
T0 = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)
MODEL = "moonshotai/kimi-k3"
J1, J2 = "judge/primary", "judge/second"


# --- the rule ----------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "I don't know",
        "**I don't know.**",
        "I don't know.\n\nI don't have specific information about this plan.",
        "No tengo información sobre ese plan. No puedo confirmarlo.",
    ],
)
def test_a_whole_answer_refusal_skips_the_judge(answer: str) -> None:
    assert detect_abstain(answer)


@pytest.mark.parametrize(
    "answer",
    [
        # Text before a web search glued to the answer after it.
        "I don't knowKementerian Sosial (Kemensos) menyalurkan bantuan.",
        "I don't know**Bob Azam** said the plant would close.",
        "I don't knowThe two obligations are Article 34 and Article 35.",
        # A refusal phrase inside a full answer.
        "The tariff was 25%, secured by lobbying from X. Neither the material "
        "nor the search names Natalia Viana, so I can't confirm the author.",
        "I don't know\n\nThe material states that Wagner died in 1883, not 1893.",
    ],
)
def test_a_refusal_inside_an_answer_goes_to_the_judge(answer: str) -> None:
    assert not detect_abstain(answer)


# --- option letters ----------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "both A and C",
        "Both A) X and C are false.",
        "**A) and C)**",
        "Options A, C",
        "The false statements are both A and C.",
    ],
)
def test_several_options_are_named(answer: str) -> None:
    assert names_several_options(answer)


@pytest.mark.parametrize(
    "answer",
    [
        "C\n\nThe material rules out A and B.",
        "**A) is FALSE.** Statements B and C match the material.",
        "A) Both parties agreed to the deal.",
    ],
)
def test_one_option_with_others_in_the_explanation(answer: str) -> None:
    assert not names_several_options(answer)


def test_an_answer_naming_several_options_is_not_correct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        judge, "chat", lambda *a, **k: calls.append(a) or ('{"correct": true}', {})
    )
    graded = grade_item(
        Gradable(question="Which is false?", expected="A) X", task_type="choice"),
        "Both A) X and C are false.",
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    assert graded.verdict is Verdict.HALLUCINATE
    assert graded.reasoning == judge.SEVERAL_OPTIONS
    assert calls == []


@pytest.mark.parametrize("generator", ["qa", "false_premise"])
def test_an_empty_answer_is_technical(generator: str) -> None:
    graded = grade_item(
        Gradable(question="q?", expected="a", generator=generator),
        "  ",
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    assert graded.verdict is Verdict.TECHNICAL


# --- re-grading --------------------------------------------------------------


def _seed() -> None:
    """One glued answer and one plain refusal, each given the old rule's
    abstain by two judges; J1 graded first, so it is the primary."""
    clock = T0
    rows: list[Any] = []
    answers = {
        "q-glued": "I don't knowThe two obligations are Article 34 and Article 35.",
        "q-plain": "I don't know",
    }
    for qa, answer in answers.items():
        for judge_model in (J1, J2):
            clock += timedelta(seconds=1)
            run_id = f"{JOB}-{qa}-{judge_model}"
            rows.append(
                Run(
                    id=run_id,
                    space=SPACE,
                    job_id=JOB,
                    context_mode="closed_book",
                    block="direct",
                    model=MODEL,
                    judge_model=judge_model,
                )
            )
            rows.append(
                Result(
                    id=f"{run_id}-res",
                    run_id=run_id,
                    qa_id=qa,
                    space=SPACE,
                    answer=answer,
                    verdict=Verdict.ABSTAIN.value,
                    reasoning="refused to answer",
                    judge_model=judge_model,
                    model=MODEL,
                    audit={
                        "judged_without_model": True,
                        "call": {"web_search": "plugin", "web_search_requests": 2},
                    },
                    created_at=clock,
                )
            )
    with session_scope() as session:
        session.add(
            Job(
                id=JOB,
                target=SPACE,
                state=JobState.SUCCEEDED.value,
                created_at=T0,
                finished_at=T0 + timedelta(hours=1),
            )
        )
        session.add_all(
            QaPair(
                id=qa,
                space=SPACE,
                generator="qa",
                question=f"Question {qa}?",
                answer="Article 34 and Article 35",
                status="active",
                model="gen/model",
                question_hash=qa,
            )
            for qa in answers
        )
        session.flush()
        session.add_all([r for r in rows if isinstance(r, Run)])
        session.flush()
        session.add_all([r for r in rows if isinstance(r, Result)])


@pytest.mark.needs_db
def test_old_rule_abstains_are_regraded_once_and_counted(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed()
    with session_scope() as session:
        found = refusal_regrade.plan(session, SPACE)
    assert found.found == 4
    assert found.still_refusals == 2
    assert sorted(c.judge for c in found.candidates) == [J1, J2]

    asked: list[str] = []

    def fake_chat(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        asked.append(kwargs["provider"].model)
        return '{"correct": true, "reasoning": "names both articles"}', {}

    monkeypatch.setattr(judge, "chat", fake_chat)
    outcome = refusal_regrade.apply(found, settings=Settings())
    assert (outcome.regraded, outcome.changed, outcome.failed) == (2, 2, 0)
    # Each verdict is re-graded by the judge that gave it.
    assert sorted(asked) == [J1, J2]

    with session_scope() as session:
        old = session.get(Result, f"{JOB}-q-glued-{J1}-res")
        assert old is not None and old.verdict == Verdict.ABSTAIN.value
        new = [
            r
            for r in session.query(Result).filter(Result.space == SPACE)
            if refusal_regrade.REGRADE_KEY in (r.audit or {})
        ]
        assert len(new) == 2
        assert {r.audit["regrade"]["old_verdict"] for r in new} == {"abstain"}
        assert {r.verdict for r in new} == {Verdict.CORRECT.value}
        # Nothing left to re-grade on a second run.
        assert refusal_regrade.plan(session, SPACE).candidates == []

        job = session.get(Job, JOB)
        assert job is not None
        report = run_view.compute(session, job, configured=[J1, J2])
    figures = report["models"][0]
    assert figures["right_alone"] == 1
    assert figures["regrade"] == {"answers": 1, "changed": 1}
    assert figures["searches"]["alone"] == {
        "answers": 2,
        "reported": 2,
        "total": 4,
        "max": 2,
    }
    assert figures["searches"]["with"] is None


@pytest.mark.needs_db
def test_a_failed_judge_call_stores_nothing(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed()
    from syft_benchmark.llm import LLMError

    def failing(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise LLMError("judge down")

    monkeypatch.setattr(judge, "chat", failing)
    with session_scope() as session:
        found = refusal_regrade.plan(session, SPACE)
    outcome = refusal_regrade.apply(found, settings=Settings())
    assert (outcome.regraded, outcome.failed) == (0, 2)
    with session_scope() as session:
        assert len(refusal_regrade.plan(session, SPACE).candidates) == 2
