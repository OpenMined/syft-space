"""The results read API: one run's figures, its questions and its document."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from syft_benchmark.config import (
    JobState,
    JudgePolicy,
    PairStatus,
    StatusReason,
    get_settings,
)
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db import (
    Job,
    QaPair,
    Result,
    Run,
    RunAggregate,
    Target,
    session_scope,
)
from syft_benchmark.report import run_view

TOKEN = "test-run-view-token"
KEY = "pytest-run-view-a"
KEY2 = "pytest-run-view-b"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
JOB = "rv-job"
T0 = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)
M1, M2 = "vendor/model-one", "other/model-two"
J1, J2 = "judge/primary", "judge/second"


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


pytestmark = pytest.mark.skipif(
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
def client() -> TestClient:
    conf = get_settings().model_copy(update={"control_token": TOKEN})
    return TestClient(create_app(conf))


def _console(client: TestClient, key: str = KEY) -> dict[str, str]:
    body = TargetSpec(key=key, url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{key}", json=body, headers=AUTH).status_code == 200
    minted = client.post(f"/targets/{key}/session", headers=AUTH)
    assert minted.status_code == 200, minted.text
    return {"Authorization": f"Bearer {minted.json()['token']}"}


class Seed:
    """Writes a job's pairs and answers with a running clock."""

    def __init__(self, job: str = JOB, *, space: str = KEY) -> None:
        self.job = job
        self.space = space
        self.clock = T0
        self.rows: list[Any] = []
        self.n = 0
        self.response_type = ""

    def pair(self, qa: str, *, generator: str = "qa", **extra: Any) -> None:
        self.rows.append(
            QaPair(
                id=qa,
                space=self.space,
                generator=generator,
                document_title=extra.pop("title", f"Article {qa}"),
                file_name=extra.pop("file_name", f"{qa}.md"),
                doc_id=extra.pop("doc_id", f"doc-{qa}"),
                question=extra.pop("question", f"Question {qa}?"),
                answer=extra.pop("answer", f"Answer {qa}"),
                context=f"Context of {qa}.",
                status=extra.pop("status", PairStatus.ACTIVE.value),
                model="gen/model",
                question_hash=qa,
                **extra,
            )
        )

    def answer(
        self,
        qa: str,
        model: str,
        arm: str,
        verdict: str,
        *,
        judge: str = J1,
        block: str = "direct",
        answer: str = "an answer",
        extra: dict[str, Any] | None = None,
        hit: bool | None = None,
        rank: int | None = None,
        retrieved: list[dict[str, Any]] | None = None,
        reasoning: str = "",
        params: dict[str, Any] | None = None,
    ) -> str:
        self.n += 1
        self.clock += timedelta(seconds=1)
        run_id = f"{self.job}-run-{self.n}"
        result_id = f"{self.job}-res-{self.n}"
        mode = {"alone": "closed_book", "with": "model_with_context"}.get(arm, arm)
        self.rows.append(
            Run(
                id=run_id,
                space=self.space,
                job_id=self.job,
                context_mode=mode,
                block=block,
                model=model,
                judge_model=judge,
                params=(
                    params
                    if params is not None
                    else {"context_docs": 2, "denial_rounds": 3}
                ),
            )
        )
        self.rows.append(
            Result(
                id=result_id,
                run_id=run_id,
                qa_id=qa,
                space=self.space,
                answer=answer,
                endpoint_response_type=self.response_type,
                verdict=verdict,
                reasoning=reasoning,
                judge_model=judge,
                model=model,
                retrieval_hit=hit,
                retrieval_rank=rank,
                retrieved=retrieved or [],
                extra=extra or {},
                created_at=self.clock,
            )
        )
        return result_id

    def save(self, state: str = JobState.SUCCEEDED.value, **job: Any) -> None:
        with session_scope() as session:
            session.add(
                Job(
                    id=self.job,
                    target=self.space,
                    state=state,
                    created_at=job.pop("created_at", T0),
                    finished_at=T0 + timedelta(hours=1),
                    **job,
                )
            )
            pairs = [r for r in self.rows if isinstance(r, QaPair)]
            session.add_all(pairs)
            session.flush()
            session.add_all([r for r in self.rows if isinstance(r, Run)])
            session.flush()
            session.add_all([r for r in self.rows if isinstance(r, Result)])


def _report(client: TestClient, auth: dict[str, str], job: str = JOB) -> Any:
    got = client.get(f"/console/report/runs/{job}", headers=auth)
    assert got.status_code == 200, got.text
    return got.json()


def _model(report: dict[str, Any], model: str) -> dict[str, Any]:
    return next(m for m in report["models"] if m["model"] == model)


def test_counted_verdict_prefers_override_then_primary(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.pair("q2")
    judged = seed.answer("q1", M1, "alone", "hallucinate", judge=J1)
    seed.answer("q1", M1, "alone", "correct", judge=J2)
    seed.answer("q1", M1, "with", "correct", judge=J1)
    # No primary verdict here: the next judge counts.
    seed.answer("q2", M1, "alone", "correct", judge=J2)
    seed.answer("q2", M1, "with", "abstain", judge=J1)
    seed.save()

    report = _report(client, auth)
    assert report["judges"] == [J1, J2]
    m1 = _model(report, M1)
    assert (m1["right_alone"], m1["graded_alone"]) == (1, 2)
    assert (m1["right_with"], m1["graded_with"]) == (1, 2)
    assert m1["rate_alone"] == 0.5 and m1["lift"] == 0
    assert m1["checks"]["answers"] == 1 and m1["checks"]["judges_agreed"] == 0

    overridden = client.post(
        f"/console/results/{judged}/verdict",
        json={"verdict": "correct", "reasoning": "it is right"},
        headers=auth,
    )
    assert overridden.status_code == 200, overridden.text
    m1 = _model(_report(client, auth), M1)
    assert m1["right_alone"] == 2 and m1["rate_alone"] == 1.0
    assert m1["lift"] == -50

    detail = client.get(
        f"/console/report/runs/{JOB}/questions/q1", params={"model": M1}, headers=auth
    ).json()
    assert detail["question"]["overridden"] is True
    assert detail["arms"]["alone"]["verdict"] == "correct"
    assert detail["arms"]["alone"]["result_id"] == judged
    assert detail["arms"]["alone"]["override"]["verdict"] == "correct"
    assert [j["model"] for j in detail["judges"]] == [J1, J2]
    assert detail["judges"][0]["primary"] is True
    assert detail["judges"][0]["alone"] == "hallucinate"
    assert detail["judges_agreed"] is False


def test_pending_and_technical_stay_out_of_rates(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    for qa in ("q1", "q2", "q3", "q4"):
        seed.pair(qa)
    seed.answer("q1", M1, "with", "correct")
    seed.answer("q2", M1, "with", "pending", judge="")
    seed.answer("q3", M1, "with", "technical")
    seed.answer("q4", M1, "with", "hallucinate", answer="ERROR: timed out")
    seed.save()

    m1 = _model(_report(client, auth), M1)
    assert m1["graded_with"] == 1 and m1["rate_with"] == 1.0
    assert (m1["pending"], m1["technical"]) == (1, 2)
    assert m1["tally"]["with"] == {
        "correct": 1,
        "abstain": 0,
        "hallucinate": 0,
        "web_sourced": 0,
        "pending": 1,
        "technical": 2,
        "graded": 1,
    }
    assert m1["asked"] == 4


def test_trick_questions_feed_only_the_trick_check(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.pair("t1", generator=run_view.TRICK_GENERATOR)
    seed.pair("t2", generator=run_view.TRICK_GENERATOR)
    seed.answer("q1", M1, "with", "correct")
    seed.answer("t1", M1, "with", "hallucinate")
    seed.answer("t2", M1, "with", "abstain")
    seed.answer("t1", M1, "alone", "abstain")
    seed.save()

    report = _report(client, auth)
    m1 = _model(report, M1)
    assert m1["graded_with"] == 1 and m1["asked"] == 1
    checks = m1["checks"]
    assert (checks["trick_asked"], checks["trick_answered"]) == (2, 1)
    assert (checks["trick_alone_asked"], checks["trick_alone_answered"]) == (1, 0)
    assert report["funnel"]["trick"] == 2 and report["run"]["questions"] == 1
    assert report["method"]["trick"] == 2

    listed = client.get(
        f"/console/report/runs/{JOB}/questions", params={"model": M1}, headers=auth
    ).json()
    assert [row["qa_id"] for row in listed["items"]] == ["q1"]


def test_an_excluded_question_leaves_the_figures_but_stays_listed(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.pair("q2")
    seed.answer("q1", M1, "with", "correct")
    seed.answer("q2", M1, "with", "hallucinate")
    seed.save()
    assert _model(_report(client, auth), M1)["rate_with"] == 0.5

    put = client.put(
        f"/console/report/runs/{JOB}/questions/q2/exclusion",
        json={"reason": "ambiguous"},
        headers=auth,
    )
    assert put.status_code == 200, put.text
    assert put.json()["question"]["excluded"] is True
    assert put.json()["exclusion"]["reason"] == "ambiguous"

    report = _report(client, auth)
    assert _model(report, M1)["rate_with"] == 1.0
    assert report["run"]["questions"] == 1 and report["funnel"]["asked"] == 1

    url = f"/console/report/runs/{JOB}/questions"
    every = client.get(url, params={"model": M1}, headers=auth).json()
    assert [(r["qa_id"], r["excluded"]) for r in every["items"]] == [
        ("q1", False),
        ("q2", True),
    ]
    only = client.get(url, params={"model": M1, "excluded": "only"}, headers=auth)
    assert [r["qa_id"] for r in only.json()["items"]] == ["q2"]
    hidden = client.get(url, params={"model": M1, "excluded": "hide"}, headers=auth)
    assert hidden.json()["counts"]["all"] == 1

    assert (
        client.delete(
            f"/console/report/runs/{JOB}/questions/q2/exclusion", headers=auth
        ).status_code
        == 204
    )
    assert _model(_report(client, auth), M1)["rate_with"] == 0.5


def test_the_question_set_ignores_the_pairs_status_now(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1", status=PairStatus.RETIRED.value)
    seed.pair("q2", status=PairStatus.REJECTED.value)
    seed.answer("q1", M1, "with", "correct")
    seed.answer("q2", M1, "with", "correct")
    seed.save()
    report = _report(client, auth)
    assert report["run"]["questions"] == 2
    assert _model(report, M1)["graded_with"] == 2


def test_the_funnel_counts_only_what_never_took_part(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    # Asked, then rotated out: not removed.
    seed.pair(
        "q1",
        job_id=JOB,
        status=PairStatus.RETIRED.value,
        status_reason=StatusReason.ROTATION.value,
    )
    seed.pair(
        "q2",
        job_id=JOB,
        status=PairStatus.REJECTED.value,
        status_reason=StatusReason.GROUNDING.value,
    )
    seed.pair(
        "q3",
        job_id=JOB,
        status=PairStatus.REJECTED.value,
        status_reason=StatusReason.GROUNDING.value,
    )
    seed.pair("q4", job_id=JOB, status=PairStatus.REJECTED.value)
    seed.pair(
        "t1",
        job_id=JOB,
        generator=run_view.TRICK_GENERATOR,
        status=PairStatus.REJECTED.value,
    )
    seed.answer("q1", M1, "with", "correct")
    seed.save()

    funnel = _report(client, auth)["funnel"]
    assert funnel["written"] == 4
    assert funnel["removed"] == {"grounding": 2, "other": 1}
    assert funnel["removed_total"] == 3
    assert funnel["asked"] == 1

    other = Seed("rv-reuse")
    other.answer("q1", M1, "with", "correct")
    other.save()
    funnel = _report(client, auth, "rv-reuse")["funnel"]
    assert funnel["written"] is None and funnel["removed_total"] is None


def test_groups_counts_and_paging(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    seed = Seed()
    outcomes = {
        "q1": ("hallucinate", "correct"),  # fixed
        "q2": ("correct", "correct"),  # either
        "q3": ("abstain", "abstain"),  # still
        "q4": ("correct", "hallucinate"),  # worse
        "q5": ("hallucinate", "correct"),  # fixed
    }
    for qa in outcomes:
        seed.pair(qa, generator="qa" if qa == "q5" else "numeric_masking")
    for qa, (alone, with_) in outcomes.items():
        seed.answer(qa, M1, "alone", alone)
        seed.answer(qa, M1, "with", with_)
    seed.save()

    report = _report(client, auth)
    assert _model(report, M1)["groups"] == {
        "fixed": 2,
        "either": 1,
        "still": 1,
        "worse": 1,
    }
    kinds = _model(report, M1)["kinds"]
    # Registry order, not lift: numeric_masking comes before qa.
    assert [k["generator"] for k in kinds] == ["numeric_masking", "qa"]
    assert kinds[0]["rate_alone"] == 0.5 and kinds[0]["graded_with"] == 4
    assert kinds[1]["lift"] == 100

    url = f"/console/report/runs/{JOB}/questions"
    page = client.get(
        url, params={"model": M1, "limit": 2, "offset": 2}, headers=auth
    ).json()
    assert [r["n"] for r in page["items"]] == [3, 4]
    assert page["total"] == 5
    assert page["counts"] == {"all": 5, "fixed": 2, "either": 1, "still": 1, "worse": 1}

    fixed = client.get(url, params={"model": M1, "group": "fixed"}, headers=auth)
    assert [r["qa_id"] for r in fixed.json()["items"]] == ["q1", "q5"]
    assert fixed.json()["counts"]["all"] == 5

    kind = client.get(url, params={"model": M1, "generator": "qa"}, headers=auth)
    assert kind.json()["counts"] == {
        "all": 1,
        "fixed": 1,
        "either": 0,
        "still": 0,
        "worse": 0,
    }
    found = client.get(url, params={"model": M1, "q": "ANSWER q3"}, headers=auth)
    assert [r["qa_id"] for r in found.json()["items"]] == ["q3"]

    assert client.get(url, params={"model": "nobody"}, headers=auth).status_code == 404
    assert (
        client.get(url, params={"model": M1, "limit": 101}, headers=auth).status_code
        == 422
    )


def test_checks_from_the_extra_blocks(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    seed = Seed()
    for qa in ("q1", "q2"):
        seed.pair(qa)
    seed.answer("q1", M1, "with", "correct", hit=True, rank=1)
    seed.answer("q2", M1, "with", "correct", hit=False)
    seed.answer(
        "q1",
        M1,
        "with",
        "correct",
        block="denial_loop",
        extra={"denial": {"rounds": 3, "flipped": False, "limit": 3, "log": []}},
    )
    seed.answer(
        "q2",
        M1,
        "with",
        "correct",
        block="denial_loop",
        extra={"denial": {"rounds": 2, "flipped": True, "flip_round": 2, "limit": 3}},
    )
    seed.answer(
        "q1",
        M1,
        "with",
        "correct",
        block="monte_carlo",
        extra={
            "monte_carlo": {
                "trials": 4,
                "accuracy": 0.75,
                "consistency": 0.5,
                "by_temperature": {"0.1": 1.0, "0.9": 0.5},
            }
        },
    )
    seed.save()

    checks = _model(_report(client, auth), M1)["checks"]
    assert checks["challenged"] == 2 and checks["denial_limit"] == 3
    assert checks["held_by_round"] == [1.0, 0.5, 0.5]
    assert checks["kept_right"] == 0.5
    assert checks["repeated"] == 1 and checks["same_answer"] == 0.5
    assert checks["by_temperature"] == [
        {"t": 0.1, "accuracy": 1.0},
        {"t": 0.9, "accuracy": 0.5},
    ]
    assert (checks["searched"], checks["missed"], checks["search_found"]) == (
        2,
        1,
        0.5,
    )

    detail = client.get(
        f"/console/report/runs/{JOB}/questions/q2", params={"model": M1}, headers=auth
    ).json()
    assert detail["arms"]["with"]["denial"] == {
        "rounds": 2,
        "flipped": True,
        "flip_round": 2,
        "limit": 3,
    }
    assert detail["arms"]["with"]["retrieval"] == {
        "hit": False,
        "rank": None,
        "context_docs": 2,
    }
    assert detail["arms"]["alone"] is None


def test_each_judge_carries_its_reasoning(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.answer("q1", M1, "alone", "correct", judge=J1, reasoning="old")
    seed.answer("q1", M1, "alone", "abstain", judge=J1, reasoning="J1 alone")
    seed.answer("q1", M1, "with", "correct", judge=J1, reasoning="J1 with")
    seed.answer("q1", M1, "alone", "correct", judge=J2, reasoning="J2 alone")
    seed.answer(
        "q1", M1, "with", "correct", judge=J2, block="denial_loop", reasoning="no"
    )
    seed.save()

    detail = client.get(
        f"/console/report/runs/{JOB}/questions/q1", params={"model": M1}, headers=auth
    ).json()
    j1, j2 = detail["judges"]
    assert (j1["alone"], j1["alone_reasoning"]) == ("abstain", "J1 alone")
    assert j1["with_reasoning"] == "J1 with"
    assert j2["alone_reasoning"] == "J2 alone"
    assert (j2["with"], j2["with_reasoning"]) == (None, None)


def test_method_reports_denial_rounds_and_repeats(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    plain = Seed("rv-plain")
    plain.pair("p1")
    plain.answer("p1", M1, "with", "correct")
    plain.save()
    method = _report(client, auth, "rv-plain")["method"]
    assert method["denial_rounds"] is None and method["repeats"] is None

    # The limit seen in the answers wins over the snapshot; the repeats come
    # from the snapshot of the monte_carlo runs.
    seed = Seed()
    seed.pair("q1")
    seed.answer("q1", M1, "with", "correct")
    seed.answer(
        "q1",
        M1,
        "with",
        "correct",
        block="denial_loop",
        extra={"denial": {"rounds": 5, "flipped": False, "limit": 5}},
    )
    seed.answer(
        "q1",
        M1,
        "with",
        "correct",
        block="monte_carlo",
        params={
            "denial_rounds": 3,
            "monte_carlo_trials": 2,
            "monte_carlo_temperatures": [0.7, 0.0, 1],
        },
        extra={"monte_carlo": {"trials": 5, "by_temperature": {"0.0": 1.0}}},
    )
    seed.save()
    method = _report(client, auth)["method"]
    assert method["denial_rounds"] == 5
    assert method["repeats"] == {"trials": 2, "temperatures": [0.0, 0.7, 1.0]}


def test_method_falls_back_when_one_source_is_missing(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.answer("q1", M1, "with", "correct")
    seed.answer(
        "q1",
        M1,
        "with",
        "correct",
        block="denial_loop",
        params={"denial_rounds": 4},
        extra={"denial": {"rounds": 1, "flipped": True, "flip_round": 1}},
    )
    seed.answer(
        "q1",
        M1,
        "with",
        "correct",
        block="monte_carlo",
        params={},
        extra={
            "monte_carlo": {
                "trials": 5,
                "by_temperature": {"0.2": 1.0, "0.8": 0.5},
            }
        },
    )
    seed.save()
    method = _report(client, auth)["method"]
    assert method["denial_rounds"] == 4
    assert method["repeats"] == {"trials": 3, "temperatures": [0.2, 0.8]}


def test_fragments_mark_the_source(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1", file_name="a.md", title="Article A")
    seed.pair("q2", file_name="b.md", title="Article B")
    docs = [
        {"file_name": "b.md", "score": 0.9, "content": "beta"},
        {"file_name": "a.md", "score": 0.8, "content": "alpha"},
        {"file_name": "c.md", "score": 0.1, "content": "gamma"},
    ]
    seed.answer("q1", M1, "with", "correct", hit=True, rank=2, retrieved=docs)
    seed.answer("q2", M1, "with", "correct")
    seed.save()
    got = client.get(
        f"/console/report/runs/{JOB}/questions/q1/fragments",
        params={"model": M1},
        headers=auth,
    )
    assert got.status_code == 200, got.text
    assert got.json() == [
        {
            "file_name": "b.md",
            "document_title": "Article B",
            "score": 0.9,
            "content": "beta",
            "is_source": False,
        },
        {
            "file_name": "a.md",
            "document_title": "Article A",
            "score": 0.8,
            "content": "alpha",
            "is_source": True,
        },
    ]


def test_runs_list_pages_and_keeps_in_progress_apart(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    for n in range(3):
        seed = Seed(f"rv-list-{n}")
        if n == 0:
            seed.pair("q1")
        seed.answer("q1", M1, "with", "correct")
        seed.save(created_at=T0 + timedelta(days=n))
    Seed("rv-running").save(state=JobState.RUNNING.value)
    Seed("rv-empty").save()

    url = "/console/report/runs"
    page = client.get(url, params={"limit": 2}, headers=auth).json()
    assert [r["job_id"] for r in page["in_progress"]] == ["rv-running"]
    assert [r["job_id"] for r in page["items"]] == ["rv-list-2", "rv-list-1"]
    assert page["total"] == 3
    assert page["items"][0]["models"][0]["rate_with"] == 1.0
    assert page["items"][0]["card_outdated"] is False

    only = client.get(url, params={"job_ids": "rv-list-0"}, headers=auth).json()
    assert [r["job_id"] for r in only["items"]] == ["rv-list-0"]
    assert only["in_progress"]
    rest = client.get(url, params={"exclude_job_ids": "rv-list-0"}, headers=auth)
    assert rest.json()["total"] == 2
    dated = client.get(
        url, params={"from": "2026-09-02", "to": "2026-09-02"}, headers=auth
    ).json()
    assert [r["job_id"] for r in dated["items"]] == ["rv-list-1"]

    with session_scope() as session:
        assert session.get(RunAggregate, "rv-list-2") is not None


def test_a_foreign_job_is_a_404(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    _console(client, KEY2)
    seed = Seed("rv-foreign", space=KEY2)
    seed.pair("f1")
    seed.answer("f1", M1, "with", "correct")
    seed.save()
    base = "/console/report/runs/rv-foreign"
    for path in (
        base,
        f"{base}/questions?model={M1}",
        f"{base}/questions/f1",
        f"{base}/questions/f1/fragments",
        f"{base}/summary.docx",
    ):
        assert client.get(path, headers=auth).status_code == 404, path
    listed = client.get("/console/report/runs", headers=auth).json()
    assert listed["items"] == []


def test_the_cache_follows_invalidation_and_skips_running_jobs(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.answer("q1", M1, "with", "hallucinate")
    seed.save(state=JobState.RUNNING.value)
    _report(client, auth)
    with session_scope() as session:
        assert session.get(RunAggregate, JOB) is None
        job = session.get(Job, JOB)
        assert job is not None
        job.state = JobState.SUCCEEDED.value
    _report(client, auth)
    with session_scope() as session:
        row = session.get(RunAggregate, JOB)
        assert row is not None and row.version == run_view.AGGREGATE_VERSION
        row.version = run_view.AGGREGATE_VERSION - 1
        row.payload = {**row.payload, "judges": ["stale"]}
    assert _report(client, auth)["judges"] == [J1]


def test_card_outdated_and_rebuilding_the_card(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    seed = Seed()
    seed.response_type = "raw"
    seed.pair("q1")
    seed.pair("q2")
    first = seed.answer("q1", M1, "with", "hallucinate")
    seed.answer("q2", M1, "with", "correct")
    seed.answer("q1", M1, "alone", "correct")
    seed.save(
        card={
            "models": [
                {"model": M1, "samples": 2, "accuracy": 0.5, "closed_accuracy": 1.0}
            ]
        }
    )
    assert _report(client, auth)["run"]["card_outdated"] is False

    client.post(
        f"/console/results/{first}/verdict",
        json={"verdict": "correct"},
        headers=auth,
    )
    assert _report(client, auth)["run"]["card_outdated"] is True

    # A preview build leaves the published baseline alone.
    built = client.post("/console/report", json={"job": JOB}, headers=auth)
    assert built.status_code == 200, built.text
    assert _report(client, auth)["run"]["card_outdated"] is True

    built = client.post(f"/console/report?job={JOB}&record=true", headers=auth)
    assert built.status_code == 200, built.text
    assert _report(client, auth)["run"]["card_outdated"] is False


def _primary_and_rate(
    configured: list[str], job: str = JOB
) -> tuple[str | None, float | None]:
    with session_scope() as session:
        row = session.get(Job, job)
        assert row is not None
        payload = run_view.compute(session, row, configured=configured)
        return payload["judges"][0], payload["models"][0]["rate_with"]


def _two_judges(seed: Seed) -> None:
    """J1 grades first and finds q1 right; J2 finds it wrong."""
    seed.response_type = "raw"
    seed.pair("q1")
    seed.answer("q1", M1, "with", "correct", judge=J1)
    seed.answer("q1", M1, "with", "hallucinate", judge=J2)


def test_settings_do_not_move_a_past_runs_primary(
    client: TestClient, clean: Any
) -> None:
    _console(client)
    seed = Seed()
    _two_judges(seed)
    seed.save(card={"instrument": {"judge": J2}})
    assert _primary_and_rate([J1, J2]) == (J2, 0.0)
    with session_scope() as session:
        row = session.get(Job, JOB)
        assert row is not None and row.params["primary_judge"] == J2
    assert _primary_and_rate([J1]) == (J2, 0.0)
    assert _primary_and_rate([]) == (J2, 0.0)


def test_the_jobs_own_panel_decides_the_primary(client: TestClient, clean: Any) -> None:
    _console(client)
    seed = Seed()
    _two_judges(seed)
    seed.save(
        params={"judge_panel": ["judge/absent", J2, J1]},
        card={"instrument": {"judge": J1}},
    )
    assert _primary_and_rate([J1, J2]) == (J2, 0.0)
    with session_scope() as session:
        row = session.get(Job, JOB)
        assert row is not None and "primary_judge" not in row.params


@pytest.mark.parametrize("record", [False, True])
def test_rebuilding_a_card_keeps_the_primary(
    client: TestClient, clean: Any, record: bool
) -> None:
    auth = _console(client)
    seed = Seed()
    _two_judges(seed)
    seed.save(card={"instrument": {"judge": J2}})
    before = _report(client, auth)
    assert before["judges"] == [J2, J1]
    for _ in range(2):
        built = client.post(
            "/console/report", json={"job": JOB, "record": record}, headers=auth
        )
        assert built.status_code == 200, built.text
        assert built.json()["instrument"]["judge"] == J2
    with session_scope() as session:
        row = session.get(Job, JOB)
        assert row is not None and row.params["primary_judge"] == J2
        assert row.card is not None and row.card["instrument"]["judge"] == J2
        session.execute(delete(RunAggregate).where(RunAggregate.job_id == JOB))
    after = _report(client, auth)
    assert after["judges"] == [J2, J1]
    assert after["models"] == before["models"]


def test_a_launch_keeps_the_judging_it_ran_with(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from syft_benchmark.control import jobs
    from syft_benchmark.control.schemas import Instrument, RunRequest
    from syft_benchmark.scheduler import Measured

    _console(client)
    with session_scope() as session:
        target = session.get(Target, KEY)
        assert target is not None
        target.instrument = {"judge_models": [J1, J2]}
    monkeypatch.setattr(jobs, "measure", lambda *a, **k: Measured())
    monkeypatch.setattr(
        jobs,
        "judge_pending",
        lambda *a, **k: SimpleNamespace(line=lambda: "", notes=[]),
    )

    request = RunRequest(evaluate=False, instrument=Instrument(judge_models=[J2, J1]))
    launches = [
        (
            f"{JOB}-run",
            "pipeline",
            request.model_dump(mode="json", exclude_none=True),
            [J2, J1],
        ),
        (f"{JOB}-judge", "judge", {}, [J1, J2]),
    ]
    for job_id, kind, params, _ in launches:
        with session_scope() as session:
            session.add(
                Job(id=job_id, target=KEY, kind=kind, state="queued", params=params)
            )
        jobs.execute(job_id)
    with session_scope() as session:
        for job_id, kind, params, panel in launches:
            row = session.get(Job, job_id)
            assert row is not None and row.state == JobState.SUCCEEDED.value, row
            policy = row.params.pop("judge_policy")
            assert policy in {p.value for p in JudgePolicy}
            assert row.params.pop("web_check_model") == ""
            assert row.params.pop("web_check_judge") == ""
            assert row.params.pop("cost")["usd"] is None
            assert row.params.pop("manual_status_priority") == "filter"
            timing = row.params.pop("timing")
            assert set(timing) == {
                "total_s",
                "phases",
                "passes",
                "calls",
                "concurrency",
            }
            if kind == "judge":
                assert [p["phase"] for p in timing["phases"]] == ["judge"]
            assert row.params == {**params, "judge_panel": panel}


def test_the_summary_document(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1", question="SECRET QUESTION TEXT")
    seed.answer("q1", M1, "alone", "hallucinate")
    seed.answer("q1", M1, "with", "correct")
    seed.answer("q1", M2, "with", "abstain")
    seed.save()
    got = client.get(f"/console/report/runs/{JOB}/summary.docx", headers=auth)
    assert got.status_code == 200, got.text
    assert got.headers["content-disposition"] == (
        f'attachment; filename="{KEY}-2026-09-01-0600.docx"'
    )
    with zipfile.ZipFile(io.BytesIO(got.content)) as docx:
        body = docx.read("word/document.xml").decode()
    assert M1 in body and "+100 pts" in body
    assert "SECRET QUESTION TEXT" not in body


def test_the_run_carries_its_timing(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    timing = {
        "total_s": 12.5,
        "phases": [{"phase": "evaluate", "s": 12.0}],
        "passes": [
            {
                "arm": "closed_book",
                "block": "direct",
                "model": M1,
                "s": 11.0,
                "questions": 1,
                "stopped": "",
            }
        ],
        "calls": [],
        "concurrency": {"model": 16, "endpoint": 2},
    }
    seed = Seed()
    seed.pair("q1")
    seed.answer("q1", M1, "alone", "correct")
    seed.save(params={"timing": timing})
    assert _report(client, auth)["timing"] == timing


def test_an_older_run_has_no_timing(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.answer("q1", M1, "alone", "correct")
    seed.save()
    assert _report(client, auth)["timing"] is None


def test_run_articles_are_the_asked_articles_with_their_real_dates(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1", doc_id="a", meta={"article_date": "2026-10-05"})
    seed.pair("q2", doc_id="b", meta={"article_date": "2026-10-09"}, job_id=JOB)
    seed.pair("q3", doc_id="b", meta={"article_date": "2026-10-09"}, job_id=JOB)
    seed.pair("q4", doc_id="c", job_id=JOB)
    for qa in ("q1", "q2", "q3", "q4"):
        seed.answer(qa, M1, "with", "correct")
    seed.save()

    report = _report(client, auth)
    want = {
        "articles": 3,
        "articles_first": "2026-10-05",
        "articles_last": "2026-10-09",
        "articles_dated": 2,
        "articles_new": 2,
    }
    for source in (report["run"], report["method"]):
        assert {k: source[k] for k in want} == want
    listed = client.get("/console/report/runs", headers=auth).json()["items"]
    assert {k: listed[0][k] for k in want} == want


def test_a_run_without_article_dates_shows_no_range(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    seed = Seed()
    seed.pair("q1")
    seed.answer("q1", M1, "with", "correct")
    seed.save()

    run = _report(client, auth)["run"]
    assert run["articles"] == 1
    assert run["articles_first"] is None and run["articles_last"] is None
    assert run["articles_dated"] == 0
    # Wrote nothing and kept no build stats: unknown, not zero.
    assert run["articles_new"] is None
