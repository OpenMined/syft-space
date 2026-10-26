"""The counted verdict behind every reported figure, and judge failures.

The counted verdict of an answer is the owner's override, else the primary
judge's freshest verdict, else the next judge's in panel order — the same
``run_view.pick`` the results page counts with. A judge call that failed on a
real answer is neither done nor graded: the ``judge`` command grades it again
without re-asking the model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    Settings,
    SpaceConfig,
    Verdict,
)
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.db.models import Job, RunAggregate
from syft_benchmark.llm import Provider
from syft_benchmark.report import card as card_mod
from syft_benchmark.report import metrics as metrics_mod
from syft_benchmark.report.metrics import judges_seen, summarize
from syft_benchmark.report.slices import judge_agreement
from syft_benchmark.runs import judge_stage
from syft_benchmark.runs.judge import ERROR_PREFIX, Grade
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE, judge_pending
from syft_benchmark.runs.status import PassStatus, SpaceStatus, _state

SPACE = "pytest-counted"
JOB = "pytest-counted-job"
PRIMARY = "judge/primary"
SECOND = "judge/second"
_T0 = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


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
            session.execute(delete(RunAggregate).where(RunAggregate.job_id == JOB))
            session.execute(delete(Job).where(Job.id == JOB))

    wipe()
    yield
    wipe()


def _seed(*, job: str | None) -> None:
    """Four answerable questions, two judges that disagree, one override.

    | question | primary           | second      | override    | counted     |
    | p1       | correct           | hallucinate |             | correct     |
    | p2       | correct           | hallucinate | hallucinate | hallucinate |
    | p3       | —                 | correct     |             | correct     |
    | p4       | correct           | hallucinate |             | correct     |

    The second judge always speaks last: a blend by time would read 1 of 4.
    """
    verdicts: dict[str, dict[str, str]] = {
        PRIMARY: {"p1": "correct", "p2": "correct", "p4": "correct"},
        SECOND: {
            "p1": "hallucinate",
            "p2": "hallucinate",
            "p3": "correct",
            "p4": "hallucinate",
        },
        OWNER_OVERRIDE: {"p2": "hallucinate"},
    }
    with session_scope() as session:
        if job:
            session.add(
                Job(
                    id=job,
                    target=SPACE,
                    state="succeeded",
                    params={"judge_panel": [PRIMARY, SECOND]},
                )
            )
        for qa in ("p1", "p2", "p3", "p4"):
            session.add(
                QaPair(
                    id=f"{SPACE}-{qa}",
                    space=SPACE,
                    generator="cloze",
                    question=f"question {qa}",
                    answer="a",
                    status="active",
                    model="m",
                    question_hash=f"{SPACE}-h-{qa}",
                )
            )
        session.flush()
        for offset, (judge, by_qa) in enumerate(verdicts.items()):
            run_id = f"{SPACE}-run-{offset}"
            session.add(
                Run(
                    id=run_id,
                    space=SPACE,
                    context_mode=ContextMode.OPEN_BOOK.value,
                    block=EvalBlock.DIRECT.value,
                    model="",
                    judge_model=judge,
                    job_id=job,
                )
            )
            session.flush()
            for qa, verdict in by_qa.items():
                session.add(
                    Result(
                        id=f"{SPACE}-{offset}-{qa}",
                        run_id=run_id,
                        qa_id=f"{SPACE}-{qa}",
                        space=SPACE,
                        endpoint="kb",
                        endpoint_response_type="summary",
                        answer="a",
                        verdict=verdict,
                        judge_model=judge,
                        created_at=_T0 + timedelta(minutes=offset),
                    )
                )


def _configured(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = Settings.model_construct(judge_models=[PRIMARY, SECOND])
    monkeypatch.setattr(metrics_mod, "get_settings", lambda: conf)


@needs_db
def test_the_card_counts_the_primary_judge_and_the_override(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(job=JOB)
    _configured(monkeypatch)

    got = card_mod.build(SPACE, "kb", job=JOB)

    assert got is not None and got.answerable is not None
    # p1, p4: primary; p2: the override over both judges; p3: the second
    # judge, the primary having no verdict.
    assert (got.answerable.graded, got.answerable.correct) == (4, 3)
    assert got.answerable.hallucinate == 1
    assert got.score == 0.75
    assert got.answerable.judge == PRIMARY
    assert got.trust.judges == 2
    assert got.instrument is not None and got.instrument.judge == PRIMARY


@needs_db
def test_the_node_as_of_now_counts_the_configured_primary(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(job=None)
    _configured(monkeypatch)

    got = summarize(SPACE, ContextMode.OPEN_BOOK)

    assert got is not None
    assert (got.graded, got.correct, got.hallucinate) == (4, 3, 1)
    assert got.judge == PRIMARY

    # The per-judge view is unchanged: each judge alone, no override.
    second = summarize(SPACE, ContextMode.OPEN_BOOK, judge=SECOND)
    assert second is not None
    assert (second.graded, second.correct) == (4, 1)


@needs_db
def test_the_panel_order_decides_which_judge_is_primary(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(job=None)
    conf = Settings.model_construct(judge_models=[SECOND, PRIMARY])
    monkeypatch.setattr(metrics_mod, "get_settings", lambda: conf)

    got = summarize(SPACE, ContextMode.OPEN_BOOK)

    assert got is not None
    # The second judge leads now; the override still wins on p2.
    assert (got.graded, got.correct, got.hallucinate) == (4, 1, 3)


@needs_db
def test_an_override_is_not_a_judge(clean: None) -> None:
    _seed(job=None)

    seen = judges_seen(SPACE, ContextMode.OPEN_BOOK, EvalBlock.DIRECT)

    assert seen == sorted([PRIMARY, SECOND])
    pairs = judge_agreement(SPACE, ContextMode.OPEN_BOOK, EvalBlock.DIRECT)
    assert [(p.left, p.right) for p in pairs] == [(PRIMARY, SECOND)]
    # Shared: p1, p2, p4 — all three disagree.
    assert (pairs[0].shared, pairs[0].agreed) == (3, 0)


# --- judge failures ---------------------------------------------------------


def test_a_failed_judge_call_is_its_own_state() -> None:
    assert _state("a real answer", Verdict.TECHNICAL.value) == "unjudged"
    assert _state(f"{ERROR_PREFIX} timeout", Verdict.TECHNICAL.value) == "failed"
    assert _state("a real answer", Verdict.PENDING.value) == "pending"
    assert _state("a real answer", Verdict.CORRECT.value) == "graded"


def test_a_failed_judge_call_is_cured_by_judging() -> None:
    entry = PassStatus(
        space="docs",
        context_mode=ContextMode.CLOSED_BOOK,
        context_source="none",
        block=EvalBlock.DIRECT,
        model="vendor/m",
        judge="judge/a",
        total=50,
        graded=45,
        failed=0,
        pending=0,
        last_at=None,
        unjudged=5,
    )
    assert entry.missing == 0
    assert not entry.done
    assert "judge failed 5" in entry.line()
    advice = " ".join(SpaceStatus("docs", 50, "", [entry]).advice())
    assert "syft-benchmark judge docs" in advice
    assert "--resume" not in advice


def _seed_failed_judge() -> None:
    with session_scope() as session:
        session.add(
            QaPair(
                id=f"{SPACE}-f",
                space=SPACE,
                generator="cloze",
                question="q",
                answer="a",
                status="active",
                model="m",
                question_hash=f"{SPACE}-h-f",
            )
        )
        session.add(
            Run(
                id=f"{SPACE}-run-f",
                space=SPACE,
                context_mode="closed_book",
                block="direct",
                model="m",
                judge_model="t",
            )
        )
        session.flush()
        session.add(
            Result(
                id=f"{SPACE}-result-f",
                run_id=f"{SPACE}-run-f",
                qa_id=f"{SPACE}-f",
                space=SPACE,
                answer="a real answer",
                verdict=Verdict.TECHNICAL.value,
                reasoning="the judge did not answer: timeout",
                judge_model="t",
            )
        )


@needs_db
def test_the_judge_stage_grades_a_failed_judge_call_again(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_failed_judge()
    graded: list[str] = []

    def fake_grade(question: str, expected: str, answer: str, **_: Any) -> Grade:
        graded.append(answer)
        return Grade(Verdict.CORRECT, "ok")

    monkeypatch.setattr(judge_stage, "grade", fake_grade)
    seat = Provider(role="judge", url="http://judge.invalid", api_key="k", model="t")
    space = SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="e")

    report = judge_pending(space, judge=seat)

    assert report.checked == 1 and report.correct == 1
    assert graded == ["a real answer"], "the recorded answer, not a new one"
    # Graded now: a second pass finds nothing.
    assert judge_pending(space, judge=seat).checked == 0


@needs_db
def test_the_judge_stage_regrades_its_own_failure_behind_another_verdict(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a panel the next judge writes after the failed one: the freshest
    row is a real verdict, and the failed judge still has none."""
    _seed_failed_judge()
    with session_scope() as session:
        session.add(
            Result(
                id=f"{SPACE}-result-f2",
                run_id=f"{SPACE}-run-f",
                qa_id=f"{SPACE}-f",
                space=SPACE,
                answer="a real answer",
                verdict=Verdict.HALLUCINATE.value,
                judge_model="other",
                created_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
    monkeypatch.setattr(
        judge_stage, "grade", lambda *a, **k: Grade(Verdict.CORRECT, "ok")
    )
    seat = Provider(role="judge", url="http://judge.invalid", api_key="k", model="t")
    space = SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="e")

    assert judge_pending(space, judge=seat).checked == 1
    other = Provider(
        role="judge", url="http://judge.invalid", api_key="k", model="other"
    )
    assert judge_pending(space, judge=other).checked == 0
