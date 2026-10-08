"""The evaluation plan behind the progress bar, and the text metrics a run
report and the answers listing carry (report API, "Progress plan" and "Text
metrics")."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    JobPhase,
    JobState,
    Settings,
    SpaceConfig,
    get_settings,
)
from syft_benchmark.control import jobs
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import JobView, TargetSpec
from syft_benchmark.db import Job, QaPair, Result, Run, Target, session_scope
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pairs import list_pairs
from syft_benchmark.llm import Provider, catalog
from syft_benchmark.llm.catalog import Catalog, ModelEntry
from syft_benchmark.question_order import KIND_ORDER, pair_key
from syft_benchmark.runs.judge_stage import list_results
from syft_benchmark.runs.parallel import Progress
from syft_benchmark.scheduler import measure

SPACE = SpaceConfig(key="pytest-plan-space", url="http://localhost:0", endpoint="kb")
OPENROUTER = "https://openrouter.ai/api/v1"
COLD = "openai/o9"  # takes no temperature: its Monte Carlo pass is skipped
WARM = "openai/gpt-5"

PLAN = {
    "questions": 10,
    "models": ["a/m"],
    "conditions": ["closed_book", "model_with_context"],
    "checks": ["direct", "denial_loop"],
    "skipped_monte_carlo": [],
    "passes": 3,
    "steps": 30,
    "started_at": "2026-10-08T00:00:00+00:00",
}


# --- the plan ---------------------------------------------------------------


class _Watcher:
    def __init__(self) -> None:
        self.plans: list[dict[str, Any]] = []
        self.order: list[str] = []

    def planned(self, passes: int) -> None:
        self.order.append("planned")

    def plan(self, plan: dict[str, Any]) -> None:
        self.order.append("plan")
        self.plans.append(plan)

    def phase(self, phase: JobPhase, message: str = "") -> None:
        self.order.append(phase.value)

    def pass_started(self, index: int, arm: str, block: str, model: str) -> None:
        self.order.append("pass")

    def pass_done(self, index: int, label: str) -> None: ...

    def watcher(self, label: str) -> Any:
        return None

    def stop_requested(self) -> bool:
        return False


def _providers(*models: str) -> list[Provider]:
    return [
        Provider(role="subject", url=OPENROUTER, api_key="k", model=m) for m in models
    ]


def test_the_plan_is_known_before_any_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "syft_benchmark.scheduler.subject_providers",
        lambda conf: _providers(WARM, COLD),
    )
    monkeypatch.setattr(
        "syft_benchmark.scheduler.judge_providers", lambda conf: _providers("j")
    )
    monkeypatch.setattr("syft_benchmark.scheduler.check_perimeter", lambda conf: None)
    monkeypatch.setattr(
        "syft_benchmark.scheduler.evaluation_gate", lambda key, conf: ""
    )
    monkeypatch.setattr(
        "syft_benchmark.scheduler._active_pairs",
        lambda key, limit, conf: [object()] * 7,
    )

    async def fake_run_pass(space: Any, mode: Any, **kwargs: Any) -> list[Any]:
        return []

    monkeypatch.setattr("syft_benchmark.scheduler.arun_pass", fake_run_pass)
    shipped = Catalog(
        models={
            WARM: ModelEntry(id=WARM, name=WARM, supports=["temperature"]),
            COLD: ModelEntry(id=COLD, name=COLD, supports=[]),
        }
    )
    monkeypatch.setattr(catalog, "load", lambda settings=None: shipped)
    conf = Settings(
        arms=[ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT],
        blocks=[EvalBlock.DIRECT, EvalBlock.MONTE_CARLO],
        generate_in_cycle=False,
    )
    watcher = _Watcher()

    done = measure(SPACE, conf, observer=watcher)

    [plan] = watcher.plans
    assert watcher.order.index("plan") < watcher.order.index("pass")
    assert plan["skipped_monte_carlo"] == [COLD]
    assert plan["questions"] == 7
    assert plan["models"] == [WARM, COLD]
    assert plan["conditions"] == ["closed_book", "model_with_context"]
    assert plan["checks"] == ["direct", "monte_carlo"]
    assert plan["passes"] == done.passes == 6
    assert plan["steps"] == plan["passes"] * 7
    assert datetime.fromisoformat(plan["started_at"]).tzinfo is not None


@contextmanager
def _no_db(*_a: Any, **_k: Any) -> Any:
    class _Session:
        def get(self, *_a: Any) -> None:
            return None

    yield _Session()


def test_the_total_is_fixed_and_the_bar_never_goes_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter = jobs.Reporter("pytest-plan")
    monkeypatch.setattr(reporter, "_write", lambda **k: None)
    monkeypatch.setattr(jobs, "session_scope", _no_db)
    reporter.plan(PLAN)
    first, resumed = reporter.watcher("p1"), reporter.watcher("p2")
    seen: list[int] = []

    def tick(watch: Any, done: int, total: int) -> None:
        watch(Progress(total=total, done=done))
        seen.append(reporter.step_done)
        assert reporter.step_total == 30

    tick(first, 3, 10)
    tick(resumed, 1, 4)  # 6 questions already done count at once
    assert reporter.step_done == 3 + 7
    tick(first, 4, 10)
    reporter.pass_done(1, "p1")  # ended early: its whole share
    seen.append(reporter.step_done)
    tick(resumed, 2, 4)
    reporter.pass_done(2, "p2")
    reporter.pass_done(3, "p3")  # never ticked
    seen.append(reporter.step_done)

    assert seen == sorted(seen)
    assert reporter.step_done == reporter.step_total == 30


def test_without_a_plan_the_total_is_the_sum_of_the_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter = jobs.Reporter("pytest-judging")
    monkeypatch.setattr(reporter, "_write", lambda **k: None)
    reporter.watcher("judging")(Progress(total=8, done=5))
    assert (reporter.step_done, reporter.step_total) == (5, 8)


def test_the_job_view_carries_the_plan() -> None:
    job = Job(
        id="j",
        target="t",
        state="running",
        phase="evaluate",
        kind="pipeline",
        done=0,
        total=3,
        arm="",
        block="",
        model="",
        step_done=0,
        step_total=30,
        message="",
        trigger="manual",
        error="",
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
        params={"evaluate": True, jobs.PROGRESS_PLAN: PLAN},
    )
    assert JobView.model_validate(job).progress_plan == PLAN
    job.params = {"evaluate": True}
    view = JobView.model_validate(job)
    assert view.progress_plan is None
    assert view.model_dump(mode="json")["progress_plan"] is None


# --- the database -----------------------------------------------------------

KEY = "pytest-text-metrics"
TOKEN = "test-text-metrics-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
JOB = "tm-job"
T0 = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)
M1 = "vendor/model-one"


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


def _seed(
    answers: list[tuple[str, str, str, str, dict[str, Any] | None]],
    *,
    state: str = JobState.SUCCEEDED.value,
    params: dict[str, Any] | None = None,
    pairs: dict[str, tuple[str, datetime]] | None = None,
) -> None:
    """answers: (qa, arm, block, judge, text_metrics); pairs: qa -> (kind, made)."""
    kinds = pairs or {}
    with session_scope() as session:
        session.add(
            Job(
                id=JOB,
                target=KEY,
                state=state,
                created_at=T0,
                finished_at=T0 + timedelta(hours=1),
                params=params or {},
            )
        )
        for qa in sorted({a[0] for a in answers} | set(kinds)):
            kind, made = kinds.get(qa, ("qa", T0))
            session.add(
                QaPair(
                    id=qa,
                    space=KEY,
                    job_id=JOB,
                    created_at=made,
                    generator=kind,
                    question=f"Question {qa}?",
                    answer=f"Answer {qa}",
                    status="active",
                    model="gen/model",
                    question_hash=qa,
                )
            )
        session.flush()
        for n, (qa, arm, block, judge, scores) in enumerate(answers):
            session.add(
                Run(
                    id=f"{JOB}-run-{n}",
                    space=KEY,
                    job_id=JOB,
                    context_mode=arm,
                    block=block,
                    model=M1,
                    judge_model=judge,
                )
            )
            session.flush()
            session.add(
                Result(
                    id=f"{JOB}-res-{n}",
                    run_id=f"{JOB}-run-{n}",
                    qa_id=qa,
                    space=KEY,
                    answer="an answer",
                    verdict="correct",
                    judge_model=judge,
                    model=M1,
                    extra={"text_metrics": scores} if scores is not None else {},
                    created_at=T0 + timedelta(seconds=n),
                )
            )


@needs_db
def test_the_answers_listing_carries_text_metrics(clean: Any) -> None:
    scores = {"bleu": 0.25, "rougeL_f": 0.5}
    _seed(
        [
            ("q1", "closed_book", "direct", "j1", scores),
            ("q2", "closed_book", "direct", "j1", None),
        ]
    )
    items, _ = list_results(KEY, job=JOB)
    by_qa = {item.qa_id: item.text_metrics for item in items}
    assert by_qa == {"q1": scores, "q2": None}


@needs_db
def test_the_report_averages_per_model_and_condition(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    _seed(
        [
            # Two judges of one answer count it once.
            ("q1", "model_with_context", "direct", "j1", {"bleu": 0.2}),
            ("q1", "model_with_context", "direct", "j2", {"bleu": 0.2}),
            ("q2", "model_with_context", "direct", "j1", {"bleu": 0.4, "rouge1_f": 1}),
            ("q1", "closed_book", "direct", "j1", {"bleu": 0.1}),
            # The other blocks repeat the direct answer.
            ("q2", "closed_book", "denial_loop", "j1", {"bleu": 0.9}),
        ]
    )
    got = client.get(f"/console/report/runs/{JOB}", headers=auth)
    assert got.status_code == 200, got.text
    assert got.json()["text_metrics"] == [
        {"model": M1, "arm": "alone", "counted": 1, "scores": {"bleu": 0.1}},
        {
            "model": M1,
            "arm": "with",
            "counted": 2,
            "scores": {"bleu": 0.3, "rouge1_f": 1.0},
        },
    ]


@needs_db
def test_a_running_job_shows_its_plan(client: TestClient, clean: Any) -> None:
    auth = _console(client)
    _seed([], state=JobState.RUNNING.value, params={jobs.PROGRESS_PLAN: PLAN})

    listed = client.get("/console/report/runs", headers=auth).json()
    assert [p["progress_plan"] for p in listed["in_progress"]] == [PLAN]
    one = client.get(f"/jobs/{JOB}", headers=AUTH)
    assert one.status_code == 200, one.text
    assert one.json()["progress_plan"] == PLAN


# --- the question order -------------------------------------------------------


def test_the_order_key_puts_kinds_in_the_setup_order() -> None:
    rows = [
        ("zzz_new", T0, "a"),
        ("qa", T0 + timedelta(1), "b"),
        ("qa", T0, "c"),
        ("named_entity_masking", T0 + timedelta(2), "d"),
        ("aaa_new", T0, "e"),
        ("false_premise", T0, "f"),
    ]
    rows.sort(key=lambda r: pair_key(*r))
    assert [r[2] for r in rows] == ["d", "c", "b", "f", "e", "a"]
    assert tuple(GENERATORS) == KIND_ORDER


# Kinds out of their order, and creation times out of id order.
ORDERED = {
    "o-mcq": ("mcq", T0),
    "o-qa-late": ("qa", T0 + timedelta(minutes=5)),
    "o-qa-early": ("qa", T0 + timedelta(minutes=1)),
    "o-names": ("named_entity_masking", T0 + timedelta(minutes=9)),
    "o-trick": ("unanswerable_property", T0),
}
EXPECTED = ["o-names", "o-mcq", "o-qa-early", "o-qa-late", "o-trick"]


@needs_db
def test_every_list_shows_questions_in_one_order(
    client: TestClient, clean: Any
) -> None:
    auth = _console(client)
    answers = [
        (qa, arm, "direct", judge, None)
        for qa in reversed(EXPECTED)
        for arm in ("model_with_context", "closed_book")
        for judge in ("j2", "j1")
    ]
    _seed(answers, pairs=ORDERED)

    pairs, _ = list_pairs(KEY)
    assert [p.id for p in pairs] == EXPECTED
    paged = [list_pairs(KEY, limit=2, offset=n)[0] for n in (0, 2, 4)]
    assert [p.id for page in paged for p in page] == EXPECTED

    results, _ = list_results(KEY, job=JOB)
    assert [(r.qa_id, r.context_mode, r.judge_model) for r in results] == [
        (qa, arm, judge)
        for qa in EXPECTED
        for arm in ("closed_book", "model_with_context")
        for judge in ("j1", "j2")
    ]

    base = f"/console/report/runs/{JOB}"
    filtered = client.get(f"{base}/filter", headers=auth).json()
    assert [d["qa_id"] for d in filtered["items"]] == EXPECTED
    asked = client.get(f"{base}/questions", params={"model": M1}, headers=auth)
    assert asked.status_code == 200, asked.text
    # Trick questions are not listed there.
    assert [q["qa_id"] for q in asked.json()["items"]] == EXPECTED[:-1]
