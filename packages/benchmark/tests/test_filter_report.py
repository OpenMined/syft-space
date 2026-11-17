"""A job's filter decisions, build-only jobs in the runs list, and how a run
was tested (web check model, judge, cost)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from syft_benchmark.config import (
    JobState,
    PairStatus,
    Settings,
    SpaceConfig,
    StatusReason,
    get_settings,
)
from syft_benchmark.db import Job, QaPair, Run, session_scope
from syft_benchmark.generation import decisions, filter_stage, web_check
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.llm import LLMError
from syft_benchmark.report import filter_view, job_params
from syft_benchmark.runs import judge as run_judge

from fakes import openrouter_settings
from support import add_rows, console_auth

KEY = "pytest-filter-report"
T0 = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
WRITER, CHECKER = "fr-job-a", "fr-job-b"


pytestmark = pytest.mark.needs_db


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "filter_model": "openai/gpt-5.1",
        "concurrency": 1,
    }
    return openrouter_settings(**{**base, **kwargs})


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
    add_rows(
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
    add_rows(_pair("p1"))
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
    auth = console_auth(client, KEY)
    add_rows(_job(WRITER), _job(CHECKER, at=T0 + timedelta(days=1)))
    add_rows(
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
    assert body["counts"] == {"kept": 2, "removed": 1, "failed": 0}
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


def test_limit_zero_returns_one_kinds_decisions_in_one_page(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The details dialog reads a kind in one request; other callers page."""
    auth = console_auth(client, KEY)
    add_rows(_job(WRITER))
    add_rows(
        *(
            _pair(f"z-{n}", job_id=WRITER, status=PairStatus.ACTIVE.value)
            for n in range(3)
        )
    )
    add_rows(_pair("z-mcq", "mcq", job_id=WRITER, status=PairStatus.ACTIVE.value))
    monkeypatch.setattr(filter_view, "MAX_PAGE", 1)
    url = f"/console/report/runs/{WRITER}/filter"

    every = client.get(url, params={"generator": "qa", "limit": 0}, headers=auth)
    assert every.status_code == 200, every.text
    body = every.json()
    assert sorted(i["qa_id"] for i in body["items"]) == ["z-0", "z-1", "z-2"]
    assert body["total"] == 3
    rest = client.get(
        url, params={"generator": "qa", "limit": 0, "offset": 2}, headers=auth
    ).json()
    assert len(rest["items"]) == 1
    paged = client.get(url, params={"generator": "qa", "limit": 1}, headers=auth)
    assert paged.status_code == 200, paged.text
    assert len(paged.json()["items"]) == 1
    unbounded = client.get(url, params={"limit": 0}, headers=auth)
    assert unbounded.status_code == 422


def test_an_unstamped_job_gets_decisions_inferred(
    client: TestClient, clean: Any
) -> None:
    auth = console_auth(client, KEY)
    add_rows(_job(WRITER))
    add_rows(
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
    auth = console_auth(client, KEY)
    measured = "fr-measured"
    add_rows(
        _job(WRITER),
        _job(CHECKER, at=T0 + timedelta(days=1), kind="filter"),
        _job(measured, at=T0 + timedelta(days=2)),
        _job("fr-nothing", at=T0 + timedelta(days=3)),
    )
    add_rows(
        _pair("b-1", job_id=WRITER),
        _pair("b-2", job_id=WRITER),
        _pair("m-1", job_id=measured, status=PairStatus.ACTIVE.value),
    )
    add_rows(
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
    auth = console_auth(client, KEY)
    cost = {"spend_before": 1.0, "spend_after": 1.25, "usd": 0.25, "usd_calls": 0.24}
    add_rows(
        _job(
            WRITER,
            params={
                job_params.WEB_CHECK_MODEL: "openai/gpt-5.1",
                job_params.WEB_CHECK_JUDGE: "judge/one",
                job_params.COST: cost,
            },
        ),
        _job(CHECKER),
    )
    add_rows(_pair("h-1", job_id=WRITER), _pair("h-2", job_id=CHECKER))

    method = client.get(f"/console/report/runs/{WRITER}", headers=auth).json()["method"]
    assert method["web_check_model"] == "openai/gpt-5.1"
    assert method["web_check_judge"] == "judge/one"
    # A job recorded without a cost by role.
    assert method["cost"] == {**cost, "total_usd": None, "by_role": None}
    bare = client.get(f"/console/report/runs/{CHECKER}", headers=auth).json()["method"]
    assert bare["web_check_model"] is None
    assert bare["web_check_judge"] is None
    assert bare["cost"] is None


def test_the_web_check_judge_is_resolved() -> None:
    conf = Settings(judge_models=["judge/one", "judge/two"])
    assert job_params.web_check_judge(conf) == ""
    on = conf.model_copy(update={"filter_model": "m/web"})
    assert job_params.web_check_judge(on) == "judge/one"
    chosen = on.model_copy(update={"filter_judge_model": "judge/web"})
    assert job_params.web_check_judge(chosen) == "judge/web"


def test_a_job_records_what_it_spent(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from syft_benchmark.control import jobs
    from syft_benchmark.llm import cost

    console_auth(client, KEY)
    reads = iter([10.0, 10.5])
    monkeypatch.setattr(jobs, "openrouter_spend", lambda conf: next(reads))

    def judging(*_: Any, **__: Any) -> Any:
        cost.charge(0.2, cost.JUDGES)
        # Untagged (an access check): in usd_calls, not in total_usd.
        cost.charge(0.1)
        return SimpleNamespace(line=lambda: "", notes=[])

    monkeypatch.setattr(jobs, "judge_pending", judging)
    add_rows(Job(id=WRITER, target=KEY, kind="judge", state="queued", params={}))

    jobs.execute(WRITER)

    with session_scope() as session:
        row = session.get(Job, WRITER)
        assert row is not None and row.state == JobState.SUCCEEDED.value
        spent = row.params[job_params.COST]
    assert spent["spend_before"] == 10.0 and spent["spend_after"] == 10.5
    assert spent["usd"] == pytest.approx(0.5)
    assert spent["usd_calls"] == pytest.approx(0.3)
    assert spent["total_usd"] == pytest.approx(0.2)
    assert spent["by_role"]["judges"] == pytest.approx(0.2)
    assert spent["by_role"]["writer"] == 0.0


def test_a_failed_spend_read_leaves_usd_empty(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from syft_benchmark.control import jobs

    console_auth(client, KEY)

    def broken(conf: Any) -> float:
        raise RuntimeError("no network")

    monkeypatch.setattr(jobs, "openrouter_spend", broken)
    monkeypatch.setattr(
        jobs,
        "judge_pending",
        lambda *a, **k: SimpleNamespace(line=lambda: "", notes=[]),
    )
    add_rows(Job(id=WRITER, target=KEY, kind="judge", state="queued", params={}))

    jobs.execute(WRITER)

    with session_scope() as session:
        row = session.get(Job, WRITER)
        assert row is not None and row.state == JobState.SUCCEEDED.value
        assert row.params[job_params.COST] == {
            "spend_before": None,
            "spend_after": None,
            "usd": None,
            "usd_calls": 0.0,
            "total_usd": 0.0,
            "by_role": {
                "writer": 0.0,
                "web_check": 0.0,
                "subjects": 0.0,
                "judges": 0.0,
            },
        }


# --- the build per kind -------------------------------------------------------


def test_the_build_per_kind_is_kept_with_the_job(
    client: TestClient, clean: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from syft_benchmark import scheduler
    from syft_benchmark.generation import pipeline

    auth = console_auth(client, KEY)
    add_rows(_job(WRITER, params={}))
    add_rows(_pair("g-1", job_id=WRITER), _pair("g-2", "mcq", job_id=WRITER))

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
            "topped_up": 0,
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

    add_rows(_job(CHECKER))
    bare = client.get(f"/console/report/runs/{CHECKER}/generated", headers=auth)
    assert bare.json() == {"kinds": [], "items": [], "total": 0}


def test_one_pair_is_read_with_its_meta_from_a_run(
    client: TestClient, clean: None
) -> None:
    auth = console_auth(client, KEY)
    add_rows(_job(WRITER))
    add_rows(
        _pair(
            "one-1",
            job_id=WRITER,
            status=PairStatus.REJECTED.value,
            status_reason=StatusReason.WRONG_LANGUAGE.value,
            meta={"writer": {"call": "c1"}},
        )
    )

    got = client.get(f"/console/report/runs/{WRITER}/pairs/one-1", headers=auth)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["id"] == "one-1"
    assert body["meta"] == {"writer": {"call": "c1"}}
    assert body["status_reason"] == StatusReason.WRONG_LANGUAGE.value
    assert body["has_results"] is False

    missing = client.get(f"/console/report/runs/{WRITER}/pairs/nope", headers=auth)
    assert missing.status_code == 404
    unknown = client.get("/console/report/runs/nope/pairs/one-1", headers=auth)
    assert unknown.status_code == 404
