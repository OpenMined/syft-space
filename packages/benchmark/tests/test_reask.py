"""Re-asks: what they ask, how they are refused, run, judged and combined,
and the worker lane they run in beside the other jobs."""

from __future__ import annotations

import asyncio
import threading
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_run_view import T0, Seed

import syft_benchmark.runs.blocks as blocks
import syft_benchmark.runs.execute as execute
import syft_benchmark.runs.judge as judge
import syft_benchmark.runs.parallel as parallel
import syft_benchmark.scheduler as scheduler
from syft_benchmark.config import (
    JobKind,
    JobState,
    PairStatus,
    Settings,
    StatusReason,
    get_settings,
)
from syft_benchmark.control import combined, jobs, reask
from syft_benchmark.control.compose import node_settings
from syft_benchmark.db import Job, Result, Run, Target, session_scope, store
from syft_benchmark.llm import cost
from syft_benchmark.report import combined_view, job_params

from support import AUTH, WEB_CHECK_MODEL, add_rows, register_target

KEY = "pytest-reask"
M1 = "vendor/model-one"
J1, J2 = "judge/primary", "judge/second"
A, B = "rk-job-a", "rk-job-b"
JOB, OTHER_JOB = A, B
INSTRUMENT = {
    "subject_models": [M1],
    "judge_models": [J1, J2],
    "filter_model": WEB_CHECK_MODEL,
    "reuse_answers": True,
}
COST = {"by_role": {cost.SUBJECTS: 0.8, cost.JUDGES: 1.6, cost.WRITER: 5.0}}

pytestmark = pytest.mark.needs_db


def _method() -> dict[str, Any]:
    """The snapshot and hash a launch on the target records now."""
    with session_scope() as session:
        row = session.get(Target, KEY)
        assert row is not None
        conf = node_settings(row, store.apply(get_settings()))
    return job_params.fingerprint(conf)


def _seed(client: TestClient, **instrument: Any) -> dict[str, Any]:
    """Two runs of M1 judged by J1 and J2. A: q1 alone (J1 hallucinate, J2
    correct), q1 with; q2 alone, retired since. B: q3 alone and with."""
    register_target(client, KEY, instrument={**INSTRUMENT, **instrument})
    method = _method()
    params = {**method, "judge_panel": [J1, J2], "cost": COST}
    a = Seed(A, space=KEY)
    a.pair("rk-q1")
    a.pair(
        "rk-q2",
        status=PairStatus.RETIRED.value,
        status_reason=StatusReason.CONTROL_SHARE.value,
    )
    a.answer("rk-q1", M1, "alone", "hallucinate", judge=J1)
    a.answer("rk-q1", M1, "alone", "correct", judge=J2)
    a.answer("rk-q1", M1, "with", "correct", judge=J1)
    a.answer("rk-q1", M1, "with", "correct", judge=J2)
    a.answer("rk-q2", M1, "alone", "correct", judge=J1)
    a.answer("rk-q2", M1, "alone", "correct", judge=J2)
    a.save(params=params, started_at=T0)
    b = Seed(B, space=KEY)
    b.clock = T0 + timedelta(hours=1)
    b.pair("rk-q3")
    b.answer("rk-q3", M1, "alone", "correct", judge=J1)
    b.answer("rk-q3", M1, "alone", "correct", judge=J2)
    b.answer("rk-q3", M1, "with", "abstain", judge=J1)
    b.answer("rk-q3", M1, "with", "abstain", judge=J2)
    b.save(params=params, created_at=T0 + timedelta(hours=1))
    return method


def _launch(client: TestClient, **body: Any) -> Any:
    return client.post(
        f"/targets/{KEY}/reasks", json={"jobs": [A, B], **body}, headers=AUTH
    )


def _reask_ids() -> list[str]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(Job.id).where(Job.target == KEY, Job.kind == JobKind.REASK.value)
            )
        )


# --- what is asked -----------------------------------------------------------


def test_a_reask_asks_exactly_what_the_runs_asked(
    client: TestClient, clean: Any
) -> None:
    _seed(client)

    made = _launch(client, label="4h")

    assert made.status_code == 202, made.text
    view = made.json()
    assert view["kind"] == "reask"
    assert view["state"] == "queued"
    assert view["reask"]["jobs"] == [A, B]
    assert view["reask"]["label"] == "4h"
    # The retired q2 is asked again: it was asked.
    assert view["reask"]["questions"] == 3
    assert view["reask"]["answers_planned"] == 5
    with session_scope() as session:
        found = reask.plan(session, KEY, [A, B], reask.Scope())
    assert found.passes == {
        ("closed_book", "direct", M1): frozenset({"rk-q1", "rk-q2", "rk-q3"}),
        ("model_with_context", "direct", M1): frozenset({"rk-q1", "rk-q3"}),
    }


def test_a_combined_run_stands_for_its_runs(client: TestClient, clean: Any) -> None:
    _seed(client)
    with session_scope() as session:
        made = combined.create(session, KEY, [A, B])
        combined_id = made.id
    try:
        got = client.post(
            f"/targets/{KEY}/reasks", json={"jobs": [combined_id]}, headers=AUTH
        )
        assert got.status_code == 202, got.text
        assert got.json()["reask"]["jobs"] == [A, B]
    finally:
        with session_scope() as session:
            job = session.get(Job, combined_id)
            if job is not None:
                jobs.discard_run(session, job)


def test_arms_and_models_narrow_the_reask(client: TestClient, clean: Any) -> None:
    _seed(client)

    made = _launch(client, arms=["closed_book"], models=[M1])

    assert made.status_code == 202, made.text
    assert made.json()["reask"]["answers_planned"] == 3
    assert made.json()["reask"]["arms"] == ["closed_book"]


def test_a_dry_run_estimates_from_the_runs_spend_and_queues_nothing(
    client: TestClient, clean: Any
) -> None:
    _seed(client)

    every = _launch(client, dry_run=True)
    primary = _launch(client, dry_run=True, judges="primary")

    assert every.status_code == 200, every.text
    # Each run spent $0.8 on the tested model and $1.6 on judges, $1.6 and
    # $3.2 over 5 answers and 10 verdicts: per answer $0.32 + $0.64; per
    # verdict $0.32.
    assert every.json() == {
        "questions": 3,
        "answers_planned": 5,
        "estimated_usd": pytest.approx(4.8),
        "max_job_usd": 100.0,
    }
    assert primary.json()["estimated_usd"] == pytest.approx(3.2)
    assert _reask_ids() == []


# --- refusals ----------------------------------------------------------------


def _refused(made: Any, words: str) -> dict[str, Any]:
    assert made.status_code == 422, made.text
    body: dict[str, Any] = made.json()
    assert words in body["detail"]
    return body


def test_unknown_or_unfit_runs_are_a_422(client: TestClient, clean: Any) -> None:
    _seed(client)
    add_rows(Job(id="rk-judge", target=KEY, state="succeeded", kind="judge"))
    try:
        _refused(
            client.post(
                f"/targets/{KEY}/reasks", json={"jobs": ["nope"]}, headers=AUTH
            ),
            "not a run of target",
        )
        _refused(
            client.post(
                f"/targets/{KEY}/reasks", json={"jobs": [A, "rk-judge"]}, headers=AUTH
            ),
            "only measurement runs",
        )
        _refused(
            _launch(client, models=["other/model"]), "asked nothing of other/model"
        )
        assert _launch(client, label="x" * 65).status_code == 422
    finally:
        with session_scope() as session:
            session.execute(Job.__table__.delete().where(Job.id == "rk-judge"))


def test_runs_measured_differently_are_a_422_with_the_differences(
    client: TestClient, clean: Any
) -> None:
    _seed(client)
    with session_scope() as session:
        job = session.get(Job, B)
        assert job is not None
        snapshot = dict(job.params[job_params.SETTINGS_SNAPSHOT])
        snapshot["similarity_threshold"] = 0.99
        job.params = {
            **job.params,
            job_params.SETTINGS_SNAPSHOT: snapshot,
            job_params.SETTINGS_HASH: job_params.settings_hash(snapshot),
        }

    body = _refused(_launch(client), "measured the same way")

    assert [d["field"] for d in body["differences"]] == ["similarity_threshold"]


def test_a_run_without_a_snapshot_or_still_running_is_a_422(
    client: TestClient, clean: Any
) -> None:
    _seed(client)
    with session_scope() as session:
        job = session.get(Job, B)
        assert job is not None
        job.state = JobState.RUNNING.value
    _refused(_launch(client), "finished")
    with session_scope() as session:
        job = session.get(Job, B)
        assert job is not None
        job.params = {"judge_panel": [J1, J2]}
    _refused(_launch(client), "no settings snapshot")


def test_an_estimate_over_the_cap_is_a_422(client: TestClient, clean: Any) -> None:
    _seed(client, max_job_usd=2.0)

    _refused(_launch(client), "over the job cap")
    assert _launch(client, judges="primary", arms=["closed_book"]).status_code == 202


# --- the sources' methodology ------------------------------------------------


def test_the_reask_measures_by_the_runs_settings_not_the_targets(
    client: TestClient, clean: Any
) -> None:
    method = _seed(client)
    register_target(
        client, KEY, instrument={**INSTRUMENT, "judge_models": [J2], "max_job_usd": 7.0}
    )
    with session_scope() as session:
        found = reask.plan(session, KEY, [A, B], reask.Scope())
        row = session.get(Target, KEY)
        assert row is not None
        node = node_settings(row, store.apply(get_settings()))

    conf, snapshot = reask.settings_of(node, found)

    assert conf.judge_models == [J1, J2]
    assert conf.resume is False
    # Outside the hash, the target's own values.
    assert conf.max_job_usd == 7.0
    assert job_params.settings_hash(snapshot) == method[job_params.SETTINGS_HASH]


def test_a_setting_added_since_must_hold_its_default() -> None:
    base = Settings(subject_models=[M1], judge_models=[J1])
    method = job_params.fingerprint(base)
    snapshot = dict(method[job_params.SETTINGS_SNAPSHOT])
    snapshot.pop("similarity_threshold")
    found = reask.Plan(
        sources=["x"],
        snapshot=snapshot,
        settings_hash=job_params.settings_hash(snapshot),
        scope=reask.Scope(),
        passes={("closed_book", "direct", M1): frozenset({"q"})},
        estimated_usd=None,
    )

    _, kept = reask.settings_of(base, found)
    assert "similarity_threshold" not in kept
    changed = base.model_copy(update={"similarity_threshold": 0.77})
    with pytest.raises(reask.Refused) as refused:
        reask.settings_of(changed, found)
    assert refused.value.differences == [
        {"field": "similarity_threshold", "runs": None, "reask": 0.77}
    ]


# --- the lane ----------------------------------------------------------------


def test_one_reask_per_target_beside_a_pipeline_job(
    client: TestClient, clean: Any
) -> None:
    _seed(client)
    first = _launch(client)
    assert first.status_code == 202

    second = _launch(client)
    scoped = client.post(
        f"/targets/{KEY}/runs", json={"documents": ["/a.md"]}, headers=AUTH
    )
    third = _launch(client)

    assert second.status_code == 409
    assert second.json()["active_job_id"] == first.json()["id"]
    assert "re-ask" in second.json()["detail"]
    # The pipeline lane is free: a document launch queues beside the re-ask,
    # and the re-ask lane is still the re-ask's.
    assert scoped.status_code == 202, scoped.text
    assert scoped.json()["kind"] == "pipeline"
    assert third.status_code == 409


def test_the_worker_runs_one_job_per_lane(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(client)
    assert client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH).status_code == 202
    reasked = _launch(client).json()["id"]
    release = threading.Event()
    ran: list[str] = []

    def held(job_id: str, settings: Any = None) -> None:
        ran.append(job_id)
        release.wait(5)

    monkeypatch.setattr(jobs, "execute", held)
    worker = jobs.Worker()
    try:
        # Other modules' queued jobs may stand first in the main lane.
        started = worker.dispatch()
        assert reasked in started
        assert len(started) == 2
        assert worker.dispatch() == []
    finally:
        release.set()
    assert jobs.lane_of(JobKind.REASK.value) == "reask"
    assert jobs.lane_of(JobKind.FILTER.value) == "main"


def test_reasks_are_left_out_of_combining_per_period(
    client: TestClient, clean: Any
) -> None:
    _seed(client)
    reasked = _launch(client).json()["id"]
    with session_scope() as session:
        job = session.get(Job, reasked)
        assert job is not None
        job.state = JobState.SUCCEEDED.value
        job.created_at = T0 + timedelta(hours=2)
        session.add(
            Run(
                id="rk-reask-run",
                space=KEY,
                job_id=reasked,
                context_mode="closed_book",
                block="direct",
                model=M1,
                judge_model=J1,
                params={},
            )
        )
        target = session.get(Target, KEY)
        assert target is not None
        target.combine_periods = ["24h"]
        made = combined.combine_due(session, target, now=T0 + timedelta(days=1))
        members = combined_view.member_ids(session, made[0])
        for job_id in made:
            found = session.get(Job, job_id)
            assert found is not None
            jobs.discard_run(session, found)

    assert members == [A, B]


# --- running it --------------------------------------------------------------


class _Stand:
    """Every model call answered here and counted, the node substituted."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []
        stand = self

        def chat(system: str, user: str, **kwargs: Any) -> Any:
            provider = kwargs["provider"]
            with stand.lock:
                stand.calls.append((provider.model, provider.role))
            if provider.role == "judge":
                return '{"correct": true, "grounded": true, "reasoning": "ok"}', {}
            return "Answer.", {"finish_reason": "stop", "latency_s": 0.01}

        def endpoint(space: Any, question: str, **kwargs: Any) -> Any:
            return {
                "answer": "Answer.",
                "documents": [
                    {
                        "content": "The answer.",
                        "metadata": {"doc_id": "doc-1", "file_name": "a.md"},
                        "similarity_score": 0.8,
                    }
                ],
                "latency": 0.0,
                "failed": False,
            }

        for module in (parallel, execute, judge, blocks):
            monkeypatch.setattr(module, "chat", chat)
        monkeypatch.setattr(parallel, "ask_endpoint", endpoint)
        monkeypatch.setattr(execute, "endpoint_mode", lambda space: "both")
        monkeypatch.setattr(scheduler, "check_perimeter", lambda conf: None)
        monkeypatch.setattr(jobs, "openrouter_spend", lambda conf: None)

    def asked(self, role: str) -> int:
        return sum(1 for _, r in self.calls if r == role)


def _run(client: TestClient, **body: Any) -> str:
    made = _launch(client, **body)
    assert made.status_code == 202, made.text
    job_id: str = made.json()["id"]
    jobs.execute(job_id)
    return job_id


def _verdicts(job_id: str) -> list[tuple[str, str, str, str]]:
    with session_scope() as session:
        return sorted(
            session.execute(
                select(
                    Run.context_mode, Result.qa_id, Result.judge_model, Result.answer
                )
                .join(Result, Result.run_id == Run.id)
                .where(Run.job_id == job_id)
            ).all()
        )


def test_a_reask_records_fresh_answers_under_the_runs_hash(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    method = _seed(client)
    stand = _Stand(monkeypatch)

    job_id = _run(client, label="1h")

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.state == JobState.SUCCEEDED.value, job.error
        params = dict(job.params)
    assert params[job_params.SETTINGS_HASH] == method[job_params.SETTINGS_HASH]
    assert params[job_params.JUDGE_PANEL] == [J1, J2]
    spent = params[job_params.COST]["by_role"]
    assert spent[cost.WRITER] == spent[cost.WEB_CHECK] == 0
    # reuse_answers is on, yet every answer is asked and recorded afresh.
    assert stand.asked("subject") == 5
    found = _verdicts(job_id)
    assert len(found) == 10
    assert {answer for *_, answer in found} == {"Answer."}
    # Runs already answered do not make the re-ask "already done".
    again = _run(client)
    assert len(_verdicts(again)) == 10


def test_a_primary_only_reask_combines_and_repeats_compare_primary_verdicts(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(client)
    _Stand(monkeypatch)

    job_id = _run(client, judges="primary")

    assert {judge_model for _, _, judge_model, _ in _verdicts(job_id)} == {J1}
    with session_scope() as session:
        made = combined.create(session, KEY, [job_id, A, B])
        combined_id = made.id
    try:
        with session_scope() as session:
            job = session.get(Job, combined_id)
            assert job is not None
            payload = combined_view.compute(session, job)
        members = payload["members"]
        assert [m["job_id"] for m in members] == [A, B, job_id]
        assert [m["kind"] for m in members] == ["pipeline", "pipeline", "reask"]
        assert members[2]["label"] is None
        alone = payload["repeats"]["models"][0]["alone"]
        # q1 alone: J1 said hallucinate, the re-ask's J1 correct; q2 and q3
        # correct both times.
        assert payload["repeats"]["questions"] == 3
        assert alone["wrong_to_right"] == 1
        assert alone["right_to_wrong"] == 0
        with_ = payload["repeats"]["models"][0]["with"]
        assert with_["wrong_to_right"] == 1  # q3 abstain -> correct
    finally:
        with session_scope() as session:
            job = session.get(Job, combined_id)
            if job is not None:
                jobs.discard_run(session, job)


def test_a_capped_reask_ends_cancelled_with_its_answers_kept(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(client)
    _Stand(monkeypatch)
    made = _launch(client)
    job_id = made.json()["id"]
    with session_scope() as session:
        target = session.get(Target, KEY)
        assert target is not None
        target.instrument = {**INSTRUMENT, "max_job_usd": 0.5}

    class _Spent:
        total_usd = 1.0

    monkeypatch.setattr(jobs, "meter_for", lambda job: _Spent())
    jobs.execute(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.state == JobState.CANCELLED.value
        assert job.error.startswith(jobs.OVER_BUDGET)


def test_a_reask_whose_runs_are_gone_fails_with_a_reason(
    client: TestClient, clean: Any
) -> None:
    _seed(client)
    job_id = _launch(client).json()["id"]
    with session_scope() as session:
        job = session.get(Job, B)
        assert job is not None
        jobs.discard_run(session, job)

    jobs.execute(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.state == JobState.FAILED.value
        assert job.error.startswith(jobs.REASK_REFUSED)


# --- the cost meter beside another job ---------------------------------------


def test_pass_workers_charge_their_own_jobs_meter() -> None:
    conf = Settings(concurrency=2, endpoint_concurrency=1)
    totals: dict[str, float] = {}
    started = threading.Barrier(2)

    def job(name: str, usd: float) -> None:
        with cost.cost_meter(job_id=name) as meter:
            started.wait()

            async def go() -> None:
                pool = parallel.Pool(conf)
                try:
                    for _ in range(3):
                        await pool.to_model(cost.charge, usd, cost.SUBJECTS)
                finally:
                    pool.close()

            asyncio.run(go())
            totals[name] = meter.total_usd

    threads = [
        threading.Thread(target=job, args=("one", 1.0)),
        threading.Thread(target=job, args=("two", 10.0)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert totals == {"one": pytest.approx(3.0), "two": pytest.approx(30.0)}
