"""Judging on its own: listing verdicts and overriding one by hand.

Grading never mutates a `Result` row — a verdict is always inserted, never
updated, and every reader (including `list_results`'s own `is_latest`) picks
the freshest by `created_at`. That is the one invariant worth a real database
for here.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

import syft_benchmark.runs.judge as judge
from syft_benchmark.config import SpaceConfig, Verdict
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.llm import Provider
from syft_benchmark.runs.judge_stage import (
    OWNER_OVERRIDE,
    judge_pending,
    list_results,
    override_verdict,
    withdraw_override,
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
def test_an_override_belongs_to_the_launch_it_overrides(clean: None) -> None:
    """Otherwise the run's own page shows the verdict the owner replaced.

    That page reads one launch — it is a page about one run — so an override
    recorded against no launch is invisible exactly where it was made, and the
    superseded verdict is what the owner is left looking at.
    """
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-launch",
                space=SPACE,
                generator="cloze",
                question="Which launch does an override belong to?",
                answer="the one it overrides",
                status="active",
                model="m",
                question_hash="h-launch",
            )
        )
        session.add(
            Run(
                id="run-launch",
                space=SPACE,
                context_mode="closed_book",
                model="m",
                job_id="job-launch",
            )
        )
        session.add(
            Result(
                id="result-launch",
                run_id="run-launch",
                qa_id="p-launch",
                space=SPACE,
                answer="none at all",
                verdict=Verdict.HALLUCINATE.value,
                judge_model="t",
            )
        )

    new_id = override_verdict("result-launch", Verdict.CORRECT, owner="pytest")
    assert new_id is not None

    rows, _ = list_results(SPACE, job="job-launch")
    stands = [row for row in rows if row.is_latest]
    assert [row.id for row in stands] == [new_id]
    assert stands[0].judge_model == OWNER_OVERRIDE


@needs_db
def test_a_block_row_carries_what_the_block_did(clean: None) -> None:
    """Otherwise it is the direct row printed again, with a stranger verdict.

    Both blocks store the answer they STARTED from, so read as text a pressure
    row and a repeat row are the direct answer a second and a third time. What
    tells them apart — the round the model gave in on, how many repeats agreed —
    is in `Result.extra`, and a reader that does not carry it out shows three
    identical rows of which one says `hallucinate` for no visible reason.
    """
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-blocks",
                space=SPACE,
                generator="qa",
                question="Does a block row say what the block did?",
                answer="it does now",
                status="active",
                model="m",
                question_hash="h-blocks",
            )
        )
        session.add(
            Run(
                id="run-denial",
                space=SPACE,
                context_mode="model_with_context",
                block="denial_loop",
                model="m",
            )
        )
        session.add(
            Result(
                id="result-denial",
                run_id="run-denial",
                qa_id="p-blocks",
                space=SPACE,
                answer="it does now",
                verdict=Verdict.HALLUCINATE.value,
                reasoning="gave in at round 3",
                judge_model="t",
                extra={
                    "denial": {
                        "rounds": 3,
                        "flipped": True,
                        "flip_round": 3,
                        "note": "switched to an abstention",
                    }
                },
            )
        )
        session.add(
            Run(
                id="run-repeats",
                space=SPACE,
                context_mode="model_with_context",
                block="monte_carlo",
                model="m",
            )
        )
        session.add(
            Result(
                id="result-repeats",
                run_id="run-repeats",
                qa_id="p-blocks",
                space=SPACE,
                answer="it does now",
                verdict=Verdict.CORRECT.value,
                judge_model="t",
                extra={
                    "monte_carlo": {
                        "trials": 4,
                        "accuracy": 1.0,
                        "consistency": 0.75,
                        "by_temperature": {"0.0": 1.0, "0.7": 1.0},
                        "note": "",
                    }
                },
            )
        )

    rows = {row.id: row for row in list_results(SPACE)[0]}

    denial = rows["result-denial"].denial
    assert denial is not None
    assert (denial.flipped, denial.flip_round, denial.rounds) == (True, 3, 3)
    assert rows["result-denial"].repeats is None

    repeats = rows["result-repeats"].repeats
    assert repeats is not None
    assert repeats.trials == 4
    assert repeats.consistency == 0.75
    assert repeats.by_temperature == {"0.0": 1.0, "0.7": 1.0}
    assert rows["result-repeats"].denial is None


@needs_db
def test_a_direct_row_has_no_block_outcome(clean: None) -> None:
    """Asking once does nothing beyond asking, and must not claim it did."""
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-direct",
                space=SPACE,
                generator="qa",
                question="And a plain one?",
                answer="nothing to report",
                status="active",
                model="m",
                question_hash="h-direct",
            )
        )
        session.add(
            Run(id="run-direct", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="result-direct",
                run_id="run-direct",
                qa_id="p-direct",
                space=SPACE,
                answer="nothing to report",
                verdict=Verdict.CORRECT.value,
                judge_model="t",
            )
        )

    row = list_results(SPACE)[0][0]
    assert row.denial is None
    assert row.repeats is None


@needs_db
def test_withdrawing_an_override_puts_the_panel_back(clean: None) -> None:
    """A verdict recorded by hand is a statement, not a measurement.

    Withdrawn, it leaves nothing for anyone to read: the graders' own verdicts
    were never touched, so they simply stand again — which is what a misclick
    has to be undoable to.
    """
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-undo",
                space=SPACE,
                generator="qa",
                question="Can a hand-recorded verdict be taken back?",
                answer="yes",
                status="active",
                model="m",
                question_hash="h-undo",
            )
        )
        session.add(
            Run(id="run-undo", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="result-undo",
                run_id="run-undo",
                qa_id="p-undo",
                space=SPACE,
                answer="yes",
                verdict=Verdict.HALLUCINATE.value,
                judge_model="t",
            )
        )

    new_id = override_verdict("result-undo", Verdict.CORRECT, owner="pytest")
    assert new_id is not None
    assert [row.id for row in list_results(SPACE)[0] if row.is_latest] == [new_id]

    assert withdraw_override(new_id) is True

    rows = list_results(SPACE)[0]
    assert [row.id for row in rows] == ["result-undo"], "the override is gone entirely"
    assert rows[0].is_latest, "and the grader's own verdict stands again"
    assert rows[0].verdict == Verdict.HALLUCINATE.value


@needs_db
def test_withdrawing_will_not_touch_a_graders_verdict(clean: None) -> None:
    """The one deletion in the module refuses everything but the owner's own row.

    A measured verdict is a record of what a judge said. Nothing in this
    codebase erases one, and a call that names one is answered exactly as a call
    naming a result that never existed.
    """
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-keep",
                space=SPACE,
                generator="qa",
                question="Is a grader's verdict ours to erase?",
                answer="no",
                status="active",
                model="m",
                question_hash="h-keep",
            )
        )
        session.add(
            Run(id="run-keep", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="result-keep",
                run_id="run-keep",
                qa_id="p-keep",
                space=SPACE,
                answer="no",
                verdict=Verdict.CORRECT.value,
                judge_model="t",
            )
        )

    assert withdraw_override("result-keep") is False
    with session_scope() as session:
        assert session.get(Result, "result-keep") is not None


@needs_db
def test_withdrawing_from_another_target_is_not_found(clean: None) -> None:
    """Same rule as the rest of the module: a token scoped to one target must
    not reach another's rows by guessing an id."""
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-scope",
                space=SPACE,
                generator="qa",
                question="Whose row is this?",
                answer="not yours",
                status="active",
                model="m",
                question_hash="h-scope",
            )
        )
        session.add(
            Run(id="run-scope", space=SPACE, context_mode="closed_book", model="m")
        )
        session.add(
            Result(
                id="result-scope",
                run_id="run-scope",
                qa_id="p-scope",
                space=SPACE,
                answer="not yours",
                verdict=Verdict.HALLUCINATE.value,
                judge_model="t",
            )
        )

    new_id = override_verdict("result-scope", Verdict.CORRECT)
    assert new_id is not None
    assert withdraw_override(new_id, target_key="somebody-else") is False
    with session_scope() as session:
        assert session.get(Result, new_id) is not None


@needs_db
def test_overriding_an_unknown_result_returns_none(clean: None) -> None:
    assert override_verdict("no-such-result", Verdict.CORRECT) is None


@needs_db
def test_judging_a_pending_answer_survives_the_session_closing(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    # A control answer goes to the behaviour judge.
    monkeypatch.setattr(
        judge,
        "chat",
        lambda *a, **k: ('{"behavior": "declined", "reasoning": "r"}', {}),
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
def test_judging_reports_progress_as_it_grades(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    # A control answer goes to the behaviour judge.
    monkeypatch.setattr(
        judge,
        "chat",
        lambda *a, **k: ('{"behavior": "declined", "reasoning": "r"}', {}),
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


@needs_db
def test_a_second_judge_does_not_supersede_the_first(clean: None) -> None:
    """A panel is two opinions on one answer, not one replacing the other.

    Read without the grader in the key, whichever judge finished last looked
    like the verdict and the other looked withdrawn — on a page that offers to
    override "the" verdict, that is an invitation to override the wrong row.
    """
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-panel",
                space=SPACE,
                generator="cloze",
                question="q",
                answer="a",
                status="active",
                model="m",
                question_hash="h-panel",
            )
        )
        session.add(
            Run(id="run-panel", space=SPACE, context_mode="closed_book", model="m")
        )
        for n, judge in enumerate(("judge/a", "judge/b")):
            session.add(
                Result(
                    id=f"result-panel-{n}",
                    run_id="run-panel",
                    qa_id="p-panel",
                    space=SPACE,
                    verdict=Verdict.CORRECT.value,
                    judge_model=judge,
                )
            )

    rows, total = list_results(SPACE, qa_id="p-panel")

    assert total == 2
    assert {row.judge_model for row in rows if row.is_latest} == {"judge/a", "judge/b"}


@needs_db
def test_an_owner_override_stands_over_the_whole_panel(clean: None) -> None:
    """Overriding is the owner saying the panel got it wrong.

    So it is not a third opinion beside the two: every grader's verdict steps
    down, or the page would offer to override a row that no longer decides
    anything.
    """
    with session_scope() as session:
        session.add(
            QaPair(
                id="p-override",
                space=SPACE,
                generator="cloze",
                question="q",
                answer="a",
                status="active",
                model="m",
                question_hash="h-override",
            )
        )
        session.add(
            Run(id="run-override", space=SPACE, context_mode="closed_book", model="m")
        )
        for n, judge in enumerate(("judge/a", "judge/b")):
            session.add(
                Result(
                    id=f"result-override-{n}",
                    run_id="run-override",
                    qa_id="p-override",
                    space=SPACE,
                    verdict=Verdict.HALLUCINATE.value,
                    judge_model=judge,
                )
            )

    override_verdict("result-override-0", Verdict.CORRECT, owner="pytest")

    rows, _ = list_results(SPACE, qa_id="p-override")
    standing = [row for row in rows if row.is_latest]

    assert len(standing) == 1
    assert standing[0].judge_model == OWNER_OVERRIDE
    assert standing[0].verdict == Verdict.CORRECT.value
