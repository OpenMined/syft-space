"""Judging on its own: listing verdicts and overriding one by hand.

Grading never mutates a `Result` row — a verdict is always inserted, never
updated, and every reader (including `list_results`'s own `is_latest`) picks
the freshest by `created_at`. That is the one invariant worth a real database
for here.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from syft_benchmark.config import SpaceConfig, Verdict
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.llm import Provider
from syft_benchmark.runs.judge_stage import (
    judge_pending,
    list_results,
    override_verdict,
)

SPACE = "pytest-judge-stage"


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean():  # type: ignore[no-untyped-def]
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Result).where(Result.space == SPACE))
            session.execute(delete(Run).where(Run.space == SPACE))
            session.execute(delete(QaPair).where(QaPair.space == SPACE))

    wipe()
    yield
    wipe()


@needs_db
def test_override_inserts_a_new_row_and_leaves_the_old_one_alone(clean: None) -> None:
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-override",
                space=SPACE,
                generator="cloze",
                question="What port does the benchmark database listen on?",
                answer="5442",
                status="active",
                model="m",
                question_hash="h-override",
            )
        )
        session.add(
            Run(id="run-override", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="result-original",
                run_id="run-override",
                qa_id="p-override",
                space=SPACE,
                answer="5443",
                verdict=Verdict.HALLUCINATE.value,
                reasoning="off by one",
            )
        )

    new_id = override_verdict(
        "result-original", Verdict.CORRECT, reasoning="actually fine", owner="pytest"
    )
    assert new_id is not None
    assert new_id != "result-original"

    with session_scope() as session:
        original = session.get(Result, "result-original")
        assert original is not None
        assert (
            original.verdict == Verdict.HALLUCINATE.value
        ), "the old row must not change"

        overridden = session.get(Result, new_id)
        assert overridden is not None
        assert overridden.verdict == Verdict.CORRECT.value
        assert overridden.qa_id == "p-override"
        assert overridden.audit.get("judged_by_owner") == "pytest"


@needs_db
def test_overriding_an_unknown_result_returns_none(clean: None) -> None:
    assert override_verdict("no-such-result", Verdict.CORRECT) is None


@needs_db
def test_judging_a_pending_answer_survives_the_session_closing(clean: None) -> None:
    """Regression, two bugs at once:

    `_pending_tasks` used to read `Result`/`Run` columns after the session
    that loaded them had already committed and closed, which SQLAlchemy only
    ever catches at attribute-access time — a mock session would not have
    noticed, so this needs the real database.

    It also used to treat a bare `judge_model` match as "already graded by
    this judge" — but a deferred answer's placeholder already carries the
    judge it is waiting for (`_save_result` stamps it before any verdict
    exists), so with only one judge configured that match was true for every
    pending row and the job "succeeded" having graded nothing. Hence
    `judge_model="t"` below, matching the seat doing the (live) judging.
    """
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-pending",
                space=SPACE,
                generator="cloze",
                question="q",
                answer="a",
                status="active",
                model="m",
                question_hash="h-pending",
                meta={"grading": "behavior"},
            )
        )
        session.add(
            Run(
                id="run-pending",
                space=SPACE,
                context_mode="closed_book",
                block="direct",
                model="m",
            )
        )
        session.add(
            Result(
                id="result-pending",
                run_id="run-pending",
                qa_id="p-pending",
                space=SPACE,
                answer="I don't know",
                verdict=Verdict.PENDING.value,
                judge_model="t",
            )
        )

    seat = Provider(role="judge", url="http://judge.invalid", api_key="k", model="t")
    report = judge_pending(
        SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="e"), judge=seat
    )
    assert report.checked == 1
    assert report.abstain == 1

    rows, _ = list_results(SPACE, qa_id="p-pending")
    latest = [row for row in rows if row.is_latest]
    assert len(latest) == 1
    assert latest[0].verdict == Verdict.ABSTAIN.value
    assert latest[0].generator == "cloze"


@needs_db
def test_judging_reports_progress_as_it_grades(clean: None) -> None:
    """A live judging run used to report nothing until it finished — a
    console watching it had only a spinner, not a count. `judge_pending`
    now tells `watch` how many of how many are done, the same way an
    evaluate pass already does.
    """
    with session_scope() as session:
        for n in range(2):
            session.add(
                QaPair(
                    id=f"p-progress-{n}",
                    space=SPACE,
                    generator="cloze",
                    question="q",
                    answer="a",
                    status="active",
                    model="m",
                    question_hash=f"h-progress-{n}",
                    meta={"grading": "behavior"},
                )
            )
            session.add(
                Run(
                    id=f"run-progress-{n}",
                    space=SPACE,
                    context_mode="closed_book",
                    context_source=f"progress-{n}",
                    block="direct",
                    model="m",
                )
            )
            session.add(
                Result(
                    id=f"result-progress-{n}",
                    run_id=f"run-progress-{n}",
                    qa_id=f"p-progress-{n}",
                    space=SPACE,
                    answer="I don't know",
                    verdict=Verdict.PENDING.value,
                    judge_model="t",
                )
            )

    seen: list[tuple[int, int]] = []
    seat = Provider(role="judge", url="http://judge.invalid", api_key="k", model="t")
    report = judge_pending(
        SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="e"),
        judge=seat,
        watch=lambda progress: seen.append((progress.done, progress.total)),
    )
    assert report.checked == 2
    assert seen == [(1, 2), (2, 2)]


@needs_db
def test_listing_marks_only_the_freshest_row_per_question_as_latest(
    clean: None,
) -> None:
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-latest",
                space=SPACE,
                generator="cloze",
                question="q",
                answer="a",
                status="active",
                model="m",
                question_hash="h-latest",
            )
        )
        session.add(
            Run(id="run-latest", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="result-old",
                run_id="run-latest",
                qa_id="p-latest",
                space=SPACE,
                verdict=Verdict.HALLUCINATE.value,
            )
        )

    override_verdict("result-old", Verdict.CORRECT, owner="pytest")

    rows, total = list_results(SPACE, qa_id="p-latest")
    assert total == 2
    latest = [row for row in rows if row.is_latest]
    assert len(latest) == 1
    assert latest[0].verdict == Verdict.CORRECT.value
