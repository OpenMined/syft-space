"""The counted verdict behind every reported figure, and judge failures.

The counted verdict of an answer is the owner's override, else the primary
judge's freshest verdict, else the next judge's in panel order — the same
``counted.pick`` the results page counts with. A judge call that failed on a
real answer is neither done nor graded: the ``judge`` command grades it again
without re-asking the model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    Settings,
    SpaceConfig,
    Verdict,
)
from syft_benchmark.db import QaPair, Result, Run, session_scope
from syft_benchmark.db.models import Job
from syft_benchmark.report import metrics as metrics_mod
from syft_benchmark.report.metrics import judges_seen, summarize
from syft_benchmark.report.slices import judge_agreement
from syft_benchmark.runs import judge as run_judge
from syft_benchmark.runs import status as status_mod
from syft_benchmark.runs.judge import ERROR_PREFIX, Grade
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE, judge_pending
from syft_benchmark.runs.status import PassStatus, SpaceStatus, collect

from fakes import StoreStub

SPACE = "pytest-counted"
JOB = "pytest-counted-job"
PRIMARY = "judge/primary"
SECOND = "judge/second"
_T0 = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


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
                    context_mode=ContextMode.MODEL_WITH_CONTEXT.value,
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


@pytest.mark.needs_db
def test_a_job_summary_counts_the_primary_judge_and_the_override(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(job=JOB)
    _configured(monkeypatch)

    got = summarize(SPACE, ContextMode.MODEL_WITH_CONTEXT, job=JOB)

    assert got is not None
    # p1, p4: primary; p2: the override over both judges; p3: the second
    # judge, the primary having no verdict.
    assert (got.graded, got.correct) == (4, 3)
    assert got.hallucinate == 1
    assert got.judge == PRIMARY


@pytest.mark.needs_db
def test_the_node_as_of_now_counts_the_configured_primary(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(job=None)
    _configured(monkeypatch)

    got = summarize(SPACE, ContextMode.MODEL_WITH_CONTEXT)

    assert got is not None
    assert (got.graded, got.correct, got.hallucinate) == (4, 3, 1)
    assert got.judge == PRIMARY

    # The per-judge view is unchanged: each judge alone, no override.
    second = summarize(SPACE, ContextMode.MODEL_WITH_CONTEXT, judge=SECOND)
    assert second is not None
    assert (second.graded, second.correct) == (4, 1)


@pytest.mark.needs_db
def test_the_panel_order_decides_which_judge_is_primary(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(job=None)
    conf = Settings.model_construct(judge_models=[SECOND, PRIMARY])
    monkeypatch.setattr(metrics_mod, "get_settings", lambda: conf)

    got = summarize(SPACE, ContextMode.MODEL_WITH_CONTEXT)

    assert got is not None
    # The second judge leads now; the override still wins on p2.
    assert (got.graded, got.correct, got.hallucinate) == (4, 1, 3)


@pytest.mark.needs_db
def test_an_override_is_not_a_judge(clean: None) -> None:
    _seed(job=None)

    seen = judges_seen(SPACE, ContextMode.MODEL_WITH_CONTEXT, EvalBlock.DIRECT)

    assert seen == sorted([PRIMARY, SECOND])
    pairs = judge_agreement(SPACE, ContextMode.MODEL_WITH_CONTEXT, EvalBlock.DIRECT)
    assert [(p.left, p.right) for p in pairs] == [(PRIMARY, SECOND)]
    # Shared: p1, p2, p4 — all three disagree.
    assert (pairs[0].shared, pairs[0].agreed) == (3, 0)


@pytest.mark.needs_db
@pytest.mark.parametrize("judge", [None, PRIMARY])
def test_each_model_keeps_its_own_counted_verdict(
    clean: None, monkeypatch: pytest.MonkeyPatch, judge: str | None
) -> None:
    """Without a model named, two models' answers to one question stay two
    answers, each with its own verdict, whether a judge is named or not."""
    _configured(monkeypatch)
    verdicts = {"vendor/a": "correct", "vendor/b": "hallucinate"}
    with session_scope() as session:
        session.add(
            QaPair(
                id=f"{SPACE}-p1",
                space=SPACE,
                generator="cloze",
                question="question p1",
                answer="a",
                status="active",
                model="m",
                question_hash=f"{SPACE}-h-p1",
            )
        )
        session.flush()
        for offset, (model, verdict) in enumerate(verdicts.items()):
            run_id = f"{SPACE}-run-{offset}"
            session.add(
                Run(
                    id=run_id,
                    space=SPACE,
                    context_mode=ContextMode.CLOSED_BOOK.value,
                    block=EvalBlock.DIRECT.value,
                    model=model,
                    judge_model=PRIMARY,
                )
            )
            session.flush()
            session.add(
                Result(
                    id=f"{SPACE}-{offset}-p1",
                    run_id=run_id,
                    qa_id=f"{SPACE}-p1",
                    space=SPACE,
                    answer="a",
                    verdict=verdict,
                    judge_model=PRIMARY,
                    model=model,
                    created_at=_T0 + timedelta(minutes=offset),
                )
            )

    rows = metrics_mod.latest_results(
        SPACE, ContextMode.CLOSED_BOOK, EvalBlock.DIRECT, judge=judge
    )

    assert sorted((r.model, r.verdict) for r in rows) == sorted(verdicts.items())


# --- judge failures ---------------------------------------------------------


def test_a_failed_judge_call_is_its_own_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed judge call is unjudged, a failed answer call failed: four states."""
    run = SimpleNamespace(
        id="r1",
        context_mode="closed_book",
        context_source="none",
        block="direct",
        model="vendor/m",
        judge_model="judge/a",
    )

    def row(qa_id: str, answer: str, verdict: Verdict) -> SimpleNamespace:
        return SimpleNamespace(
            run_id="r1",
            qa_id=qa_id,
            answer=answer,
            verdict=verdict.value,
            created_at=_T0,
        )

    rows = [
        row("q1", "a real answer", Verdict.TECHNICAL),
        row("q2", f"{ERROR_PREFIX} timeout", Verdict.TECHNICAL),
        row("q3", "a real answer", Verdict.PENDING),
        row("q4", "a real answer", Verdict.CORRECT),
    ]

    class _Store(StoreStub):
        def all(self) -> list[Any]:
            return [run] if "FROM runs" in str(self.statements[-1]) else rows

    monkeypatch.setattr(status_mod, "session_scope", _Store())
    (entry,) = collect("docs", total=4).passes

    assert (entry.unjudged, entry.failed, entry.pending, entry.graded) == (1, 1, 1, 1)


def test_a_failed_judge_call_is_cured_by_judging() -> None:
    entry = PassStatus(
        context_mode=ContextMode.CLOSED_BOOK,
        block=EvalBlock.DIRECT,
        model="vendor/m",
        judge="judge/a",
        total=50,
        graded=45,
        failed=0,
        pending=0,
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


@pytest.mark.needs_db
def test_the_judge_stage_grades_a_failed_judge_call_again(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_failed_judge()
    graded: list[str] = []

    def fake_grade(question: str, expected: str, answer: str, **_: Any) -> Grade:
        graded.append(answer)
        return Grade(Verdict.CORRECT, "ok")

    monkeypatch.setattr(run_judge, "grade", fake_grade)
    conf = Settings(judge_model="t")
    space = SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="e")

    report = judge_pending(space, settings=conf)

    assert report.checked == 1 and report.correct == 1
    assert graded == ["a real answer"], "the recorded answer, not a new one"
    # Graded now: a second pass finds nothing.
    assert judge_pending(space, settings=conf).checked == 0


@pytest.mark.needs_db
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
        run_judge, "grade", lambda *a, **k: Grade(Verdict.CORRECT, "ok")
    )
    space = SpaceConfig(key=SPACE, url="http://space.invalid", endpoint="e")

    assert judge_pending(space, settings=Settings(judge_model="t")).checked == 1
    assert judge_pending(space, settings=Settings(judge_model="other")).checked == 0


def test_a_copied_run_must_name_its_job() -> None:
    """A run of further verdicts outside the answer's job would be missing from
    that job's figures, so the job is never left to a default."""
    from syft_benchmark.runs.regrade import copy_run

    source: dict[str, Any] = {
        "endpoint": "kb",
        "context_mode": ContextMode.MODEL_WITH_CONTEXT.value,
        "context_source": "",
        "profile": "",
        "params": {},
        "block": EvalBlock.DIRECT.value,
        "model": "",
        "model_vendor": "",
    }
    with pytest.raises(TypeError, match="job_id"):
        copy_run(source, space=SPACE, judge_model=PRIMARY, note="n")  # type: ignore[call-arg]

    run = copy_run(source, space=SPACE, judge_model=PRIMARY, note="n", job_id=JOB)
    assert run.job_id == JOB


def test_a_copied_run_keeps_every_column_of_the_answer() -> None:
    """How the answer was obtained, down to the build served, carries over;
    only who judges, why and when are the copy's own."""
    from syft_benchmark.runs.regrade import columns, copy_run

    source = Run(
        id="run-src",
        space=SPACE,
        endpoint="kb",
        job_id="job-old",
        context_mode=ContextMode.MODEL_WITH_CONTEXT.value,
        context_source="chunks",
        profile="p",
        params={"retrieval_top_k": 3},
        block=EvalBlock.DIRECT.value,
        model="m",
        model_vendor="v",
        model_sent_as="m-sent",
        model_provider="openrouter",
        model_build="m-2026-01-01",
        judge_model="old-judge",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 2, tzinfo=UTC),
        note="old",
    )
    row = columns(source)

    copied = columns(
        copy_run(row, space=SPACE, judge_model="new-judge", note="n", job_id=JOB)
    )

    fresh = {"id", "job_id", "judge_model", "note", "started_at", "finished_at"}
    assert {k: v for k, v in copied.items() if k not in fresh} == {
        k: v for k, v in row.items() if k not in fresh
    }
    assert copied["id"] != "run-src"
    assert (copied["job_id"], copied["judge_model"], copied["note"]) == (
        JOB,
        "new-judge",
        "n",
    )
    assert copied["started_at"] is None and copied["finished_at"] is None


def test_a_new_verdict_drops_only_the_judge_side_of_the_audit() -> None:
    """The original judge's call is not the new verdict's: carried over, its
    prompt, reply and cost would be shown and counted again."""
    from syft_benchmark.runs.regrade import JUDGE_AUDIT_KEYS, answer_audit

    answer_side = {
        "responder_system": "s",
        "responder_prompt": "p",
        "context": "c",
        "call": {"cost_usd": 0.1},
        "citations": [],
    }
    judge_side = dict.fromkeys(JUDGE_AUDIT_KEYS, "x")

    assert answer_audit(answer_side | judge_side) == answer_side
    assert answer_audit(None) == {}


def test_a_new_verdict_keeps_the_block_outcome_but_not_its_rounds() -> None:
    """The figures count pressure and repeats off the counted row, so their
    outcome stays; the rounds, with their judge calls and cost, stay with the
    result that ran them."""
    from syft_benchmark.runs.regrade import answer_extra

    denial = {"rounds": 3, "flipped": True, "flip_round": 2, "note": "n", "limit": 3}
    repeats = {
        "trials": 4,
        "accuracy": 0.5,
        "consistency": 0.75,
        "by_temperature": {"0.7": 0.5},
        "note": "",
    }
    transcript = {"log": [{"round": 1, "judge_cost_usd": 0.01}], "judge_system": "s"}
    extra = {
        "behavior": "refused",
        "text_metrics": {"bleu": 0.1},
        "denial": denial | transcript,
        "monte_carlo": repeats | transcript,
    }

    assert answer_extra(extra) == {
        "behavior": "refused",
        "text_metrics": {"bleu": 0.1},
        "denial": denial,
        "monte_carlo": repeats,
    }
    assert extra["denial"]["log"], "the source row is left as it was"
    assert answer_extra(None) == {}


def test_a_copied_result_keeps_every_answer_field() -> None:
    """A new verdict on the same answer: only the verdict-side columns change."""
    from syft_benchmark.runs.regrade import columns, copy_result

    source = Result(
        id="r-src",
        run_id="run-src",
        qa_id="q",
        space=SPACE,
        endpoint="kb",
        endpoint_response_type="summary",
        answer="Harbourton",
        verdict=Verdict.HALLUCINATE.value,
        reasoning="old",
        expected_behavior="answer",
        grounded=True,
        grounded_note="note",
        retrieval_hit=True,
        retrieval_rank=2,
        retrieved=[{"id": "c1"}],
        extra={"x": 1},
        audit={"judge_raw": "r"},
        latency_s=3.5,
        model="m",
        served_by="upstream-a",
        judge_model="old-judge",
        judge_served_by="upstream-j",
    )
    row = columns(source)

    copy = copy_result(
        row,
        run_id="run-new",
        verdict=Verdict.CORRECT.value,
        reasoning="new",
        extra={"y": 2},
        audit={},
        judge_model="new-judge",
    )

    replaced = {
        "id",
        "run_id",
        "created_at",
        "verdict",
        "reasoning",
        "extra",
        "audit",
        "judge_model",
        "judge_served_by",
    }
    copied = columns(copy)
    assert {k: v for k, v in copied.items() if k not in replaced} == {
        k: v for k, v in row.items() if k not in replaced
    }
    assert copied["id"] != "r-src" and copied["run_id"] == "run-new"
    assert (copied["verdict"], copied["judge_model"], copied["judge_served_by"]) == (
        Verdict.CORRECT.value,
        "new-judge",
        "",
    )
