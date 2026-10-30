"""The data under the results pages: the deletion guard, status reasons and the
run aggregate cache."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import syft_benchmark.runs.judge as judge
from syft_benchmark.config import (
    JobState,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    Verdict,
)
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.db import (
    Job,
    QaPair,
    Result,
    Run,
    RunAggregate,
    session_scope,
)
from syft_benchmark.db.pair_guard import delete_pairs
from syft_benchmark.generation.filter_stage import filter_pending, override_status
from syft_benchmark.runs.judge_stage import (
    judge_pending,
    override_verdict,
    withdraw_override,
)

from support import console_auth

KEY = "pytest-results-a"


def _pair(
    pair_id: str,
    *,
    space: str = KEY,
    status: str = PairStatus.ACTIVE.value,
    **extra: Any,
) -> QaPair:
    return QaPair(
        id=pair_id,
        space=space,
        generator=extra.pop("generator", "qa"),
        question="What port does the benchmark database listen on?",
        answer=extra.pop("answer", "5442"),
        context=extra.pop("context", "The benchmark database listens on 5442."),
        status=status,
        model="m",
        question_hash=pair_id,
        **extra,
    )


def _job(job_id: str, *, target: str = KEY) -> Job:
    return Job(id=job_id, target=target, state=JobState.SUCCEEDED.value)


def _answered(
    pair_id: str, job_id: str | None, *, space: str = KEY, verdict: str = "correct"
) -> list[Any]:
    """A run of the job and one result for the pair under it."""
    run_id = f"run-{pair_id}-{job_id}"
    return [
        Run(
            id=run_id,
            space=space,
            job_id=job_id,
            context_mode="closed_book",
            block="direct",
            model="m",
        ),
        Result(
            id=f"result-{pair_id}-{job_id}",
            run_id=run_id,
            qa_id=pair_id,
            space=space,
            answer="I don't know",
            verdict=verdict,
            judge_model="t",
        ),
    ]


def _cache(*job_ids: str) -> None:
    with session_scope() as session:
        for job_id in job_ids:
            session.add(RunAggregate(job_id=job_id, version=1, payload={"x": 1}))


def _cached(job_id: str) -> bool:
    with session_scope() as session:
        return session.get(RunAggregate, job_id) is not None


# --- the deletion guard ------------------------------------------------------


@pytest.mark.needs_db
def test_the_guard_deletes_only_pairs_that_never_took_part(clean: None) -> None:
    with session_scope() as session:
        session.add(_job("job-guard"))
        session.add_all([_pair("p-free"), _pair("p-measured")])
        session.flush()
        session.add_all(_answered("p-measured", "job-guard"))

    with session_scope() as session:
        outcome = delete_pairs(session, ["p-free", "p-measured", "p-missing"])

    assert outcome.deleted == ["p-free"]
    assert outcome.kept == ["p-measured"]
    with session_scope() as session:
        assert session.get(QaPair, "p-free") is None
        assert session.get(QaPair, "p-measured") is not None


@pytest.mark.needs_db
def test_the_console_delete_refuses_a_pair_that_took_part(
    client: TestClient, clean: Any
) -> None:
    session_a = console_auth(client, KEY)
    with session_scope() as session:
        session.add(_job("job-del"))
        session.add(_pair("p-del"))
        session.flush()
        session.add_all(_answered("p-del", "job-del"))

    assert client.delete("/console/pairs/p-del", headers=session_a).status_code == 409


# --- status reasons ----------------------------------------------------------


@pytest.mark.needs_db
def test_an_owner_status_change_records_owner_and_clears_on_return(
    client: TestClient, clean: Any
) -> None:
    session_a = console_auth(client, KEY)
    with session_scope() as session:
        session.add(_pair("p-owner"))

    rejected = client.patch(
        "/console/pairs/p-owner", json={"status": "rejected"}, headers=session_a
    )
    assert rejected.status_code == 200
    assert rejected.json()["status_reason"] == StatusReason.OWNER.value

    back = client.patch(
        "/console/pairs/p-owner", json={"status": "active"}, headers=session_a
    )
    assert back.json()["status_reason"] is None


@pytest.mark.needs_db
def test_screening_records_grounding_and_the_gate(clean: None) -> None:
    with session_scope() as session:
        session.add(
            _pair(
                "p-ungrounded",
                status=PairStatus.PENDING.value,
                answer="Nineteen elephants",
                context="Nothing about animals here.",
            )
        )
        session.add(
            _pair(
                "p-grounded",
                status=PairStatus.PENDING.value,
                answer="5442",
                context="The database listens on 5442.",
            )
        )
        session.add(
            _pair(
                "p-control",
                status=PairStatus.PENDING.value,
                generator="unanswerable_property",
            )
        )

    filter_pending(
        SpaceConfig(key=KEY, url="http://space.invalid", endpoint="e"), retrieve=None
    )

    with session_scope() as session:
        reasons = {
            row.id: (row.status, row.status_reason)
            for row in session.query(QaPair).where(QaPair.space == KEY)
        }
    assert reasons["p-ungrounded"] == ("rejected", StatusReason.GROUNDING.value)
    assert reasons["p-grounded"] == ("active", None)
    assert reasons["p-control"] == ("rejected", StatusReason.RETRIEVAL_GATE.value)


@pytest.mark.needs_db
def test_the_pair_list_filters_by_status(client: TestClient, clean: Any) -> None:
    session_a = console_auth(client, KEY)
    with session_scope() as session:
        session.add(_pair("p-on"))
        session.add(_pair("p-off", status=PairStatus.REJECTED.value))

    listed = client.get("/console/pairs?status=rejected", headers=session_a)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["items"]] == ["p-off"]


# --- the aggregate cache -----------------------------------------------------


@pytest.mark.needs_db
def test_overrides_drop_the_cached_aggregate(clean: None) -> None:
    with session_scope() as session:
        session.add(_job("job-ovr"))
        session.add(_pair("p-ovr"))
        session.flush()
        session.add_all(_answered("p-ovr", "job-ovr", verdict="hallucinate"))
    _cache("job-ovr")

    new_id = override_verdict("result-p-ovr-job-ovr", Verdict.CORRECT)
    assert new_id is not None
    assert not _cached("job-ovr")

    _cache("job-ovr")
    assert withdraw_override(new_id)
    assert not _cached("job-ovr")


@pytest.mark.needs_db
def test_a_status_change_drops_the_aggregate_of_every_job_it_took_part_in(
    clean: None,
) -> None:
    with session_scope() as session:
        session.add_all([_job("job-s1"), _job("job-s2"), _job("job-s3")])
        session.add_all([_pair("p-s"), _pair("p-other")])
        session.flush()
        session.add_all(_answered("p-s", "job-s1"))
        session.add_all(_answered("p-s", "job-s2"))
        session.add_all(_answered("p-other", "job-s3"))
    _cache("job-s1", "job-s2", "job-s3")

    assert override_status("p-s", PairStatus.RETIRED)

    assert not _cached("job-s1")
    assert not _cached("job-s2")
    assert _cached("job-s3")


@pytest.mark.needs_db
def test_finishing_a_job_drops_its_aggregate(clean: None) -> None:
    with session_scope() as session:
        session.add(_job("job-fin"))
    _cache("job-fin")

    job_queue._finish("job-fin", JobState.SUCCEEDED)

    assert not _cached("job-fin")


@pytest.mark.needs_db
def test_deferred_judging_belongs_to_the_answers_launch(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope() as session:
        session.add(_job("job-judge"))
        session.add(_pair("p-judge", meta={"grading": "behavior"}))
        session.flush()
        session.add_all(_answered("p-judge", "job-judge", verdict="pending"))
    _cache("job-judge")
    # A control answer goes to the behaviour judge.
    monkeypatch.setattr(
        judge,
        "chat",
        lambda *a, **k: ('{"behavior": "declined", "reasoning": "r"}', {}),
    )

    report = judge_pending(
        SpaceConfig(key=KEY, url="http://space.invalid", endpoint="e"),
        settings=Settings(judge_model="t"),
    )
    assert report.checked == 1

    assert not _cached("job-judge")
    with session_scope() as session:
        jobs = {
            run.job_id
            for run in session.query(Run).where(
                Run.space == KEY, Run.judge_model == "t"
            )
        }
    assert jobs == {"job-judge"}
