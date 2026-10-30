"""What the results tab's Details view reads: a pair's writer and entity-check
calls whichever pair of the call carries them, the job's filter decisions of
one kind, pairs by id, and one model's verdicts with the counted row marked."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from syft_benchmark.config import JobState, PairStatus
from syft_benchmark.db import Job, QaPair, Result, Run, session_scope
from syft_benchmark.db.models import WriterCall
from syft_benchmark.generation import decisions
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.recorded import PASSAGE_MARK
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE

from support import add_rows, console_auth, control_client

KEY = "pytest-report-details"
OTHER_KEY = "pytest-report-details-b"
JOB = "rd-job"
OTHER_JOB = "rd-other-job"
T0 = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
CONTEXT = "The council restored the Harbourton lighthouse."
PASSAGE = "Spring report. The council restored the Harbourton lighthouse. More."


pytestmark = pytest.mark.needs_db


@pytest.fixture
def auth(clean: None) -> dict[str, str]:
    headers = console_auth(control_client(), KEY)
    add_rows(Job(id=JOB, target=KEY, state=JobState.SUCCEEDED.value, created_at=T0))
    return headers


def _pair(pair_id: str, generator: str = "qa", **extra: Any) -> QaPair:
    return QaPair(
        id=pair_id,
        space=KEY,
        generator=generator,
        task_type=GENERATORS[generator].task_type,
        doc_id="d1",
        question=f"Question {pair_id}?",
        answer="Harbourton lighthouse",
        context=extra.pop("context", CONTEXT),
        status=extra.pop("status", PairStatus.ACTIVE.value),
        model="gen/model",
        question_hash=uuid.uuid4().hex,
        job_id=JOB,
        **extra,
    )


# --- a pair's calls ----------------------------------------------------------


def test_every_pair_of_a_call_carries_its_texts_and_passage(
    auth: dict[str, str],
) -> None:
    writer = {
        "call": "c1",
        "model": "gen/model",
        "system": "Write questions.",
        "user": f"Passage:\n{PASSAGE_MARK}\nWrite two.",
        "reply": "[...]",
        "passage": PASSAGE,
        "cost_usd": 0.01,
        "latency_s": 1.5,
    }
    check = {
        "call": "e1",
        "outcome": "kept",
        "model": "check/model",
        "system": "Check names.",
        "user": "Names?",
        "reply": "{}",
    }
    add_rows(
        _pair("w-1", meta={"writer": writer, "entity_check": check}),
        _pair(
            "w-2",
            meta={
                "writer": {"call": "c1"},
                "entity_check": {"call": "e1", "outcome": "kept"},
            },
        ),
        _pair("w-solo"),
    )
    client = control_client()

    second = client.get(f"/console/report/runs/{JOB}/pairs/w-2", headers=auth).json()

    call = second["writer_call"]
    assert call["call"] == "c1"
    assert call["passage"] == PASSAGE
    assert call["user"] == f"Passage:\n{PASSAGE}\nWrite two."
    assert call["system"] == "Write questions."
    assert call["reply"] == "[...]"
    assert call["cost_usd"] == 0.01
    assert second["entity_call"]["system"] == "Check names."
    assert second["entity_call"]["passage"] == ""
    solo = client.get(f"/console/report/runs/{JOB}/pairs/w-solo", headers=auth).json()
    assert solo["writer_call"] is None and solo["entity_call"] is None

    listed = client.get(f"/console/report/runs/{JOB}/generated", headers=auth).json()
    by_id = {item["id"]: item for item in listed["items"]}
    assert by_id["w-1"]["writer_call"] == by_id["w-2"]["writer_call"]


def test_a_call_kept_on_no_pair_is_read_from_the_log(auth: dict[str, str]) -> None:
    add_rows(
        WriterCall(
            id=uuid.uuid4().hex,
            job_id=JOB,
            call="c-logged",
            model="gen/model",
            passage=PASSAGE,
            system="Write questions.",
            system_digest="d",
            user=f"Passage:\n{PASSAGE_MARK}",
            reply="[...]",
            dropped={},
            created_at=T0,
        ),
        _pair("l-1", meta={"writer": {"call": "c-logged"}}),
        _pair("l-2", meta={"writer": {"call": "c-gone"}}),
    )
    client = control_client()

    logged = client.get(f"/console/report/runs/{JOB}/pairs/l-1", headers=auth).json()
    gone = client.get(f"/console/report/runs/{JOB}/pairs/l-2", headers=auth).json()

    assert logged["writer_call"]["user"] == f"Passage:\n{PASSAGE}"
    assert logged["writer_call"]["passage"] == PASSAGE
    assert gone["writer_call"]["call"] == "c-gone"
    assert gone["writer_call"]["user"] == ""
    assert gone["writer_call"]["passage"] == CONTEXT


def _logged(call: str, job: str = JOB, system: str = "") -> WriterCall:
    return WriterCall(
        id=uuid.uuid4().hex,
        job_id=job,
        call=call,
        model="gen/model",
        passage=PASSAGE,
        system=system,
        system_digest="d",
        user=f"Passage:\n{PASSAGE_MARK}",
        reply=f"reply of {call}",
        dropped={},
        created_at=T0,
    )


def test_logged_calls_are_read_in_a_fixed_number_of_queries(
    auth: dict[str, str],
) -> None:
    """The log is read for the pairs' own jobs, the system prompts in one go."""
    from sqlalchemy import event

    from syft_benchmark.generation.pairs import list_pairs
    from syft_benchmark.report import pair_calls

    add_rows(
        _logged("lc-1", system="Write questions."),
        _logged("lc-2"),
        _logged("lc-3"),
        _logged("lc-x", job=OTHER_JOB, system="Another build's prompt."),
        _pair("p-1", meta={"writer": {"call": "lc-1"}}),
        _pair("p-2", meta={"writer": {"call": "lc-2"}}),
        _pair("p-3", meta={"writer": {"call": "lc-3"}}),
        _pair("p-x", meta={"writer": {"call": "lc-x"}}),
    )
    views, _ = list_pairs(KEY, job=JOB)
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    with session_scope() as session:
        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            calls = pair_calls.pair_calls(session, KEY, views)
        finally:
            event.remove(engine, "before_cursor_execute", count)

    # The pairs carrying texts, the log rows, their system prompts.
    assert len(statements) == 3, statements
    systems = {pid: (calls[pid]["writer_call"] or {}).get("system") for pid in calls}
    assert systems == {
        "p-1": "Write questions.",
        "p-2": "Write questions.",
        "p-3": "Write questions.",
        "p-x": "",
    }


def test_a_call_is_looked_up_only_in_the_target_and_jobs_of_its_pairs(
    auth: dict[str, str],
) -> None:
    """A call id is the job's own: a pair of another job or target naming the
    same id does not lend its texts, and the lookup is scoped in SQL."""
    from sqlalchemy import event

    from syft_benchmark.generation.pairs import list_pairs
    from syft_benchmark.report import pair_calls

    texts = {"call": "dup", "model": "m", "system": "S", "user": "U", "reply": "R"}
    stranger = _pair("s-job", meta={"writer": texts, "entity_check": texts})
    stranger.job_id = OTHER_JOB
    foreign = _pair("s-target", meta={"writer": texts, "entity_check": texts})
    foreign.space = OTHER_KEY
    mine = _pair(
        "s-mine", meta={"writer": {"call": "dup"}, "entity_check": {"call": "dup"}}
    )
    add_rows(stranger, foreign, mine)
    views, _ = list_pairs(KEY, job=JOB)
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    with session_scope() as session:
        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            calls = pair_calls.pair_calls(session, KEY, views)
        finally:
            event.remove(engine, "before_cursor_execute", count)

    assert calls["s-mine"]["writer_call"] == {
        "call": "dup",
        "model": "",
        "system": "",
        "user": "",
        "reply": "",
        "passage": CONTEXT,
        "cost_usd": None,
        "latency_s": None,
    }
    assert calls["s-mine"]["entity_call"] is None
    lookups = [s for s in statements if "FROM qa_pairs" in s]
    assert len(lookups) == 2, statements
    for sql in lookups:
        assert "qa_pairs.space =" in sql and "qa_pairs.job_id IN" in sql, sql


def test_a_jobless_pair_finds_its_call_only_in_its_own_unit(
    auth: dict[str, str],
) -> None:
    """A pair whose job is gone looks its call up among the jobless pairs of
    its own unit, not every jobless pair of the target."""
    from sqlalchemy import event, select

    from syft_benchmark.report import pair_calls

    def texts(system: str) -> dict[str, str]:
        return {"call": "oc", "model": "m", "system": system, "user": "U"}

    carrier = _pair("o-carrier", chunk_id="u1", meta={"writer": texts("Mine")})
    other = _pair("o-other", chunk_id="u2", meta={"writer": texts("Not mine")})
    mine = _pair("o-mine", chunk_id="u1", meta={"writer": {"call": "oc"}})
    for row in (carrier, other, mine):
        row.job_id = None
    add_rows(carrier, other, mine)
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    with session_scope() as session:
        rows = list(session.scalars(select(QaPair).where(QaPair.id == "o-mine")))
        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            calls = pair_calls.writer_calls(session, KEY, rows)
        finally:
            event.remove(engine, "before_cursor_execute", count)

    assert calls["oc"]["system"] == "Mine"
    lookups = [s for s in statements if "FROM qa_pairs" in s]
    assert len(lookups) == 1, statements
    assert "qa_pairs.chunk_id IN" in lookups[0], lookups[0]
    assert "qa_pairs.job_id IS NULL" in lookups[0], lookups[0]


def test_pairs_are_read_by_id_whichever_job_wrote_them(auth: dict[str, str]) -> None:
    orphan = _pair("i-3", meta={"writer": {"call": "c-gone"}})
    orphan.job_id = "deleted-writer"
    add_rows(_pair("i-1"), _pair("i-2"), orphan)
    client = control_client()

    got = client.get(
        f"/console/report/runs/{JOB}/pairs",
        params={"ids": "i-1,i-3,other"},
        headers=auth,
    )

    assert got.status_code == 200, got.text
    body = got.json()
    assert sorted(item["id"] for item in body["items"]) == ["i-1", "i-3"]
    assert body["total"] == 2
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["i-3"]["writer_call"]["call"] == "c-gone"
    assert "entity_call" in by_id["i-1"]

    too_many = ",".join(f"x-{n}" for n in range(201))
    refused = client.get(
        f"/console/report/runs/{JOB}/pairs", params={"ids": too_many}, headers=auth
    )
    assert refused.status_code == 422
    unknown = client.get(
        "/console/report/runs/nope/pairs", params={"ids": "i-1"}, headers=auth
    )
    assert unknown.status_code == 404


# --- filter decisions of one kind -------------------------------------------


def test_filter_decisions_are_read_for_one_kind(auth: dict[str, str]) -> None:
    def screened(outcome: str) -> dict[str, Any]:
        record = {"job_id": JOB, "stage": "web_check", "outcome": outcome}
        return {decisions.SCREENING: [record]}

    add_rows(
        _pair("f-qa", meta=screened("kept")),
        _pair("f-mcq", "mcq", meta=screened("removed")),
    )

    body = (
        control_client()
        .get(
            f"/console/report/runs/{JOB}/filter",
            params={"generator": "mcq"},
            headers=auth,
        )
        .json()
    )

    assert [item["qa_id"] for item in body["items"]] == ["f-mcq"]
    assert body["total"] == 1
    assert body["counts"]["removed"] == 1 and body["counts"]["kept"] == 0


# --- one model's verdicts ----------------------------------------------------


def _verdicts(*rows: tuple[str, str, str, int]) -> list[Any]:
    """Runs and results of ``JOB`` on ``r-1``: (model, judge, verdict, minute)."""
    out: list[Any] = []
    for model, judge, verdict, minute in rows:
        run_id = f"run-{model}-{judge}"
        out += [
            Run(
                id=run_id,
                space=KEY,
                job_id=JOB,
                context_mode="closed_book",
                block="direct",
                model=model,
                judge_model=judge,
            ),
            Result(
                id=f"res-{model}-{judge}",
                run_id=run_id,
                qa_id="r-1",
                space=KEY,
                answer="Harbourton lighthouse",
                verdict=verdict,
                judge_model=judge,
                created_at=T0 + timedelta(minutes=minute),
            ),
        ]
    return out


def test_results_of_one_model_mark_the_counted_row(auth: dict[str, str]) -> None:
    add_rows(_pair("r-1"))
    add_rows(
        *_verdicts(
            ("m/one", "z/judge", "correct", 1),
            ("m/one", "a/judge", "hallucinate", 2),
            ("m/two", "z/judge", "correct", 3),
        )
    )
    client = control_client()
    query = {"qa_id": "r-1", "job": JOB, "model": "m/one"}

    body = client.get("/console/results", params=query, headers=auth).json()

    assert body["total"] == 2
    counted = {item["judge_model"]: item["counted"] for item in body["items"]}
    # The first judge to grade is the primary: not the first by name.
    assert counted == {"z/judge": True, "a/judge": False}
    unscoped = client.get(
        "/console/results", params={"qa_id": "r-1"}, headers=auth
    ).json()
    assert {item["counted"] for item in unscoped["items"]} == {None}

    add_rows(*_verdicts(("m/one", OWNER_OVERRIDE, "abstain", 4)))
    body = client.get("/console/results", params=query, headers=auth).json()
    counted = {item["judge_model"]: item["counted"] for item in body["items"]}
    assert counted == {"z/judge": False, "a/judge": False, OWNER_OVERRIDE: True}


def _answer(
    qa_id: str, judge: str, verdict: str, minute: int, arm: str = "closed_book"
) -> list[Any]:
    """One verdict of ``m/one`` under ``JOB``, on its own run."""
    run_id = f"run-{qa_id}-{judge}-{arm}"
    return [
        Run(
            id=run_id,
            space=KEY,
            job_id=JOB,
            context_mode=arm,
            block="direct",
            model="m/one",
            judge_model=judge,
        ),
        Result(
            id=f"res-{qa_id}-{judge}-{arm}",
            run_id=run_id,
            qa_id=qa_id,
            space=KEY,
            answer="Harbourton lighthouse",
            verdict=verdict,
            judge_model=judge,
            created_at=T0 + timedelta(minutes=minute),
        ),
    ]


def test_a_retired_arms_row_is_never_counted(auth: dict[str, str]) -> None:
    add_rows(_pair("r-1"))
    add_rows(
        *_answer("r-1", "z/judge", "correct", 1),
        *_answer("r-1", "z/judge", "correct", 2, arm="open_book"),
    )

    body = (
        control_client()
        .get(
            "/console/results",
            params={"qa_id": "r-1", "job": JOB, "model": "m/one"},
            headers=auth,
        )
        .json()
    )

    counted = {item["id"]: item["counted"] for item in body["items"]}
    assert counted == {
        "res-r-1-z/judge-closed_book": True,
        "res-r-1-z/judge-open_book": False,
    }


def test_the_counted_rows_follow_the_figures_judge_order(
    auth: dict[str, str],
) -> None:
    """``counted_ids`` orders the judges without the aggregate, as it does."""
    from syft_benchmark.report import run_questions, run_view
    from syft_benchmark.report.job_params import JUDGE_PANEL

    add_rows(_pair("r-1"), _pair("r-2"))
    add_rows(
        # The earliest verdict, in a retired arm: it does not order the judges.
        *_answer("r-1", "x/judge", "hallucinate", 0, arm="open_book"),
        *_answer("r-1", "c/judge", "abstain", 1),
        *_answer("r-1", "b/judge", "hallucinate", 2),
        *_answer("r-2", "p/judge", "correct", 3),
        *_answer("r-1", "x/judge", "hallucinate", 5),
    )
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        job.state = JobState.RUNNING.value
        job.params = {JUDGE_PANEL: ["p/judge"]}

    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        judges = run_view.counting_judges(session, job)
        figures = run_view.aggregate(session, job)
        counted = run_questions.counted_ids(session, job, {"r-1", "r-2"})

    assert judges == ["p/judge", "c/judge", "b/judge", "x/judge"]
    assert figures["judges"] == judges
    assert counted == {"res-r-1-c/judge-closed_book", "res-r-2-p/judge-closed_book"}
    by_qa = {entry["qa_id"]: entry["models"]["m/one"] for entry in figures["questions"]}
    assert by_qa["r-1"][0] == "abstain", "the figures count the same row"
