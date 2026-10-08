"""A job's filter decisions, build-only jobs in the runs list, and how a run
was tested (web check model, judge, cost)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from syft_benchmark.config import (
    JobState,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    get_settings,
)
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db import Job, QaPair, Result, Run, Target, session_scope
from syft_benchmark.generation import decisions, filter_stage, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.llm import LLMError
from syft_benchmark.report import run_view
from syft_benchmark.runs import judge as run_judge

KEY = "pytest-filter-report"
TOKEN = "test-filter-report-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
OPENROUTER = "https://openrouter.ai/api/v1"
T0 = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
WRITER, CHECKER = "fr-job-a", "fr-job-b"


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
            session.execute(delete(Result).where(Result.space == KEY))
            session.execute(delete(Run).where(Run.space == KEY))
            session.execute(delete(QaPair).where(QaPair.space == KEY))
            session.execute(delete(Job).where(Job.target == KEY))
            session.execute(delete(Target).where(Target.key == KEY))

    wipe()
    yield
    wipe()


@pytest.fixture
def client() -> TestClient:
    conf = get_settings().model_copy(update={"control_token": TOKEN})
    return TestClient(create_app(conf))


def _console(client: TestClient) -> dict[str, str]:
    body = TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{KEY}", json=body, headers=AUTH).status_code == 200
    minted = client.post(f"/targets/{KEY}/session", headers=AUTH)
    assert minted.status_code == 200, minted.text
    return {"Authorization": f"Bearer {minted.json()['token']}"}


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "filter_model": "openai/gpt-5.1",
        "subject_url": OPENROUTER,
        "subject_key": "sk-test",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
        "max_consecutive_failures": 0,
        "concurrency": 1,
    }
    return Settings(**{**base, **kwargs})


def _pair(pair_id: str, generator: str = "qa", **extra: Any) -> QaPair:
    return QaPair(
        id=pair_id,
        space=KEY,
        generator=generator,
        task_type=GENERATORS[generator].task_type,
        doc_id="d1",
        question=f"Question {pair_id}: which landmark was restored?",
        answer=extra.pop("answer", "Harbourton lighthouse"),
        context="The council restored the Harbourton lighthouse this spring.",
        status=extra.pop("status", PairStatus.PENDING.value),
        model="gen/model",
        question_hash=uuid.uuid4().hex,
        **extra,
    )


def _job(job_id: str, *, at: datetime = T0, **extra: Any) -> Job:
    return Job(
        id=job_id,
        target=KEY,
        state=extra.pop("state", JobState.SUCCEEDED.value),
        created_at=at,
        finished_at=at + timedelta(minutes=5),
        **extra,
    )


def _add(*rows: Any) -> None:
    with session_scope() as session:
        for row in rows:
            session.add(row)
            session.flush()


def _stub_web(
    monkeypatch: pytest.MonkeyPatch,
    answerable: set[str],
    failing: frozenset[str] = frozenset(),
) -> None:
    def web_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        if any(f"Question {pid}:" in user for pid in failing):
            raise LLMError("the provider is down")
        usage = {
            "web_search": "plugin",
            "web_search_requests": 2,
            "citations": [{"url": "https://example.org/a", "title": "A"}],
        }
        return f"Web answer to: {user}", usage

    def judge_chat(system: str, user: str, **_: Any) -> tuple[str, dict[str, Any]]:
        right = any(f"Question {pid}:" in user for pid in answerable)
        return f'{{"correct": {"true" if right else "false"}}}', {}

    monkeypatch.setattr(web_check, "chat", web_chat)
    monkeypatch.setattr(run_judge, "chat", judge_chat)


def _space() -> SpaceConfig:
    return SpaceConfig(key=KEY, url="http://space:8080", endpoint="ep")


def _meta(pair_id: str) -> dict[str, Any]:
    with session_scope() as session:
        row = session.get(QaPair, pair_id)
        assert row is not None
        return dict(row.meta)


# --- stamping ---------------------------------------------------------------


def test_every_decision_is_stamped_with_the_job(
    clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add(
        _pair("p-web", job_id=WRITER),
        _pair("p-keep", job_id=WRITER),
        _pair("p-fail", job_id=WRITER),
        _pair("p-ungrounded", job_id=WRITER, answer="Nothing in the passage"),
        _pair("p-control", "unanswerable_property", job_id=WRITER),
    )
    _stub_web(monkeypatch, answerable={"p-web"}, failing={"p-fail"})

    filter_stage.filter_pending(_space(), settings=_settings(), job_id=CHECKER)

    def last(pair_id: str) -> dict[str, Any]:
        entry = decisions.of_job(_meta(pair_id), CHECKER)
        assert entry is not None, pair_id
        return entry

    web = last("p-web")
    assert (web["stage"], web["outcome"], web["reason"]) == (
        "web_check",
        "removed",
        StatusReason.WEB_ANSWERABLE.value,
    )
    assert web["web"]["verdict"] == "correct"
    assert web["web"]["job_id"] == CHECKER
    assert _meta("p-web")["web_check"]["job_id"] == CHECKER
    assert (last("p-keep")["stage"], last("p-keep")["outcome"]) == ("web_check", "kept")
    assert last("p-fail")["outcome"] == "failed"
    assert (last("p-ungrounded")["stage"], last("p-ungrounded")["outcome"]) == (
        "grounding",
        "removed",
    )
    assert (last("p-control")["stage"], last("p-control")["outcome"]) == (
        "control",
        "removed",
    )


def test_no_job_no_stamp(clean: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _add(_pair("p1"))
    _stub_web(monkeypatch, answerable=set())

    filter_stage.filter_pending(_space(), settings=_settings())

    meta = _meta("p1")
    assert decisions.SCREENING not in meta
    assert "job_id" not in meta["web_check"]


def test_records_are_bounded() -> None:
    meta: dict[str, Any] = {}
    for n in range(30):
        entry = decisions.record(job_id=f"j{n}", stage="grounding", outcome="kept")
        meta = {**meta, **decisions.stamped(meta, entry)}
    kept = meta[decisions.SCREENING]
    assert len(kept) == 20 and kept[-1]["job_id"] == "j29"
    assert decisions.of_job(meta, "j5") is None


# --- the report routes --------------------------------------------------------


def test_a_jobs_filter_list_includes_pairs_written_earlier(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = _console(client)
    _add(_job(WRITER), _job(CHECKER, at=T0 + timedelta(days=1)))
    _add(
        _pair("old-1", job_id=WRITER),
        _pair("old-2", job_id=WRITER),
        _pair("new-1", job_id=CHECKER),
    )
    _stub_web(monkeypatch, answerable={"old-1"})
    filter_stage.filter_pending(_space(), settings=_settings(), job_id=CHECKER)

    got = client.get(f"/console/report/runs/{CHECKER}/filter", headers=auth)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["total"] == 3
    assert body["counts"] == {"kept": 2, "removed": 1, "failed": 0, "skipped": 0}
    rows = {item["qa_id"]: item for item in body["items"]}
    old = rows["old-1"]
    assert old["earlier"] is True
    assert old["written_by_job"] == WRITER
    assert old["written_by_job_at"].startswith("2026-10-01")
    assert old["recorded"] is True
    assert old["outcome"] == "removed" and old["reason_code"] == "web_answerable"
    details = old["web_check"]
    assert details["model"] == "openai/gpt-5.1"
    assert details["verdict"] == "correct"
    assert details["citations"] == [{"url": "https://example.org/a", "title": "A"}]
    assert details["searches"] == 2
    assert details["searched"] is True
    assert rows["new-1"]["earlier"] is False

    removed = client.get(
        f"/console/report/runs/{CHECKER}/filter",
        params={"outcome": "removed"},
        headers=auth,
    ).json()
    assert [i["qa_id"] for i in removed["items"]] == ["old-1"]
    assert removed["counts"]["kept"] == 2
    paged = client.get(
        f"/console/report/runs/{CHECKER}/filter",
        params={"limit": 1, "offset": 1},
        headers=auth,
    ).json()
    assert len(paged["items"]) == 1 and paged["total"] == 3
    bad = client.get(
        f"/console/report/runs/{CHECKER}/filter",
        params={"stage": "nope"},
        headers=auth,
    )
    assert bad.status_code == 422

    # The writer made no decision on them: its list is empty.
    writer = client.get(f"/console/report/runs/{WRITER}/filter", headers=auth).json()
    assert writer["total"] == 0


def test_an_unstamped_job_gets_decisions_inferred(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    _add(_job(WRITER))
    _add(
        _pair(
            "l-rejected",
            job_id=WRITER,
            status=PairStatus.REJECTED.value,
            status_reason=StatusReason.WEB_ANSWERABLE.value,
            status_note="web_answerable",
            meta={"web_check": {"model": "m/web", "verdict": "correct"}},
        ),
        _pair("l-active", job_id=WRITER, status=PairStatus.ACTIVE.value),
        _pair("l-pending", job_id=WRITER),
    )

    body = client.get(f"/console/report/runs/{WRITER}/filter", headers=auth).json()

    rows = {item["qa_id"]: item for item in body["items"]}
    assert set(rows) == {"l-rejected", "l-active"}
    assert rows["l-rejected"]["recorded"] is False
    assert rows["l-rejected"]["stage"] == "web_check"
    assert rows["l-rejected"]["outcome"] == "removed"
    assert rows["l-rejected"]["web_check"]["model"] == "m/web"
    assert rows["l-active"]["outcome"] == "kept"


def test_build_only_jobs_are_listed(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = _console(client)
    measured = "fr-measured"
    _add(
        _job(WRITER),
        _job(CHECKER, at=T0 + timedelta(days=1), kind="filter"),
        _job(measured, at=T0 + timedelta(days=2)),
        _job("fr-nothing", at=T0 + timedelta(days=3)),
    )
    _add(
        _pair("b-1", job_id=WRITER),
        _pair("b-2", job_id=WRITER),
        _pair("m-1", job_id=measured, status=PairStatus.ACTIVE.value),
    )
    _add(
        Run(
            id="fr-run",
            space=KEY,
            job_id=measured,
            context_mode="closed_book",
            model="vendor/model",
        )
    )
    _stub_web(monkeypatch, answerable={"b-1"})
    filter_stage.filter_pending(_space(), settings=_settings(), job_id=CHECKER)

    page = client.get("/console/report/runs", headers=auth).json()

    items = {item["job_id"]: item for item in page["items"]}
    assert set(items) == {WRITER, CHECKER, measured}
    assert page["total"] == 3
    assert items[measured]["build_only"] is False
    assert items[WRITER]["build_only"] is True
    assert items[WRITER]["build"]["written"] == 2
    assert items[WRITER]["build"]["checked"] == 0
    assert items[CHECKER]["build"] == {
        "written": 0,
        "checked": 2,
        "kept": 1,
        "removed": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert items[CHECKER]["state"] == JobState.SUCCEEDED.value
    assert items[CHECKER]["models"] == []

    one = client.get(f"/console/report/runs/{WRITER}", headers=auth)
    assert one.status_code == 200, one.text
    report = one.json()
    assert report["run"]["build_only"] is True
    assert report["models"] == []
    assert report["funnel"]["written"] == 2


def test_how_tested_reads_the_jobs_snapshot(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    cost = {"spend_before": 1.0, "spend_after": 1.25, "usd": 0.25, "usd_calls": 0.24}
    _add(
        _job(
            WRITER,
            params={
                run_view.WEB_CHECK_MODEL: "openai/gpt-5.1",
                run_view.WEB_CHECK_JUDGE: "judge/one",
                run_view.COST: cost,
            },
        ),
        _job(CHECKER),
    )
    _add(_pair("h-1", job_id=WRITER), _pair("h-2", job_id=CHECKER))

    method = client.get(f"/console/report/runs/{WRITER}", headers=auth).json()["method"]
    assert method["web_check_model"] == "openai/gpt-5.1"
    assert method["web_check_judge"] == "judge/one"
    assert method["cost"] == cost
    bare = client.get(f"/console/report/runs/{CHECKER}", headers=auth).json()["method"]
    assert bare["web_check_model"] is None
    assert bare["web_check_judge"] is None
    assert bare["cost"] is None


def test_the_web_check_judge_is_resolved() -> None:
    conf = Settings(judge_models=["judge/one", "judge/two"])
    assert run_view.web_check_judge(conf) == ""
    on = conf.model_copy(update={"filter_model": "m/web"})
    assert run_view.web_check_judge(on) == "judge/one"
    chosen = on.model_copy(update={"filter_judge_model": "judge/web"})
    assert run_view.web_check_judge(chosen) == "judge/web"


def test_a_job_records_what_it_spent(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from syft_benchmark.control import jobs
    from syft_benchmark.llm import cost

    _console(client)
    reads = iter([10.0, 10.5])
    monkeypatch.setattr(jobs, "openrouter_spend", lambda conf: next(reads))

    def judging(*_: Any, **__: Any) -> Any:
        cost.charge(0.2)
        cost.charge(0.1)
        return SimpleNamespace(line=lambda: "", notes=[])

    monkeypatch.setattr(jobs, "judge_pending", judging)
    _add(Job(id=WRITER, target=KEY, kind="judge", state="queued", params={}))

    jobs.execute(WRITER)

    with session_scope() as session:
        row = session.get(Job, WRITER)
        assert row is not None and row.state == JobState.SUCCEEDED.value
        spent = row.params[run_view.COST]
    assert spent["spend_before"] == 10.0 and spent["spend_after"] == 10.5
    assert spent["usd"] == pytest.approx(0.5)
    assert spent["usd_calls"] == pytest.approx(0.3)


def test_a_failed_spend_read_leaves_usd_empty(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from syft_benchmark.control import jobs

    _console(client)

    def broken(conf: Any) -> float:
        raise RuntimeError("no network")

    monkeypatch.setattr(jobs, "openrouter_spend", broken)
    monkeypatch.setattr(
        jobs,
        "judge_pending",
        lambda *a, **k: SimpleNamespace(line=lambda: "", notes=[]),
    )
    _add(Job(id=WRITER, target=KEY, kind="judge", state="queued", params={}))

    jobs.execute(WRITER)

    with session_scope() as session:
        row = session.get(Job, WRITER)
        assert row is not None and row.state == JobState.SUCCEEDED.value
        assert row.params[run_view.COST] == {
            "spend_before": None,
            "spend_after": None,
            "usd": None,
            "usd_calls": 0.0,
        }


# --- the build per kind -------------------------------------------------------


def test_the_build_per_kind_is_kept_with_the_job(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from syft_benchmark import scheduler
    from syft_benchmark.generation import pipeline

    auth = _console(client)
    _add(_job(WRITER, params={}))
    _add(_pair("g-1", job_id=WRITER), _pair("g-2", "mcq", job_id=WRITER))

    def built(*_: Any, **__: Any) -> pipeline.GenerationReport:
        report = pipeline.GenerationReport(space=KEY)
        report.kinds["qa"] = pipeline.KindStats(
            kind="qa",
            unit="passage",
            budget=4,
            written=1,
            units_available=3,
            units_read=3,
            dropped={"duplicate": 1},
            stopped=pipeline.OUT_OF_MATERIAL,
        )
        return report

    monkeypatch.setattr(scheduler, "generate_for_space", built)
    scheduler.measure(
        _space(),
        get_settings(),
        generate=True,
        filter=False,
        evaluate=False,
        job_id=WRITER,
    )

    got = client.get(f"/console/report/runs/{WRITER}/generated", headers=auth)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["kinds"] == [
        {
            "kind": "qa",
            "unit": "passage",
            "budget": 4,
            "written": 1,
            "units_available": 3,
            "units_read": 3,
            "failed_units": 0,
            "dropped": {"duplicate": 1},
            "stopped": "ran out of material",
        }
    ]
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {"g-1", "g-2"}
    only = client.get(
        f"/console/report/runs/{WRITER}/generated",
        params={"generator": "mcq"},
        headers=auth,
    ).json()
    assert [item["id"] for item in only["items"]] == ["g-2"]

    _add(_job(CHECKER))
    bare = client.get(f"/console/report/runs/{CHECKER}/generated", headers=auth)
    assert bare.json() == {"kinds": [], "items": [], "total": 0}
