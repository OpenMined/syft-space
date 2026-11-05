"""The job queue: one measurement per target at a time, and how a job ends.

The queue is a row two threads look at, so most of these checks run against the
test database: a stubbed session would check a conspiracy of stubs rather than the
behaviour.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from syft_benchmark.config import JobPhase, JobState
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db.models import Job
from syft_benchmark.db.session import session_scope

from support import AUTH

KEY = "pytest-target"


# --- queueing --------------------------------------------------------------


@pytest.mark.needs_db
def test_the_same_target_is_not_measured_twice_at_once(
    client: TestClient, clean: Any
) -> None:
    """A double press of the button must not mean a double measurement of one node."""
    client.put(
        f"/targets/{KEY}",
        json=TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json"),
        headers=AUTH,
    )
    first = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH)
    second = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH)
    assert first.status_code == 202
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.needs_db
def test_a_disabled_target_is_not_measured(client: TestClient, clean: Any) -> None:
    spec = TargetSpec(key=KEY, url="http://space.invalid", enabled=False)
    client.put(f"/targets/{KEY}", json=spec.model_dump(mode="json"), headers=AUTH)
    assert client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH).status_code == 409


@pytest.mark.needs_db
def test_filter_and_judge_queue_a_job_of_their_own_kind(
    client: TestClient, clean: Any
) -> None:
    """Unlike `/runs`, these never touch generation or evaluation."""
    client.put(
        f"/targets/{KEY}",
        json=TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json"),
        headers=AUTH,
    )

    filtered = client.post(f"/targets/{KEY}/filter", json={}, headers=AUTH)
    assert filtered.status_code == 202, filtered.text
    assert filtered.json()["kind"] == "filter"

    with session_scope() as session:
        session.execute(delete(Job).where(Job.target == KEY))

    judged = client.post(f"/targets/{KEY}/judge", json={}, headers=AUTH)
    assert judged.status_code == 202, judged.text
    assert judged.json()["kind"] == "judge"


@pytest.mark.needs_db
def test_filter_is_refused_for_a_disabled_target(
    client: TestClient, clean: Any
) -> None:
    spec = TargetSpec(key=KEY, url="http://space.invalid", enabled=False)
    client.put(f"/targets/{KEY}", json=spec.model_dump(mode="json"), headers=AUTH)
    refused = client.post(f"/targets/{KEY}/filter", json={}, headers=AUTH)
    assert refused.status_code == 409


# --- how a job ends --------------------------------------------------------


def test_a_cancelled_job_is_finished_and_not_an_error() -> None:
    """A measurement stopped by its owner is finished, not broken: the data stayed."""
    assert JobState.CANCELLED.final
    assert JobState.QUEUED.final is False
    assert JobState.RUNNING.final is False


@pytest.mark.needs_db
def test_a_queued_job_is_dropped_on_the_spot(client: TestClient, clean: Any) -> None:
    """No work has been done on it yet — so there is nothing to finish either."""
    client.put(
        f"/targets/{KEY}",
        json=TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json"),
        headers=AUTH,
    )
    job_id = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH).json()["id"]
    stopped = client.post(f"/jobs/{job_id}/cancel", headers=AUTH)
    assert stopped.json()["state"] == JobState.CANCELLED.value
    assert client.post(f"/jobs/{job_id}/cancel", headers=AUTH).status_code == 409


@pytest.mark.needs_db
def test_a_job_running_when_the_service_died_is_closed_on_restart(clean: Any) -> None:
    """Otherwise it is an eternally live measurement and a queue locked forever."""
    with session_scope() as session:
        session.add(
            Job(
                id="pytest-stale-job",
                target=KEY,
                state=JobState.RUNNING.value,
                phase=JobPhase.EVALUATE.value,
            )
        )
    try:
        assert job_queue.sweep() >= 1
        with session_scope() as session:
            job = session.get(Job, "pytest-stale-job")
            assert job is not None
            assert job.state == JobState.FAILED.value
            # A code, not a phrase: the job's row is read by a foreign UI.
            assert job.error == job_queue.SERVICE_RESTARTED
    finally:
        with session_scope() as session:
            session.execute(delete(Job).where(Job.id == "pytest-stale-job"))


@pytest.mark.needs_db
def test_a_finished_job_carries_its_notes_as_the_message_not_the_error(
    clean: Any,
) -> None:
    """A skipped block is not a failure: the UI reads `error` as one."""
    with session_scope() as session:
        session.add(
            Job(
                id="pytest-noted-job",
                target=KEY,
                state=JobState.RUNNING.value,
                phase=JobPhase.EVALUATE.value,
                message="pass 3",
            )
        )
    note = "openai/o9: no temperature, Monte Carlo skipped"
    job_queue._finish("pytest-noted-job", JobState.SUCCEEDED, message=note)
    with session_scope() as session:
        job = session.get(Job, "pytest-noted-job")
        assert job is not None
        assert job.state == JobState.SUCCEEDED.value
        assert job.error == ""
        assert job.message == note
