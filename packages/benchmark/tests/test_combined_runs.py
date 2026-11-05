"""Combined runs: the pooled figures, the lifecycle, visibility and combining
per period."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from test_run_view import Seed

from syft_benchmark.config import JobKind, JobState, PairStatus, StatusReason
from syft_benchmark.control import combined
from syft_benchmark.db import CombinedMember, Job, Result, Run, Target, session_scope
from syft_benchmark.report import combined_view
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE

from support import AUTH, console_auth

KEY = "pytest-combined-a"
KEY2 = "pytest-combined-b"
T0 = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)
M1 = "vendor/model-one"
J1, J2 = "judge/primary", "judge/second"
A, B, C, D = "cb-job-a", "cb-job-b", "cb-job-c", "cb-job-d"
TRICK = "unanswerable_property"

pytestmark = pytest.mark.needs_db

COST_A = {
    "spend_before": 10.0,
    "spend_after": 11.0,
    "usd": 1.0,
    "usd_calls": 0.9,
    "total_usd": 0.8,
    "by_role": {"judges": 0.5, "subjects": 0.3},
}
COST_B = {
    "spend_before": 11.0,
    "spend_after": 13.0,
    "usd": 2.0,
    "usd_calls": 1.5,
    "total_usd": 1.2,
    "by_role": {"judges": 0.7, "writer": 0.5},
}
TIMING_A = {
    "total_s": 100.0,
    "phases": [{"phase": "evaluate", "s": 60.0}, {"phase": "judge", "s": 40.0}],
    "passes": [
        {
            "arm": "alone",
            "block": "direct",
            "model": M1,
            "s": 10.0,
            "questions": 2,
            "stopped": "",
        }
    ],
    "calls": [
        {
            "model": M1,
            "role": "answer",
            "count": 4,
            "failed": 1,
            "mean_s": 2.0,
            "p90_s": 3.0,
            "max_s": 5.0,
            "total_s": 8.0,
        }
    ],
    "concurrency": {"model": 4, "endpoint": 2},
}
TIMING_B = {
    "total_s": 50.0,
    "phases": [{"phase": "evaluate", "s": 30.0}],
    "passes": [
        {
            "arm": "alone",
            "block": "direct",
            "model": M1,
            "s": 5.0,
            "questions": 3,
            "stopped": "",
        }
    ],
    "calls": [
        {
            "model": M1,
            "role": "answer",
            "count": 6,
            "failed": 0,
            "mean_s": 3.0,
            "p90_s": 4.0,
            "max_s": 7.0,
            "total_s": 18.0,
        },
        {
            "model": J2,
            "role": "judge",
            "count": 3,
            "failed": 0,
            "mean_s": 1.0,
            "p90_s": 1.0,
            "max_s": 1.0,
            "total_s": 3.0,
        },
    ],
    "concurrency": {"model": 4, "endpoint": 2},
}


def _kind(budget: int, written: int, duplicate: int) -> dict[str, Any]:
    return {
        "kind": "qa",
        "unit": "passage",
        "budget": budget,
        "written": written,
        "units_available": 10,
        "units_read": 4,
        "failed_units": 0,
        "topped_up": 0,
        "dropped": {"duplicate": duplicate},
        "stopped": "",
    }


def _params(panel: list[str], **extra: Any) -> dict[str, Any]:
    return {"settings_hash": "h1", "judge_panel": panel, **extra}


def _seed_pair(client: TestClient) -> tuple[dict[str, str], dict[str, str]]:
    """Two compatible runs of one model; q2 is asked in both.

    A (primary J1): q1 alone J1 hallucinate / J2 correct, with correct; q2
    right both ways; a trick question made up; r1 written and rejected.
    B (panel J2, J1 — primary J2): q2 alone J1 correct / J2 hallucinate, with
    correct; q3 alone abstain, with J2 correct / J1 hallucinate; q4 alone
    correct, with J2 abstain overridden to correct.
    """
    auth = console_auth(client, KEY)
    ids: dict[str, str] = {}
    a = Seed(A, space=KEY)
    a.pair("cb-q1", job_id=A)
    a.pair("cb-q2", job_id=A)
    a.pair("cb-t1", generator=TRICK, job_id=A)
    a.pair(
        "cb-r1",
        job_id=A,
        status=PairStatus.REJECTED.value,
        status_reason=StatusReason.GROUNDING.value,
    )
    ids["a_q1_alone"] = a.answer("cb-q1", M1, "alone", "hallucinate", judge=J1)
    a.answer("cb-q1", M1, "alone", "correct", judge=J2)
    a.answer("cb-q1", M1, "with", "correct", judge=J1)
    a.answer("cb-q2", M1, "alone", "correct", judge=J1)
    a.answer("cb-q2", M1, "with", "correct", judge=J1)
    a.answer("cb-t1", M1, "with", "hallucinate", judge=J1)
    a.save(
        params=_params(
            [J1, J2], cost=COST_A, timing=TIMING_A, generation=[_kind(5, 3, 1)]
        ),
        started_at=T0,
    )

    b = Seed(B, space=KEY)
    b.pair("cb-q3", job_id=B)
    b.pair("cb-q4", job_id=B)
    b.answer("cb-q2", M1, "alone", "correct", judge=J1)
    b.answer("cb-q2", M1, "alone", "hallucinate", judge=J2)
    b.answer("cb-q2", M1, "with", "correct", judge=J2)
    b.answer("cb-q3", M1, "alone", "abstain", judge=J2)
    b.answer("cb-q3", M1, "with", "correct", judge=J2)
    b.answer("cb-q3", M1, "with", "hallucinate", judge=J1)
    b.answer("cb-q4", M1, "alone", "correct", judge=J2)
    b.answer("cb-q4", M1, "with", "abstain", judge=J2)
    b.answer("cb-q4", M1, "with", "correct", judge=OWNER_OVERRIDE)
    b.save(
        params=_params(
            [J2, J1], cost=COST_B, timing=TIMING_B, generation=[_kind(4, 2, 2)]
        ),
        created_at=T0 + timedelta(hours=2),
        started_at=T0 + timedelta(hours=2),
    )
    with session_scope() as session:
        for job, latency in ((A, 1.0), (B, 4.0)):
            runs = select(Run.id).where(Run.job_id == job)
            session.execute(
                update(Result).where(Result.run_id.in_(runs)).values(latency_s=latency)
            )
    return auth, ids


def _create(
    client: TestClient, auth: dict[str, str], *job_ids: str, title: str | None = None
) -> Any:
    made = client.post(
        "/console/report/combined",
        json={"job_ids": list(job_ids), "title": title},
        headers=auth,
    )
    assert made.status_code == 201, made.text
    return made.json()


def _report(client: TestClient, auth: dict[str, str], job_id: str) -> Any:
    got = client.get(f"/console/report/runs/{job_id}", headers=auth)
    assert got.status_code == 200, got.text
    return got.json()


def _listed(client: TestClient, auth: dict[str, str], **params: Any) -> Any:
    got = client.get("/console/report/runs", params=params, headers=auth)
    assert got.status_code == 200, got.text
    return got.json()


def test_combined_figures_are_recomputed_from_pooled_answers(
    client: TestClient, clean: Any
) -> None:
    auth, _ = _seed_pair(client)
    item = _create(client, auth, B, A, title="Two runs")
    cid = item["job_id"]
    assert item["combined"] == {
        "members": 2,
        "origin": "manual",
        "period": None,
        "period_start": None,
        "title": "Two runs",
    }

    report = _report(client, auth, cid)
    (m1,) = report["models"]
    # q1 and q2 from A, q3 and q4 from B; q2 counts once, from A.
    assert m1["asked"] == 4
    assert (m1["right_alone"], m1["graded_alone"]) == (2, 4)
    assert (m1["right_with"], m1["graded_with"]) == (4, 4)
    assert m1["rate_alone"] == 0.5 and m1["rate_with"] == 1.0
    assert m1["lift"] == 50
    assert m1["made_up_alone"] == 0.25 and m1["made_up_with"] == 0.0
    assert m1["tally"]["alone"]["abstain"] == 1
    assert m1["groups"] == {"fixed": 2, "either": 2, "still": 0, "worse": 0}
    checks = m1["checks"]
    assert (checks["trick_asked"], checks["trick_answered"]) == (1, 1)
    # Two judges graded q1 alone (A) and q3 with (B); B's q2 is not counted.
    assert (checks["answers"], checks["judges_agreed"]) == (2, 0)

    run = report["run"]
    assert run["job_id"] == cid and run["window_days"] is None
    assert run["questions"] == 4 and run["articles"] == 4
    assert run["articles_new"] == 6
    assert run["created_at"] == T0.isoformat()
    assert run["combined"]["members"] == 2
    assert run["build_only"] is False
    assert report["judges"] == [J1, J2]
    assert report["method"]["trick"] == 1

    assert report["funnel"] == {
        "written": 5,
        "removed": {"grounding": 1},
        "removed_total": 1,
        "unchecked": None,
        "asked": 5,
        "trick": 1,
    }
    assert report["method"]["cost"] == {
        "spend_before": 10.0,
        "spend_after": 13.0,
        "usd": 3.0,
        "usd_calls": 2.4,
        "total_usd": 2.0,
        "by_role": {"judges": 1.2, "subjects": 0.3, "writer": 0.5},
    }
    timing = report["timing"]
    assert timing["total_s"] == 150.0
    assert timing["phases"] == [
        {"phase": "evaluate", "s": 90.0},
        {"phase": "judge", "s": 40.0},
    ]
    assert timing["passes"] == [
        {
            "arm": "alone",
            "block": "direct",
            "model": M1,
            "s": 15.0,
            "questions": 5,
            "stopped": "",
        }
    ]
    answer, judge = timing["calls"]
    # 5 answers of A at 1 s, 6 of B at 4 s: the 10th of 11 is 4 s.
    assert answer == {
        "model": M1,
        "role": "answer",
        "count": 10,
        "failed": 1,
        "mean_s": 2.6,
        "p90_s": 4.0,
        "max_s": 7.0,
        "total_s": 26.0,
    }
    assert judge["p90_s"] is None and judge["mean_s"] == 1.0
    assert timing["concurrency"] == {"model": 4, "endpoint": 2}

    first, second = report["members"]
    assert (first["job_id"], second["job_id"]) == (A, B)
    assert (first["questions"], second["questions"]) == (2, 3)
    assert (first["documents"], second["documents"]) == (2, 3)
    assert (first["cost_usd"], second["cost_usd"]) == (0.8, 1.2)
    assert first["state"] == "succeeded" and first["stopped"] is None

    repeats = report["repeats"]
    assert repeats["questions"] == 1
    (by_model,) = repeats["models"]
    assert by_model["model"] == M1
    assert by_model["alone"] == {
        "questions": 1,
        "observations": 2,
        "graded": 2,
        "compared": 1,
        "agreed": 0,
        "agreement": 0.0,
        "right": 1,
        "accuracy": 0.5,
        "wrong_to_right": 0,
        "right_to_wrong": 1,
    }
    assert by_model["with"]["agreement"] == 1.0
    assert by_model["with"]["accuracy"] == 1.0

    generated = client.get(f"/console/report/runs/{cid}/generated", headers=auth).json()
    (kind,) = generated["kinds"]
    assert (kind["budget"], kind["written"], kind["units_read"]) == (9, 5, 8)
    assert kind["dropped"] == {"duplicate": 3}
    assert generated["total"] == 6


def test_a_single_run_keeps_its_shape(client: TestClient, clean: Any) -> None:
    auth, _ = _seed_pair(client)
    report = _report(client, auth, A)
    assert report["members"] is None and report["repeats"] is None
    page = client.get(
        f"/console/report/runs/{A}/questions", params={"model": M1}, headers=auth
    ).json()
    assert {row["job_id"] for row in page["items"]} == {A}


def test_combined_questions_name_the_counted_member(
    client: TestClient, clean: Any
) -> None:
    auth, _ = _seed_pair(client)
    cid = _create(client, auth, A, B)["job_id"]
    page = client.get(
        f"/console/report/runs/{cid}/questions", params={"model": M1}, headers=auth
    ).json()
    assert {row["qa_id"]: row["job_id"] for row in page["items"]} == {
        "cb-q1": A,
        "cb-q2": A,
        "cb-q3": B,
        "cb-q4": B,
    }
    detail = client.get(
        f"/console/report/runs/{cid}/questions/cb-q2",
        params={"model": M1},
        headers=auth,
    ).json()
    assert detail["question"]["job_id"] == A
    assert detail["arms"]["alone"]["verdict"] == "correct"
    assert [
        (o["job_id"], o["verdict_alone"], o["verdict_with"])
        for o in detail["observations"]
    ] == [(A, "correct", "correct"), (B, "hallucinate", "correct")]
    # q3 is read with B's judges: its primary J2 counts.
    q3 = client.get(
        f"/console/report/runs/{cid}/questions/cb-q3",
        params={"model": M1},
        headers=auth,
    ).json()
    assert q3["arms"]["with"]["verdict"] == "correct"
    assert q3["judges"][0] == {**q3["judges"][0], "model": J2, "primary": True}
    fragments = client.get(
        f"/console/report/runs/{cid}/questions/cb-q3/fragments",
        params={"model": M1},
        headers=auth,
    )
    assert fragments.status_code == 200 and fragments.json() == []


def test_the_runs_list_hides_members_unless_asked(
    client: TestClient, clean: Any
) -> None:
    auth, _ = _seed_pair(client)
    lone = Seed(C, space=KEY)
    lone.pair("cb-q5")
    lone.answer("cb-q5", M1, "with", "correct")
    lone.save(params=_params([J1]), created_at=T0 + timedelta(hours=5))
    cid = _create(client, auth, A, B)["job_id"]

    hidden = _listed(client, auth)
    assert [i["job_id"] for i in hidden["items"]] == [C, cid]
    assert hidden["total"] == 2
    assert hidden["items"][0]["combined"] is None
    assert hidden["items"][0]["combined_into"] == []
    assert hidden["items"][1]["combined"]["members"] == 2

    shown = _listed(client, auth, show_combined_members="true")
    assert shown["total"] == 4
    into = {i["job_id"]: i["combined_into"] for i in shown["items"]}
    held = [{"job_id": cid, "title": None}]
    assert into == {C: [], B: held, A: held, cid: []}
    paged = _listed(client, auth, show_combined_members="true", limit=1, offset=3)
    assert [i["job_id"] for i in paged["items"]] == [shown["items"][3]["job_id"]]

    deleted = client.delete(f"/console/report/runs/{cid}", headers=auth)
    assert deleted.status_code == 204
    again = _listed(client, auth)
    assert {i["job_id"] for i in again["items"]} == {A, B, C}
    with session_scope() as session:
        assert session.get(Job, A) is not None
        assert session.get(Job, B) is not None


def test_a_combined_run_is_listed_at_its_latest_member(
    client: TestClient, clean: Any
) -> None:
    auth = console_auth(client, KEY)
    times = {
        A: (T0, T0 + timedelta(hours=1)),
        B: (T0 + timedelta(days=2), T0 + timedelta(days=2, hours=3)),
        C: (T0 + timedelta(days=2, hours=1), T0 + timedelta(days=2, hours=2)),
    }
    for job, (created, finished) in times.items():
        seed = Seed(job, space=KEY)
        seed.pair(f"lt-{job}", job_id=job)
        seed.answer(f"lt-{job}", M1, "with", "correct")
        seed.save(params=_params([J1]), created_at=created)
        with session_scope() as session:
            session.execute(
                update(Job).where(Job.id == job).values(finished_at=finished)
            )
    cid = _create(client, auth, A, B)["job_id"]

    shown = _listed(client, auth, show_combined_members="true")
    # B finished last, at T0 + 2 days 3 h; C was created after B.
    assert [i["job_id"] for i in shown["items"]] == [cid, C, B, A]
    assert shown["total"] == 4
    assert shown["items"][0]["created_at"] == T0.isoformat()
    paged = _listed(client, auth, show_combined_members="true", limit=2, offset=2)
    assert [i["job_id"] for i in paged["items"]] == [B, A]
    assert paged["total"] == 4

    day = T0.date()
    late = _listed(client, auth, **{"from": str(day + timedelta(days=2))})
    assert [i["job_id"] for i in late["items"]] == [cid, C]
    assert late["total"] == 2
    early = _listed(
        client, auth, show_combined_members="true", to=str(day + timedelta(days=1))
    )
    assert [i["job_id"] for i in early["items"]] == [A]
    assert early["total"] == 1


def test_check_reports_differences(client: TestClient, clean: Any) -> None:
    auth, _ = _seed_pair(client)
    ok = client.post(
        "/console/report/combined/check", json={"job_ids": [A, B]}, headers=auth
    ).json()
    assert ok == {
        "ok": True,
        "members": [A, B],
        "settings_hash": "h1",
        "differences": [],
        "repeated_questions": 1,
    }

    other = Seed(C, space=KEY)
    other.pair("cb-q5")
    other.answer("cb-q5", M1, "with", "correct")
    other.save(
        params={
            "settings_hash": "h2",
            "settings_snapshot": {"judge_policy": "strict", "limit": 5},
        },
        created_at=T0 + timedelta(hours=4),
    )
    with session_scope() as session:
        a = session.get(Job, A)
        assert a is not None
        a.params = {
            **a.params,
            "settings_snapshot": {"judge_policy": "lenient", "limit": 9},
        }
    found = client.post(
        "/console/report/combined/check", json={"job_ids": [A, C]}, headers=auth
    ).json()
    assert found["ok"] is False and found["settings_hash"] is None
    assert found["differences"] == [
        {
            "field": "judge_policy",
            "values": [
                {"job_id": A, "value": "lenient"},
                {"job_id": C, "value": "strict"},
            ],
        }
    ]
    refused = client.post(
        "/console/report/combined", json={"job_ids": [A, C]}, headers=auth
    )
    assert refused.status_code == 422
    assert refused.json()["differences"] == found["differences"]

    running = Seed(D, space=KEY)
    running.save(state=JobState.RUNNING.value, params=_params([J1]))
    busy = client.post(
        "/console/report/combined/check", json={"job_ids": [A, D]}, headers=auth
    ).json()
    assert [d["field"] for d in busy["differences"]] == ["state", "measured"]

    alone = client.post(
        "/console/report/combined", json={"job_ids": [A, A]}, headers=auth
    )
    assert alone.status_code == 422
    missing = client.post(
        "/console/report/combined", json={"job_ids": [A, "nope"]}, headers=auth
    )
    assert missing.status_code == 404


def test_jobs_without_a_hash_compare_judging_and_runs(
    client: TestClient, clean: Any
) -> None:
    auth = console_auth(client, KEY)
    for job, panel, docs, hours in ((A, [J1], 2, 0), (B, [J1], 2, 1), (C, [J2], 3, 2)):
        seed = Seed(job, space=KEY)
        seed.pair(f"cb-{job}")
        seed.answer(
            f"cb-{job}",
            M1,
            "with",
            "correct",
            params={"context_docs": docs, "denial_rounds": 3},
        )
        seed.save(params={"judge_panel": panel}, created_at=T0 + timedelta(hours=hours))
    same = client.post(
        "/console/report/combined/check", json={"job_ids": [A, B]}, headers=auth
    ).json()
    assert same["ok"] is True and same["settings_hash"] is None
    differ = client.post(
        "/console/report/combined/check", json={"job_ids": [A, C]}, headers=auth
    ).json()
    fields = [d["field"] for d in differ["differences"]]
    assert fields == ["judge_panel", "runs: model_with_context / direct / " + M1]
    assert differ["differences"][1]["values"][1]["value"] == [
        {"context_docs": 3, "denial_rounds": 3}
    ]


def test_members_are_flattened_added_and_dropped(
    client: TestClient, clean: Any
) -> None:
    auth, _ = _seed_pair(client)
    extra = Seed(C, space=KEY)
    extra.pair("cb-q5")
    extra.answer("cb-q5", M1, "with", "correct")
    extra.save(params=_params([J1]), created_at=T0 + timedelta(hours=5))
    more = Seed(D, space=KEY)
    more.pair("cb-q6")
    more.answer("cb-q6", M1, "with", "correct")
    more.save(params=_params([J1]), created_at=T0 + timedelta(hours=6))

    first = _create(client, auth, A, B)["job_id"]
    assert _report(client, auth, first)["run"]["questions"] == 4
    # A combined run as a member stands for its members.
    second = _create(client, auth, first, C)["job_id"]
    with session_scope() as session:
        assert combined_view.member_ids(session, second) == [A, B, C]

    grown = client.post(
        f"/console/report/combined/{first}/members",
        json={"job_ids": [D, A]},
        headers=auth,
    )
    assert grown.status_code == 200, grown.text
    assert grown.json()["combined"]["members"] == 3
    assert _report(client, auth, first)["run"]["questions"] == 5
    not_combined = client.post(
        f"/console/report/combined/{A}/members", json={"job_ids": [D]}, headers=auth
    )
    assert not_combined.status_code == 422

    assert client.delete(f"/console/report/runs/{D}", headers=auth).status_code == 204
    with session_scope() as session:
        assert combined_view.member_ids(session, first) == [A, B]
    assert _report(client, auth, first)["run"]["questions"] == 4

    assert client.delete(f"/console/report/runs/{B}", headers=auth).status_code == 204
    with session_scope() as session:
        # One member left: the record goes; the other keeps A and C.
        assert session.get(Job, first) is None
        assert combined_view.member_ids(session, second) == [A, C]
        assert (
            session.scalars(
                select(CombinedMember).where(CombinedMember.member_job_id == B)
            ).all()
            == []
        )


def test_a_members_new_verdict_reaches_the_combined_run(
    client: TestClient, clean: Any
) -> None:
    auth, ids = _seed_pair(client)
    cid = _create(client, auth, A, B)["job_id"]
    assert _report(client, auth, cid)["models"][0]["right_alone"] == 2
    overridden = client.post(
        f"/console/results/{ids['a_q1_alone']}/verdict",
        json={"verdict": "correct", "reasoning": "it is right"},
        headers=auth,
    )
    assert overridden.status_code == 200, overridden.text
    assert _report(client, auth, cid)["models"][0]["right_alone"] == 3


def test_combined_downloads(client: TestClient, clean: Any) -> None:
    auth, _ = _seed_pair(client)
    cid = _create(client, auth, A, B)["job_id"]
    docx = client.get(f"/console/report/runs/{cid}/summary.docx", headers=auth)
    assert docx.status_code == 200
    with zipfile.ZipFile(io.BytesIO(docx.content)) as archive:
        text = archive.read("word/document.xml").decode()
    assert "Runs combined" in text
    assert "Questions asked in more than one run" in text

    xlsx = client.get(f"/console/report/runs/{cid}/export.xlsx", headers=auth)
    assert xlsx.status_code == 200
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(xlsx.content), read_only=True)
    assert book.sheetnames[:2] == ["Run", "Members"]
    members = list(book["Members"].iter_rows(values_only=True))
    assert [row[0] for row in members[1:]] == [A, B]
    answers = list(book["Answers"].iter_rows(values_only=True))
    assert answers[0][0] == "Job"
    judging = list(book["Judging"].iter_rows(values_only=True))
    header = judging[0]
    counted = [
        (row[0], row[header.index("Question id")], row[header.index("Judge")])
        for row in judging[1:]
        if row[header.index("Counted")] == "yes"
    ]
    # q2 alone is counted from A only, though B graded it too.
    assert (A, "cb-q2", J1) in counted
    assert not [c for c in counted if c[0] == B and c[1] == "cb-q2"]


def test_a_combined_run_is_never_queued_or_listed_as_a_job(
    client: TestClient, clean: Any
) -> None:
    auth, _ = _seed_pair(client)
    cid = _create(client, auth, A, B)["job_id"]
    with session_scope() as session:
        job = session.get(Job, cid)
        assert job is not None
        assert (job.kind, job.state) == (JobKind.COMBINED.value, "succeeded")
        assert job.params["members"] == [A, B]
        assert job.params["settings_hash"] == "h1"
    jobs = client.get("/console/jobs", headers=auth).json()
    assert cid not in {j["id"] for j in jobs}
    target = client.get(f"/targets/{KEY}", headers=AUTH).json()
    assert target["last_job"]["id"] != cid
    assert client.post(f"/jobs/{cid}/cancel", headers=AUTH).status_code == 409


def test_combine_periods_are_validated_and_kept(client: TestClient, clean: Any) -> None:
    bad = client.put(
        f"/targets/{KEY}",
        json={"key": KEY, "url": "http://space.invalid", "combine_periods": ["5h"]},
        headers=AUTH,
    )
    assert bad.status_code == 422
    good = client.put(
        f"/targets/{KEY}",
        json={
            "key": KEY,
            "url": "http://space.invalid",
            "combine_periods": ["24h", "4h", "4h"],
        },
        headers=AUTH,
    )
    assert good.status_code == 200, good.text
    assert good.json()["combine_periods"] == ["4h", "24h"]


DAY = datetime(2026, 11, 2, tzinfo=UTC)


def _leaf(job: str, hours: float, settings_hash: str, **save: Any) -> None:
    seed = Seed(job, space=KEY)
    seed.pair(f"cb-{job}")
    seed.answer(f"cb-{job}", M1, "with", "correct")
    seed.save(
        params={"settings_hash": settings_hash},
        created_at=DAY + timedelta(hours=hours),
        **save,
    )


def test_the_ticker_combines_each_closed_period_once(
    client: TestClient, clean: Any
) -> None:
    console_auth(client, KEY, combine_periods=["24h"])
    _leaf(A, 6, "h1")
    _leaf(B, 18, "h1")
    _leaf(C, 10, "h2")
    now = DAY + timedelta(days=1, hours=1)
    with session_scope() as session:
        target = session.get(Target, KEY)
        assert target is not None
        made = combined.combine_due(session, target, now=now)
    assert len(made) == 1
    with session_scope() as session:
        job = session.get(Job, made[0])
        assert job is not None
        assert job.trigger == "auto"
        assert job.params["period"] == "24h"
        assert job.params["period_start"] == DAY.isoformat()
        assert job.params["title"] == "24h · 2026-11-02"
        assert combined_view.member_ids(session, job.id) == [A, B]

    with session_scope() as session:
        target = session.get(Target, KEY)
        assert target is not None
        assert combined.combine_due(session, target, now=now) == []
        session.delete(session.get(Job, made[0]))
    with session_scope() as session:
        target = session.get(Target, KEY)
        assert target is not None
        # A period dealt with is not combined again, even after a delete.
        assert combined.combine_due(session, target, now=now) == []


def test_the_ticker_waits_for_a_period_still_running(
    client: TestClient, clean: Any
) -> None:
    console_auth(client, KEY, combine_periods=["12h"])
    _leaf(A, 1, "h1")
    _leaf(B, 2, "h1")
    _leaf(D, 3, "h1", state=JobState.RUNNING.value)
    _leaf(C, 13, "h1")
    later = Seed("cb-job-e", space=KEY)
    later.pair("cb-e")
    later.answer("cb-e", M1, "with", "correct")
    later.save(params={"settings_hash": "h1"}, created_at=DAY + timedelta(hours=14))
    now = DAY + timedelta(days=1)
    with session_scope() as session:
        target = session.get(Target, KEY)
        assert target is not None
        assert combined.combine_due(session, target, now=now) == []
        running = session.get(Job, D)
        assert running is not None
        running.state = JobState.SUCCEEDED.value
    with session_scope() as session:
        target = session.get(Target, KEY)
        assert target is not None
        made = combined.combine_due(session, target, now=now)
        assert [combined_view.member_ids(session, m) for m in made] == [
            [A, B, D],
            [C, "cb-job-e"],
        ]
        assert target.combine_marks == {"12h": (DAY + timedelta(hours=12)).isoformat()}
