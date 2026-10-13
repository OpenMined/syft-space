"""Deleting one run from the console: only that job's data goes, questions stay."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from syft_benchmark.config import JobState, PairStatus, get_settings
from syft_benchmark.control import report_routes
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db import (
    Job,
    QaPair,
    Result,
    Run,
    RunAggregate,
    RunExclusion,
    Target,
    session_scope,
)
from syft_benchmark.generation import decisions
from syft_benchmark.publish import PublishOutcome

TOKEN = "test-delete-run-token"
KEY = "pytest-delete-a"
KEY2 = "pytest-delete-b"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean() -> Any:
    def wipe() -> None:
        with session_scope() as session:
            for key in (KEY, KEY2):
                session.execute(delete(Result).where(Result.space == key))
                session.execute(delete(Run).where(Run.space == key))
                session.execute(delete(QaPair).where(QaPair.space == key))
                session.execute(delete(Job).where(Job.target == key))
                session.execute(delete(Target).where(Target.key == key))

    wipe()
    yield
    wipe()


@pytest.fixture
def client() -> Any:
    conf = get_settings().model_copy(update={"control_token": TOKEN})
    return TestClient(create_app(conf))


@pytest.fixture
def space(monkeypatch: Any) -> dict[str, Any]:
    """The Space as the route sees it: which job is published, retractions."""
    state: dict[str, Any] = {"published": None, "retracted": 0, "retract_ok": True}

    def fake_published(_: Any) -> tuple[PublishOutcome, str | None]:
        return PublishOutcome(True, "read"), state["published"]

    def fake_retract(_: Any) -> PublishOutcome:
        if not state["retract_ok"]:
            return PublishOutcome(False, "HTTP 500: down")
        state["retracted"] += 1
        state["published"] = None
        return PublishOutcome(True, "retracted: True")

    monkeypatch.setattr(report_routes, "published_job", fake_published)
    monkeypatch.setattr(report_routes, "retract_card", fake_retract)
    return state


def _console(client: TestClient, key: str) -> dict[str, str]:
    body = TargetSpec(key=key, url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{key}", json=body, headers=AUTH).status_code == 200
    minted = client.post(f"/targets/{key}/session", headers=AUTH)
    assert minted.status_code == 200, minted.text
    return {"Authorization": f"Bearer {minted.json()['token']}"}


def _seed(job_id: str, pair_id: str, *, target: str = KEY, state: str = "") -> None:
    """A job, a question it wrote and screened, its answer, override,
    exclusion and cached figures."""
    with session_scope() as session:
        session.add(
            Job(id=job_id, target=target, state=state or JobState.SUCCEEDED.value)
        )
        session.add(
            QaPair(
                id=pair_id,
                space=target,
                job_id=job_id,
                generator="qa",
                question="What port does the benchmark database listen on?",
                answer="5442",
                status=PairStatus.ACTIVE.value,
                model="m",
                question_hash=pair_id,
                meta={
                    "keep": 1,
                    decisions.SCREENING: [
                        decisions.record(
                            job_id=job_id, stage=decisions.GROUNDING, outcome="kept"
                        ),
                        decisions.record(
                            job_id="job-other", stage=decisions.CONTROL, outcome="kept"
                        ),
                    ],
                },
            )
        )
        session.flush()
        for suffix in ("answer", "override"):
            run_id = f"run-{job_id}-{suffix}"
            session.add(
                Run(
                    id=run_id,
                    space=target,
                    job_id=job_id,
                    context_mode="closed_book",
                    model="m",
                )
            )
            session.flush()
            session.add(
                Result(
                    id=f"result-{job_id}-{suffix}",
                    run_id=run_id,
                    qa_id=pair_id,
                    space=target,
                    verdict="correct",
                )
            )
        session.add(RunExclusion(job_id=job_id, qa_id=pair_id, reason="x"))
        session.add(RunAggregate(job_id=job_id, version=1, payload={"x": 1}))


def _left(job_id: str) -> dict[str, int]:
    with session_scope() as session:

        def count(model: Any, *where: Any) -> int:
            return session.execute(
                select(func.count()).select_from(model).where(*where)
            ).scalar_one()

        return {
            "jobs": count(Job, Job.id == job_id),
            "runs": count(Run, Run.job_id == job_id),
            "results": count(Result, Result.id.like(f"result-{job_id}-%")),
            "exclusions": count(RunExclusion, RunExclusion.job_id == job_id),
            "aggregates": count(RunAggregate, RunAggregate.job_id == job_id),
        }


GONE = {"jobs": 0, "runs": 0, "results": 0, "exclusions": 0, "aggregates": 0}
KEPT = {"jobs": 1, "runs": 2, "results": 2, "exclusions": 1, "aggregates": 1}


@needs_db
def test_deleting_a_run_takes_only_its_data_and_keeps_the_questions(
    client: TestClient, clean: Any, space: dict[str, Any]
) -> None:
    session_a = _console(client, KEY)
    _seed("job-del", "p-del")
    _seed("job-keep", "p-keep")

    done = client.delete("/console/report/runs/job-del", headers=session_a)
    assert done.status_code == 204, done.text

    assert _left("job-del") == GONE
    assert _left("job-keep") == KEPT
    assert space["retracted"] == 0
    with session_scope() as session:
        pair = session.get(QaPair, "p-del")
        assert pair is not None
        assert pair.status == PairStatus.ACTIVE.value
        assert pair.job_id is None
        assert pair.meta["keep"] == 1
        assert [r["job_id"] for r in pair.meta[decisions.SCREENING]] == ["job-other"]
        other = session.get(QaPair, "p-keep")
        assert other is not None and other.job_id == "job-keep"

    again = client.delete("/console/report/runs/job-del", headers=session_a)
    assert again.status_code == 404


@needs_db
@pytest.mark.parametrize("state", [JobState.QUEUED.value, JobState.RUNNING.value])
def test_a_queued_or_running_run_is_refused(
    client: TestClient, clean: Any, space: dict[str, Any], state: str
) -> None:
    session_a = _console(client, KEY)
    _seed("job-live", "p-live", state=state)

    refused = client.delete("/console/report/runs/job-live", headers=session_a)
    assert refused.status_code == 409
    assert _left("job-live") == KEPT


@needs_db
def test_another_targets_run_cannot_be_deleted(
    client: TestClient, clean: Any, space: dict[str, Any]
) -> None:
    session_a = _console(client, KEY)
    _console(client, KEY2)
    _seed("job-b", "p-b", target=KEY2)

    refused = client.delete("/console/report/runs/job-b", headers=session_a)
    assert refused.status_code == 404
    assert _left("job-b") == KEPT


@needs_db
def test_a_published_run_is_made_private_first(
    client: TestClient, clean: Any, space: dict[str, Any]
) -> None:
    session_a = _console(client, KEY)
    _seed("job-pub", "p-pub")
    space["published"] = "job-pub"

    done = client.delete("/console/report/runs/job-pub", headers=session_a)
    assert done.status_code == 204, done.text
    assert space["retracted"] == 1
    assert _left("job-pub") == GONE


@needs_db
def test_a_failed_retraction_keeps_the_run(
    client: TestClient, clean: Any, space: dict[str, Any]
) -> None:
    session_a = _console(client, KEY)
    _seed("job-stuck", "p-stuck")
    space["published"] = "job-stuck"
    space["retract_ok"] = False

    refused = client.delete("/console/report/runs/job-stuck", headers=session_a)
    assert refused.status_code == 502
    assert "made private" in refused.json()["detail"]
    assert _left("job-stuck") == KEPT


@needs_db
def test_an_unreachable_space_keeps_the_run(client: TestClient, clean: Any) -> None:
    session_a = _console(client, KEY)
    _seed("job-far", "p-far")

    refused = client.delete("/console/report/runs/job-far", headers=session_a)
    assert refused.status_code == 502
    assert _left("job-far") == KEPT


def test_the_published_job_is_read_from_the_spaces_card(monkeypatch: Any) -> None:
    import httpx

    from syft_benchmark.config import SpaceConfig
    from syft_benchmark.publish import published_job

    replies = iter(
        [
            httpx.Response(200, json={"reported": True, "report": {"job": "job-x"}}),
            httpx.Response(200, json={"reported": False, "report": None}),
            httpx.Response(404),
            httpx.Response(500, text="boom"),
        ]
    )
    monkeypatch.setattr(httpx, "get", lambda *_, **__: next(replies))
    space_conf = SpaceConfig(key=KEY, url="http://space.invalid", endpoint="e")

    assert published_job(space_conf)[1] == "job-x"
    assert published_job(space_conf) == (PublishOutcome(True, "read"), None)
    assert published_job(space_conf)[0].ok
    failed, job = published_job(space_conf)
    assert not failed.ok and job is None
