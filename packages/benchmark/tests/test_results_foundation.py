"""The data under the results pages: the deletion guard, status reasons, the
run aggregate cache, exclusions and the card of a named launch."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

import syft_benchmark.runs.judge as judge
from syft_benchmark.config import (
    JobState,
    PairStatus,
    SpaceConfig,
    StatusReason,
    Verdict,
    get_settings,
)
from syft_benchmark.control import app as control_app
from syft_benchmark.control import jobs as job_queue
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
from syft_benchmark.db.pair_guard import delete_pairs
from syft_benchmark.generation.filter_stage import filter_pending, override_status
from syft_benchmark.llm import Provider
from syft_benchmark.runs.judge_stage import (
    judge_pending,
    override_verdict,
    withdraw_override,
)

TOKEN = "test-results-token"
KEY = "pytest-results-a"
KEY2 = "pytest-results-b"
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


def _console(client: TestClient, key: str) -> dict[str, str]:
    body = TargetSpec(key=key, url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{key}", json=body, headers=AUTH).status_code == 200
    minted = client.post(f"/targets/{key}/session", headers=AUTH)
    assert minted.status_code == 200, minted.text
    return {"Authorization": f"Bearer {minted.json()['token']}"}


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


def _payload(job_id: str) -> dict[str, Any]:
    with session_scope() as session:
        row = session.get(RunAggregate, job_id)
        return dict(row.payload) if row is not None else {}


def _cached(job_id: str) -> bool:
    with session_scope() as session:
        return session.get(RunAggregate, job_id) is not None


# --- the deletion guard ------------------------------------------------------


@needs_db
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


@needs_db
def test_the_console_delete_refuses_a_pair_that_took_part(
    client: TestClient, clean: Any
) -> None:
    session_a = _console(client, KEY)
    with session_scope() as session:
        session.add(_job("job-del"))
        session.add(_pair("p-del"))
        session.flush()
        session.add_all(_answered("p-del", "job-del"))

    assert client.delete("/console/pairs/p-del", headers=session_a).status_code == 409


# --- status reasons ----------------------------------------------------------


@needs_db
def test_an_owner_status_change_records_owner_and_clears_on_return(
    client: TestClient, clean: Any
) -> None:
    session_a = _console(client, KEY)
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


@needs_db
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


@needs_db
def test_the_pair_list_filters_by_status(client: TestClient, clean: Any) -> None:
    session_a = _console(client, KEY)
    with session_scope() as session:
        session.add(_pair("p-on"))
        session.add(_pair("p-off", status=PairStatus.REJECTED.value))

    for name in ("status", "status_filter"):
        listed = client.get(f"/console/pairs?{name}=rejected", headers=session_a)
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()["items"]] == ["p-off"]


# --- the aggregate cache -----------------------------------------------------


@needs_db
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


@needs_db
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


@needs_db
def test_finishing_a_job_drops_its_aggregate(clean: None) -> None:
    with session_scope() as session:
        session.add(_job("job-fin"))
    _cache("job-fin")

    job_queue._finish("job-fin", JobState.SUCCEEDED)

    assert not _cached("job-fin")


@needs_db
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

    seat = Provider(role="judge", url="http://judge.invalid", api_key="k", model="t")
    report = judge_pending(
        SpaceConfig(key=KEY, url="http://space.invalid", endpoint="e"), judge=seat
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


# --- exclusions --------------------------------------------------------------


def _exclusion_url(job_id: str, qa_id: str) -> str:
    return f"/console/report/runs/{job_id}/questions/{qa_id}/exclusion"


@needs_db
def test_excluding_and_restoring_a_question(client: TestClient, clean: Any) -> None:
    session_a = _console(client, KEY)
    with session_scope() as session:
        session.add(_job("job-ex"))
        session.add_all([_pair("p-ex"), _pair("p-absent")])
        session.flush()
        session.add_all(_answered("p-ex", "job-ex"))
    _cache("job-ex")

    url = _exclusion_url("job-ex", "p-ex")
    first = client.put(url, json={"reason": "ambiguous"}, headers=session_a)
    assert first.status_code == 200, first.text
    assert first.json()["exclusion"]["reason"] == "ambiguous"
    assert first.json()["question"]["excluded"] is True
    assert first.json()["question"]["status"] == PairStatus.ACTIVE.value
    # The placeholder is gone; the detail recomputed the real figures.
    assert "run" in _payload("job-ex")

    again = client.put(url, json={"reason": "badly worded"}, headers=session_a)
    assert again.status_code == 200
    assert (
        again.json()["exclusion"]["created_at"]
        == first.json()["exclusion"]["created_at"]
    )
    with session_scope() as session:
        rows = session.query(RunExclusion).where(RunExclusion.job_id == "job-ex").all()
        assert [(r.qa_id, r.reason) for r in rows] == [("p-ex", "badly worded")]

    assert _cached("job-ex")
    assert client.delete(url, headers=session_a).status_code == 204
    assert client.delete(url, headers=session_a).status_code == 204
    assert not _cached("job-ex")
    with session_scope() as session:
        assert session.get(RunExclusion, ("job-ex", "p-ex")) is None

    missing = _exclusion_url("job-ex", "p-absent")
    assert client.put(missing, json={}, headers=session_a).status_code == 404
    assert client.delete(missing, headers=session_a).status_code == 404


@needs_db
def test_excluding_with_retire_retires_the_pair(client: TestClient, clean: Any) -> None:
    session_a = _console(client, KEY)
    with session_scope() as session:
        session.add(_job("job-ret"))
        session.add(_pair("p-ret"))
        session.flush()
        session.add_all(_answered("p-ret", "job-ret"))

    url = _exclusion_url("job-ret", "p-ret")
    done = client.put(url, json={"reason": "wrong", "retire": True}, headers=session_a)
    assert done.status_code == 200
    assert done.json()["question"]["status"] == PairStatus.RETIRED.value
    with session_scope() as session:
        pair = session.get(QaPair, "p-ret")
        assert pair is not None
        assert pair.status == PairStatus.RETIRED.value
        assert pair.status_reason == StatusReason.OWNER.value

    # Restoring keeps the pair retired.
    assert client.delete(url, headers=session_a).status_code == 204
    with session_scope() as session:
        pair = session.get(QaPair, "p-ret")
        assert pair is not None and pair.status == PairStatus.RETIRED.value


@needs_db
def test_another_targets_job_cannot_be_touched(client: TestClient, clean: Any) -> None:
    session_a = _console(client, KEY)
    _console(client, KEY2)
    with session_scope() as session:
        session.add(_job("job-b", target=KEY2))
        session.add(_pair("p-b", space=KEY2))
        session.flush()
        session.add_all(_answered("p-b", "job-b", space=KEY2))

    url = _exclusion_url("job-b", "p-b")
    assert client.put(url, json={}, headers=session_a).status_code == 404
    assert client.delete(url, headers=session_a).status_code == 404


# --- the card of a named launch -----------------------------------------------


@needs_db
def test_the_card_is_built_for_the_named_job(
    client: TestClient, clean: Any, monkeypatch: Any
) -> None:
    session_a = _console(client, KEY)
    _console(client, KEY2)
    with session_scope() as session:
        session.add_all([_job("job-card"), _job("job-foreign", target=KEY2)])

    asked: list[str | None] = []

    def fake_build(*_: Any, job: str | None = None, **__: Any) -> None:
        asked.append(job)

    monkeypatch.setattr(control_app, "build_card", fake_build)
    monkeypatch.setattr(control_app, "latest_measuring_job", lambda _: "newest")

    for route in ("/console/report", "/console/publish"):
        by_body = client.post(route, json={"job": "job-card"}, headers=session_a)
        assert by_body.status_code == 409
        by_query = client.post(f"{route}?job=job-card", headers=session_a)
        assert by_query.status_code == 409
        unnamed = client.post(route, headers=session_a)
        assert unnamed.status_code == 409
        foreign = client.post(route, json={"job": "job-foreign"}, headers=session_a)
        assert foreign.status_code == 404

    assert asked == ["job-card", "job-card", "newest"] * 2
