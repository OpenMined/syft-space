"""The console: a session token scoped to one target, and what it can reach.

The one thing that matters most here is isolation — a session minted for one
target must not read, change or delete another's pairs and results by
guessing an id — so most of these checks are two-target checks, not
one-target checks with an extra assertion bolted on.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from syft_benchmark.config import PairStatus, Verdict, get_settings
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db.models import Job, QaPair, Result, Run, Target
from syft_benchmark.db.session import session_scope

TOKEN = "test-console-token"
KEY = "pytest-console-a"
KEY2 = "pytest-console-b"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(Job).where(Job.target == KEY))
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
    """Same reasoning as `test_control.py`'s: no worker thread in tests."""
    conf = get_settings().model_copy(update={"control_token": TOKEN})
    return TestClient(create_app(conf))


def _register(client: TestClient, key: str) -> None:
    body = TargetSpec(key=key, url="http://space.invalid").model_dump(mode="json")
    made = client.put(f"/targets/{key}", json=body, headers=AUTH)
    assert made.status_code == 200, made.text


def _session_for(client: TestClient, key: str) -> dict[str, str]:
    minted = client.post(f"/targets/{key}/session", headers=AUTH)
    assert minted.status_code == 200, minted.text
    return {"Authorization": f"Bearer {minted.json()['token']}"}


def _pair(
    pair_id: str, space: str, *, status: str = PairStatus.PENDING.value
) -> QaPair:
    return QaPair(
        id=pair_id,
        space=space,
        generator="cloze",
        question="q",
        answer="a",
        context="a fragment",
        status=status,
        model="m",
        question_hash=pair_id,
    )


@needs_db
def test_a_session_reaches_only_its_own_target(client: TestClient, clean: Any) -> None:
    _register(client, KEY)
    _register(client, KEY2)
    session_a = _session_for(client, KEY)

    with session_scope() as db:
        db.add(_pair("pair-a", KEY))
        db.add(_pair("pair-b", KEY2))

    # Its own target's pairs are visible...
    listed = client.get("/console/pairs", headers=session_a)
    assert listed.status_code == 200
    assert {row["id"] for row in listed.json()["items"]} == {"pair-a"}

    # ...but the other target's pair, by id, is not.
    assert client.get("/console/pairs/pair-b", headers=session_a).status_code == 404
    patched = client.patch(
        "/console/pairs/pair-b",
        json={"status": "rejected"},
        headers=session_a,
    )
    assert patched.status_code == 404
    assert client.delete("/console/pairs/pair-b", headers=session_a).status_code == 404

    with session_scope() as db:
        row = db.get(QaPair, "pair-b")
        assert (
            row is not None and row.status == PairStatus.PENDING.value
        ), "a foreign session must not have changed it"


@needs_db
def test_a_wrong_or_garbage_session_token_is_refused(
    client: TestClient, clean: Any
) -> None:
    _register(client, KEY)
    bad = {"Authorization": "Bearer not-a-real-session"}
    assert client.get("/console/pairs", headers=bad).status_code == 401
    assert client.get("/console/pairs").status_code == 401


@needs_db
def test_patch_and_delete_round_trip(client: TestClient, clean: Any) -> None:
    _register(client, KEY)
    session_a = _session_for(client, KEY)

    with session_scope() as db:
        db.add(_pair("pair-lonely", KEY))
        db.add(_pair("pair-measured", KEY, status=PairStatus.ACTIVE.value))
        db.add(Run(id="run-console", space=KEY, context_mode="closed_book", model="m"))
        db.add(
            Result(
                id="result-console",
                run_id="run-console",
                qa_id="pair-measured",
                space=KEY,
                verdict="correct",
            )
        )

    rejected = client.patch(
        "/console/pairs/pair-lonely",
        json={"status": "rejected", "note": "not actually grounded"},
        headers=session_a,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["status_note"] == "not actually grounded"

    assert (
        client.delete("/console/pairs/pair-lonely", headers=session_a).status_code
        == 204
    )
    assert (
        client.get("/console/pairs/pair-lonely", headers=session_a).status_code == 404
    )

    blocked = client.delete("/console/pairs/pair-measured", headers=session_a)
    assert blocked.status_code == 409
    still_there = client.get("/console/pairs/pair-measured", headers=session_a)
    assert still_there.status_code == 200
    assert still_there.json()["has_results"] is True


@needs_db
def test_overriding_a_verdict_inserts_and_is_visible_as_latest(
    client: TestClient, clean: Any
) -> None:
    _register(client, KEY)
    session_a = _session_for(client, KEY)

    with session_scope() as db:
        db.add(_pair("pair-verdict", KEY, status=PairStatus.ACTIVE.value))
        db.add(Run(id="run-verdict", space=KEY, context_mode="closed_book", model="m"))
        db.add(
            Result(
                id="result-verdict",
                run_id="run-verdict",
                qa_id="pair-verdict",
                space=KEY,
                verdict=Verdict.HALLUCINATE.value,
            )
        )

    overridden = client.post(
        "/console/results/result-verdict/verdict",
        json={"verdict": "correct", "reasoning": "actually fine"},
        headers=session_a,
    )
    assert overridden.status_code == 200, overridden.text
    new_id = overridden.json()["id"]
    assert new_id != "result-verdict"
    assert overridden.json()["verdict"] == "correct"
    assert overridden.json()["generator"] == "cloze"

    listed = client.get(
        "/console/results", params={"qa_id": "pair-verdict"}, headers=session_a
    )
    assert listed.status_code == 200
    rows = {row["id"]: row for row in listed.json()["items"]}
    assert rows[new_id]["is_latest"] is True
    assert rows["result-verdict"]["is_latest"] is False
    assert rows[new_id]["generator"] == "cloze"


@needs_db
def test_console_runs_filter_and_judge_queue_the_right_kind(
    client: TestClient, clean: Any
) -> None:
    _register(client, KEY)
    session_a = _session_for(client, KEY)

    run = client.post("/console/runs", json={}, headers=session_a)
    assert run.status_code == 202, run.text
    assert run.json()["kind"] == "pipeline"

    with session_scope() as db:
        db.execute(delete(Job).where(Job.target == KEY))

    filtered = client.post("/console/filter", json={}, headers=session_a)
    assert filtered.status_code == 202
    assert filtered.json()["kind"] == "filter"

    with session_scope() as db:
        db.execute(delete(Job).where(Job.target == KEY))

    judged = client.post("/console/judge", json={}, headers=session_a)
    assert judged.status_code == 202
    assert judged.json()["kind"] == "judge"


@needs_db
def test_console_report_with_nothing_graded_is_a_conflict(
    client: TestClient, clean: Any
) -> None:
    _register(client, KEY)
    session_a = _session_for(client, KEY)
    assert client.post("/console/report", headers=session_a).status_code == 409
    assert client.post("/console/publish", headers=session_a).status_code == 409


@needs_db
def test_console_retract_against_an_unreachable_space_is_a_bad_gateway(
    client: TestClient, clean: Any
) -> None:
    _register(client, KEY)
    session_a = _session_for(client, KEY)
    assert client.post("/console/retract", headers=session_a).status_code == 502


@needs_db
def test_the_probe_layer_round_trips_and_reports_what_it_inherits(
    client: TestClient, clean: Any
) -> None:
    _register(client, KEY)
    session_a = _session_for(client, KEY)

    fresh = client.get("/console/probe", headers=session_a)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["probe"] == {}
    assert "retrieval_top_k" in fresh.json()["inherited"]
    assert any(field["name"] == "retrieval_top_k" for field in fresh.json()["fields"])

    saved = client.put("/console/probe", json={"retrieval_top_k": 3}, headers=session_a)
    assert saved.status_code == 200, saved.text
    assert saved.json()["probe"] == {"retrieval_top_k": 3}

    reread = client.get("/console/probe", headers=session_a)
    assert reread.json()["probe"] == {"retrieval_top_k": 3}


@needs_db
def test_the_probe_layer_is_scoped_to_its_own_target(
    client: TestClient, clean: Any
) -> None:
    _register(client, KEY)
    _register(client, KEY2)
    session_a = _session_for(client, KEY)

    client.put("/console/probe", json={"retrieval_top_k": 9}, headers=session_a)

    with session_scope() as db:
        other = db.get(Target, KEY2)
        assert other is not None
        assert other.probe in (None, {})
