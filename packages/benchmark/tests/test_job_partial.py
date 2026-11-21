"""A job that reached the end with failures recorded ends ``partial``, and
says per model which passes failed (control API, "Jobs")."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    JobPhase,
    JobState,
    Settings,
    SpaceConfig,
)
from syft_benchmark.control import jobs
from syft_benchmark.control.schemas import JobView
from syft_benchmark.db import Job, QaPair, Result, Run, session_scope
from syft_benchmark.llm import Provider
from syft_benchmark.report import job_params
from syft_benchmark.runs.execute import RunReport
from syft_benchmark.runs.parallel import OWNER_STOP
from syft_benchmark.scheduler import Measured, PassProblem, measure

SPACE = SpaceConfig(key="pytest-partial-space", url="http://localhost:0", endpoint="kb")
KEY = SPACE.key
JOB = "pytest-partial-job"
OPENROUTER = "https://openrouter.ai/api/v1"
BROKEN = "vendor/broken"  # its with-context pass raises
STREAK = "vendor/streak"  # its with-context pass stops on a failure streak
OWNED = "vendor/owned"  # its with-context pass the owner stopped
FINE = "vendor/fine"


def _providers(*models: str) -> list[Provider]:
    return [
        Provider(role="subject", url=OPENROUTER, api_key="k", model=m) for m in models
    ]


def _measure(monkeypatch: pytest.MonkeyPatch) -> Measured:
    monkeypatch.setattr(
        "syft_benchmark.scheduler.subject_providers",
        lambda conf: _providers(BROKEN, STREAK, OWNED, FINE),
    )
    monkeypatch.setattr(
        "syft_benchmark.scheduler.judge_providers", lambda conf: _providers("j")
    )
    monkeypatch.setattr("syft_benchmark.scheduler.check_perimeter", lambda conf: None)
    monkeypatch.setattr(
        "syft_benchmark.scheduler.evaluation_gate", lambda key, conf, **_: ""
    )
    monkeypatch.setattr("syft_benchmark.scheduler.summarize", lambda *a: None)

    async def fake_run_pass(space: Any, mode: Any, **kwargs: Any) -> list[RunReport]:
        model = kwargs["subject"].model
        stopped = ""
        if mode is ContextMode.MODEL_WITH_CONTEXT:
            if model == BROKEN:
                raise RuntimeError("UntranslatableCharacter: \\u0000")
            stopped = {STREAK: "5 questions in a row failed", OWNED: OWNER_STOP}.get(
                model, ""
            )
        report = RunReport(
            run_id="r", context_mode=mode, model=model, judge="j", asked=3
        )
        report.correct = 3
        report.stopped = stopped
        return [report]

    monkeypatch.setattr("syft_benchmark.scheduler.arun_pass", fake_run_pass)
    conf = Settings(
        arms=[ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT],
        blocks=[EvalBlock.DIRECT],
        generate_in_cycle=False,
    )
    return measure(SPACE, conf, evaluate=True)


def test_a_failed_or_stopped_pass_is_flagged_per_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "syft_benchmark.scheduler._active_pairs", lambda *a, **k: [object()] * 3
    )
    done = _measure(monkeypatch)

    flagged = {(p.model, p.arm, p.block): p.reason for p in done.pass_problems}
    assert flagged == {
        (BROKEN, "model_with_context", "direct"): "UntranslatableCharacter: \\u0000",
        (STREAK, "model_with_context", "direct"): "5 questions in a row failed",
    }
    # The owner's stop is the job's cancellation, not a failed pass.
    assert all(p.model != OWNED for p in done.pass_problems)
    assert all(p.expected is None for p in done.pass_problems)


def test_a_reask_pass_knows_how_many_questions_it_was_to_ask() -> None:
    from syft_benchmark.scheduler import PassSpec

    spec = PassSpec(
        ContextMode.CLOSED_BOOK,
        EvalBlock.DIRECT,
        _providers(FINE)[0],
        qa_ids=frozenset({"a", "b"}),
    )
    problem = PassProblem.of(spec, "  the node\nwent away ")
    assert problem.expected == 2
    assert problem.reason == "the node went away"


def test_partial_is_a_final_state() -> None:
    assert JobState.PARTIAL.final
    assert JobState.PARTIAL.value not in job_params.ACTIVE_STATES
    assert len(JobState.PARTIAL.value) <= 20  # jobs.state is String(20)


class _Reporter:
    def __init__(self, *, cancelled: bool = False) -> None:
        self.cancelled = cancelled


@pytest.mark.parametrize(
    ("cancelled", "failed", "state"),
    [
        (False, False, JobState.SUCCEEDED),
        (False, True, JobState.PARTIAL),
        (True, True, JobState.CANCELLED),
        (True, False, JobState.CANCELLED),
    ],
)
def test_the_end_state(cancelled: bool, failed: bool, state: JobState) -> None:
    reporter: Any = _Reporter(cancelled=cancelled)
    assert jobs._end_state(reporter, failed=failed) is state


def test_the_job_view_carries_the_failed_passes() -> None:
    problem = {"model": BROKEN, "arm": "model_with_context", "block": "direct"}
    job = Job(
        id="j",
        target="t",
        state=JobState.PARTIAL.value,
        phase="done",
        kind="pipeline",
        done=2,
        total=2,
        arm="",
        block="",
        model="",
        step_done=0,
        step_total=0,
        message="",
        trigger="manual",
        error="",
        created_at=datetime.now(UTC),
        params={job_params.PASS_PROBLEMS: [problem]},
    )
    assert JobView.model_validate(job).pass_problems == [problem]
    job.params = {}
    assert JobView.model_validate(job).pass_problems == []


# --- against the database --------------------------------------------------


def _job(state: str = JobState.RUNNING.value) -> None:
    with session_scope() as session:
        session.add(Job(id=JOB, target=KEY, state=state, phase=JobPhase.EVALUATE.value))


def _answers(model: str, arm: str, count: int) -> None:
    """``count`` answers of ``model`` in ``arm``, recorded by the job."""
    with session_scope() as session:
        run_id = f"run-{JOB}-{model}-{arm}"
        session.add(
            Run(id=run_id, space=KEY, job_id=JOB, context_mode=arm, model=model)
        )
        for i in range(count):
            pair_id = f"pytest-partial-{model}-{arm}-{i}"
            session.add(
                QaPair(
                    id=pair_id,
                    space=KEY,
                    generator="qa",
                    question=f"q{i}",
                    answer="a",
                    status="active",
                    model="m",
                    question_hash=pair_id,
                )
            )
            session.flush()
            session.add(
                Result(
                    id=f"result-{pair_id}",
                    run_id=run_id,
                    qa_id=pair_id,
                    space=KEY,
                    verdict="correct",
                )
            )


def _conclude(done: Measured, *, per_pass: int | None = 5) -> Job:
    reporter = jobs.Reporter(JOB, Settings())
    reporter._per_pass = per_pass
    jobs._conclude(JOB, reporter, done, evaluated=True)
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        session.expunge(job)
        return job


@pytest.mark.needs_db
def test_a_stopped_pass_ends_the_job_partial_with_its_counts(clean: Any) -> None:
    _job()
    _answers(BROKEN, "model_with_context", 2)
    done = Measured(asked=5, graded=5)
    done.pass_problems.append(
        PassProblem(
            arm="model_with_context",
            block="direct",
            model=BROKEN,
            reason="UntranslatableCharacter",
        )
    )

    job = _conclude(done)

    assert job.state == JobState.PARTIAL.value
    # The streak stopped the pass, nothing went into `error`: the flag alone
    # makes the job partial.
    assert job.error == ""
    assert job_params.pass_problems_of(job) == [
        {
            "model": BROKEN,
            "arm": "model_with_context",
            "block": "direct",
            "reason": "UntranslatableCharacter",
            "expected": 5,
            "recorded": 2,
        }
    ]


@pytest.mark.needs_db
def test_a_job_with_an_error_code_ends_partial(clean: Any) -> None:
    _job()
    job = _conclude(Measured(asked=4, graded=0, failure_sample="no key"))
    assert job.state == JobState.PARTIAL.value
    assert job.error.startswith(jobs.NOTHING_GRADED)
    assert job_params.pass_problems_of(job) == []


@pytest.mark.needs_db
def test_a_clean_job_succeeds_and_notes_do_not_count(clean: Any) -> None:
    _job()
    job = _conclude(Measured(asked=4, graded=4, notes=["a skipped block"]))
    assert job.state == JobState.SUCCEEDED.value
    assert job.error == ""
    assert job.message == "a skipped block"


@pytest.mark.needs_db
def test_a_cancelled_job_stays_cancelled_with_its_failed_passes(clean: Any) -> None:
    _job()
    done = Measured(asked=4, graded=4)
    done.pass_problems.append(
        PassProblem(arm="closed_book", block="direct", model=FINE, reason="boom")
    )
    reporter = jobs.Reporter(JOB, Settings())
    reporter.cancelled = True
    jobs._conclude(JOB, reporter, done, evaluated=True)
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        assert job.state == JobState.CANCELLED.value
        assert job_params.pass_problems_of(job)[0]["expected"] is None


@pytest.mark.needs_db
def test_a_partial_run_is_listed_and_reported(clean: Any) -> None:
    """Its results stay usable: the runs list and the report show it."""
    from fastapi.testclient import TestClient

    from support import console_auth, control_client

    _job()
    _answers(BROKEN, "closed_book", 1)
    done = Measured(asked=1, graded=1)
    done.pass_problems.append(
        PassProblem(arm="model_with_context", block="direct", model=BROKEN, reason="x")
    )
    _conclude(done)

    client: TestClient = control_client()
    session = console_auth(client, KEY)
    listed = client.get("/console/report/runs", headers=session)
    assert listed.status_code == 200, listed.text
    [item] = [i for i in listed.json()["items"] if i["job_id"] == JOB]
    assert item["state"] == JobState.PARTIAL.value
    assert [p["model"] for p in item["pass_problems"]] == [BROKEN]
    report = client.get(f"/console/report/runs/{JOB}", headers=session)
    assert report.status_code == 200, report.text
    assert report.json()["run"]["pass_problems"][0]["reason"] == "x"
