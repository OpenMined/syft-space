"""The mandatory web check: settings, launch refusals, question selection, report.

Only questions that passed the web check by the current ``filter_model`` reach
the tested models; control questions are exempt; a hand-set status counts only
when ``manual_status_priority`` is "manual".
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from syft_benchmark.config import (
    ContextMode,
    DatasetMode,
    EvalBlock,
    JudgePolicy,
    ManualStatusPriority,
    PairStatus,
    Settings,
    SpaceConfig,
    get_settings,
)
from syft_benchmark.control.app import create_app
from syft_benchmark.control.compose import settings_for
from syft_benchmark.control.formfields import catalogue
from syft_benchmark.control.schemas import Instrument, RunRequest, TargetSpec
from syft_benchmark.db import Job, QaPair, Result, Run, session_scope
from syft_benchmark.db.models import Target
from syft_benchmark.report import run_view
from syft_benchmark.report.card import _dataset
from syft_benchmark.runs import evaluation_gate, run_pass
from syft_benchmark.runs.console import export_questions
from syft_benchmark.runs.execute import _active_pairs
from syft_benchmark.runs.gate import FILTER_REQUIRED

KEY = "pytest-filter-gate"
TOKEN = "test-gate-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
WEB = "openai/gpt-5.1"
OTHER = "x-ai/grok-4.6"
JOB = "pytest-filter-gate-job"
T0 = datetime(2026, 10, 1, tzinfo=UTC)


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="no benchmark database")


@pytest.fixture
def clean() -> Iterator[None]:
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


def _client(**update: Any) -> TestClient:
    conf = get_settings().model_copy(update={"control_token": TOKEN, **update})
    return TestClient(create_app(conf))


def _conf(**update: Any) -> Settings:
    return get_settings().model_copy(
        update={
            "filter_model": WEB,
            "subject_models": ["qwen/qwen3.8-27b"],
            "judge_model": "google/gemini-3.1-pro-preview",
            "judge_models": ["google/gemini-3.1-pro-preview"],
            "judge_policy": JudgePolicy.WARN,
            **update,
        }
    )


def _pair(
    qa: str,
    *,
    web: dict[str, Any] | None = None,
    generator: str = "qa",
    task_type: str = "factual",
    grading: str = "judge",
    status: str = PairStatus.ACTIVE.value,
    manual: bool = False,
    minutes: int = 0,
) -> QaPair:
    meta: dict[str, Any] = {"grading": grading}
    if web is not None:
        meta["web_check"] = web
    if manual:
        meta["manual_override"] = {"status": status, "at": T0.isoformat()}
    return QaPair(
        id=qa,
        space=KEY,
        generator=generator,
        task_type=task_type,
        doc_id=f"doc-{qa}",
        question=f"Question {qa}?",
        answer=f"Answer {qa}",
        context=f"Context {qa}.",
        status=status,
        model="gen/model",
        question_hash=qa,
        meta=meta,
        job_id=JOB,
        created_at=T0 + timedelta(minutes=minutes),
    )


def _passed(model: str = WEB) -> dict[str, Any]:
    return {"model": model, "verdict": "hallucinate"}


def _seed(*rows: QaPair) -> None:
    with session_scope() as session:
        session.add_all(rows)


def _mixed_set() -> None:
    _seed(
        _pair("kept", web=_passed(), minutes=1),
        _pair("answered", web={"model": WEB, "verdict": "correct"}, minutes=2),
        _pair("other-model", web=_passed(OTHER), minutes=3),
        _pair("failed", web={"model": WEB, "verdict": "", "error": "x"}, minutes=4),
        _pair("unchecked", minutes=5),
        _pair(
            "control",
            generator="false_premise",
            task_type="negative",
            grading="behavior",
            minutes=6,
        ),
        _pair("by-hand", manual=True, minutes=7),
        _pair("rejected", web=_passed(), status=PairStatus.REJECTED.value, minutes=8),
    )


# --- settings -------------------------------------------------------------------


def test_the_new_settings_and_their_defaults() -> None:
    conf = Settings()
    assert conf.manual_status_priority is ManualStatusPriority.FILTER
    assert conf.concurrency == 16
    fields = {f["name"]: f for f in catalogue()["instrument"]}
    assert fields["manual_status_priority"]["group"] == "filter"
    assert fields["manual_status_priority"]["choices"] == ["filter", "manual"]
    assert fields["concurrency"]["group"] == "run"
    assert (fields["concurrency"]["minimum"], fields["concurrency"]["maximum"]) == (
        1,
        64,
    )


@needs_db
def test_both_settings_are_stored_applied_and_defaulted(clean: Any) -> None:
    client = _client(filter_model=WEB)
    spec = TargetSpec(
        key=KEY,
        url="http://space.invalid",
        instrument=Instrument(
            concurrency=24, manual_status_priority=ManualStatusPriority.MANUAL
        ),
    ).model_dump(mode="json", exclude_none=True)
    saved = client.put(f"/targets/{KEY}", json=spec, headers=AUTH)
    assert saved.status_code == 200, saved.text
    assert saved.json()["instrument"]["concurrency"] == 24
    assert saved.json()["instrument"]["manual_status_priority"] == "manual"

    with session_scope() as session:
        row = session.get(Target, KEY)
        assert row is not None
        conf, _ = settings_for(row, get_settings())
    assert conf.concurrency == 24
    assert conf.manual_status_priority is ManualStatusPriority.MANUAL

    defaults = client.get("/defaults", headers=AUTH).json()["instrument"]
    assert defaults["manual_status_priority"] == "filter"
    assert defaults["concurrency"] == get_settings().concurrency


# --- launch refusals ------------------------------------------------------------


@needs_db
def test_a_launch_without_a_web_check_model_is_refused(clean: Any) -> None:
    client = _client(filter_model=None)
    plain = TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{KEY}", json=plain, headers=AUTH).status_code == 200

    refused = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH)
    assert refused.status_code == 422
    assert refused.json()["detail"] == FILTER_REQUIRED

    # Not evaluating: nothing is asked, nothing to refuse.
    only_build = client.post(
        f"/targets/{KEY}/runs", json={"evaluate": False}, headers=AUTH
    )
    assert only_build.status_code == 202, only_build.text


@needs_db
def test_the_request_can_bring_the_web_check_model(clean: Any) -> None:
    client = _client(filter_model=None)
    plain = TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json")
    client.put(f"/targets/{KEY}", json=plain, headers=AUTH)
    request = RunRequest(instrument=Instrument(filter_model=WEB)).model_dump(
        mode="json", exclude_none=True
    )
    assert (
        client.post(f"/targets/{KEY}/runs", json=request, headers=AUTH).status_code
        == 202
    )


@needs_db
def test_a_scheduled_target_without_a_web_check_model_is_not_saved(
    clean: Any,
) -> None:
    client = _client(filter_model=None)
    scheduled = TargetSpec(key=KEY, url="http://space.invalid", schedule="24h")
    refused = client.put(
        f"/targets/{KEY}", json=scheduled.model_dump(mode="json"), headers=AUTH
    )
    assert refused.status_code == 422
    assert refused.json()["detail"] == FILTER_REQUIRED

    with_model = scheduled.model_copy(
        update={"instrument": Instrument(filter_model=WEB)}
    )
    saved = client.put(
        f"/targets/{KEY}",
        json=with_model.model_dump(mode="json", exclude_none=True),
        headers=AUTH,
    )
    assert saved.status_code == 200, saved.text


@needs_db
def test_the_console_launch_is_refused_too(clean: Any) -> None:
    client = _client(filter_model=None)
    plain = TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json")
    client.put(f"/targets/{KEY}", json=plain, headers=AUTH)
    token = client.post(f"/targets/{KEY}/session", headers=AUTH).json()["token"]
    refused = client.post(
        "/console/runs", json={}, headers={"Authorization": f"Bearer {token}"}
    )
    assert refused.status_code == 422
    assert refused.json()["detail"] == FILTER_REQUIRED


# --- selection ------------------------------------------------------------------


@needs_db
@pytest.mark.parametrize("mode", [DatasetMode.ROLLING, DatasetMode.REBUILD])
def test_only_filtered_questions_are_asked(clean: Any, mode: DatasetMode) -> None:
    _mixed_set()
    conf = _conf(dataset_mode=mode)
    picked = {p.id for p in _active_pairs(KEY, None, conf)}
    assert picked == {"kept", "control"}

    manual = conf.model_copy(
        update={"manual_status_priority": ManualStatusPriority.MANUAL}
    )
    assert {p.id for p in _active_pairs(KEY, None, manual)} == {
        "kept",
        "control",
        "by-hand",
    }


@needs_db
def test_without_a_web_check_model_only_controls_pass(clean: Any) -> None:
    _mixed_set()
    picked = {p.id for p in _active_pairs(KEY, None, _conf(filter_model=None))}
    assert picked == {"control"}


@needs_db
def test_the_console_export_takes_only_filtered_questions(
    clean: Any, tmp_path: Path
) -> None:
    _mixed_set()
    out = tmp_path / "questions.txt"
    report = export_questions(KEY, out, limit=10, settings=_conf())
    assert report.exported == 2
    text = out.read_text(encoding="utf-8")
    assert "--- kept" in text and "--- control" in text
    assert "--- unchecked" not in text


@needs_db
def test_nothing_passed_ends_the_pass_with_a_note_and_no_run(clean: Any) -> None:
    _seed(_pair("unchecked"), _pair("other-model", web=_passed(OTHER)))
    conf = _conf()
    held = evaluation_gate(KEY, conf)
    assert held.startswith(f"no question has passed the web check by {WEB}")
    assert "2 active questions" in held

    space = SpaceConfig(key=KEY, url="http://space.invalid", endpoint="demo")
    reports = run_pass(
        space, ContextMode.CLOSED_BOOK, settings=conf, block=EvalBlock.DIRECT
    )
    assert reports and all(r.asked == 0 and r.run_id == "" for r in reports)
    assert all(held in r.notes for r in reports)
    with session_scope() as session:
        assert session.execute(select(Run).where(Run.space == KEY)).first() is None


@needs_db
def test_an_empty_set_is_not_a_gate_refusal(clean: Any) -> None:
    assert evaluation_gate(KEY, _conf()) == ""


# --- report ---------------------------------------------------------------------


@needs_db
def test_the_card_counts_the_set_as_asked(clean: Any) -> None:
    _mixed_set()
    assert _dataset(KEY, _conf()).questions == 2


@needs_db
def test_the_funnel_names_questions_held_back_by_the_web_check(clean: Any) -> None:
    _mixed_set()
    with session_scope() as session:
        session.add(
            Job(
                id=JOB,
                target=KEY,
                kind="pipeline",
                state="succeeded",
                params=run_view.judging_snapshot(_conf()),
            )
        )
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        funnel = run_view._funnel(session, job, set(), 0, 0)
    # answered, other-model, failed, unchecked, by-hand; not kept or control.
    assert funnel["unchecked"] == 5
    assert funnel["written"] == 8


@needs_db
def test_an_old_job_has_no_unchecked_count(clean: Any) -> None:
    _mixed_set()
    with session_scope() as session:
        session.add(Job(id=JOB, target=KEY, kind="pipeline", state="succeeded"))
    with session_scope() as session:
        job = session.get(Job, JOB)
        assert job is not None
        assert run_view._funnel(session, job, set(), 0, 0)["unchecked"] is None
