"""Every pass at once, Monte Carlo repeats side by side, and where the time went.

No database and no model: the passes run over a stand whose calls are counted
and timed.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest
from sqlalchemy import delete

import syft_benchmark.runs.blocks as blocks
import syft_benchmark.runs.execute as execute
import syft_benchmark.runs.judge as judge
import syft_benchmark.runs.parallel as parallel
import syft_benchmark.scheduler as scheduler
from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    DatasetMode,
    EvalBlock,
    JobPhase,
    PairStatus,
    Settings,
    SpaceConfig,
)
from syft_benchmark.control import jobs
from syft_benchmark.llm import LLMError, LLMFatalError, Provider
from syft_benchmark.runs.blocks import Trial, monte_carlo_plan, tally_monte_carlo
from syft_benchmark.runs.parallel import Progress, Streak
from syft_benchmark.runs.timing import CallClock, JobClock, PassTime, p90

SPACE = SpaceConfig(key="pytest-concurrent", url="http://node.local", endpoint="kb")


def _seat(role: str, model: str) -> Provider:
    return Provider(role=role, url="http://localhost:11434", api_key="", model=model)


class _Pair:
    def __init__(self, n: int) -> None:
        self.id = f"pair-{n}"
        self.question = f"What port does rig {n} use?"
        self.answer = "5442"
        self.context = "The port is published as 5442."
        self.task_type = "open"
        self.expected_behavior = "answer"
        self.generator = "qa"
        self.meta: dict[str, Any] = {}
        self.doc_id = "doc-1"
        self.file_name = "setup.md"


class _Stand:
    """Models, judges and the node substituted; calls counted and in flight."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        pairs: int = 4,
        delay: float = 0.0,
        subjects: tuple[str, ...] = ("a/m1",),
        judges: tuple[str, ...] = ("j/one",),
    ) -> None:
        self.pairs = [_Pair(i) for i in range(pairs)]
        self.delay = delay
        self.lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []
        self.in_flight = 0
        self.peak = 0
        self.refuse: set[str] = set()
        self.fail: set[str] = set()
        self.subjects = [_seat("subject", m) for m in subjects]
        self.judges = [_seat("judge", m) for m in judges]
        stand = self

        def chat(system: str, user: str, **kwargs: Any) -> Any:
            provider = kwargs["provider"]
            with stand.lock:
                stand.calls.append((provider.model, provider.role))
                stand.in_flight += 1
                stand.peak = max(stand.peak, stand.in_flight)
            try:
                if stand.delay:
                    time.sleep(stand.delay)
                if provider.model in stand.refuse:
                    raise LLMFatalError(f"{provider.model} is not a valid model ID")
                if provider.model in stand.fail:
                    raise LLMError("down")
                if provider.role == "judge":
                    return '{"correct": true, "grounded": true, "reasoning": "ok"}', {}
                return "Port 5442.", {"finish_reason": "stop", "latency_s": 0.01}
            finally:
                with stand.lock:
                    stand.in_flight -= 1

        def endpoint(space: SpaceConfig, question: str, **kwargs: Any) -> Any:
            return {
                "answer": "Port 5442.",
                "documents": [
                    {
                        "content": "The port is published as 5442.",
                        "metadata": {"doc_id": "doc-1", "file_name": "setup.md"},
                        "similarity_score": 0.81,
                    }
                ],
                "latency": 0.0,
                "failed": False,
            }

        class _Session:
            def add(self, obj: Any) -> None: ...

        class _Scope:
            def __enter__(self) -> Any:
                return _Session()

            def __exit__(self, *exc: Any) -> bool:
                return False

        monkeypatch.setattr(parallel, "ask_endpoint", endpoint)
        for module in (parallel, execute, judge, blocks):
            monkeypatch.setattr(module, "chat", chat)
        monkeypatch.setattr(execute, "endpoint_mode", lambda space: "both")
        monkeypatch.setattr(
            execute, "_active_pairs", lambda key, limit, conf=None: self.pairs
        )
        monkeypatch.setattr(execute, "session_scope", lambda *a, **k: _Scope())
        monkeypatch.setattr(execute, "skips_monte_carlo", lambda *a: False)
        monkeypatch.setattr(scheduler, "skips_monte_carlo", lambda *a: False)
        monkeypatch.setattr(scheduler, "check_perimeter", lambda conf: None)
        monkeypatch.setattr(scheduler, "evaluation_gate", lambda key, conf: "")
        monkeypatch.setattr(scheduler, "summarize", lambda *a, **k: None)
        monkeypatch.setattr(scheduler, "subject_providers", lambda conf: self.subjects)
        monkeypatch.setattr(scheduler, "judge_providers", lambda conf: self.judges)

    def asked(self, model: str) -> int:
        return sum(1 for m, _ in self.calls if m == model)


def _conf(**update: Any) -> Settings:
    body: dict[str, Any] = {
        "ollama_url": "http://localhost:11434",
        "arms": [ContextMode.CLOSED_BOOK],
        "blocks": [EvalBlock.DIRECT],
        "context_source": ContextSource.ENDPOINT_FRAGMENTS,
        "generate_in_cycle": False,
        "judge_policy": "off",
        "concurrency": 8,
        "monte_carlo_temperatures": [0.3, 0.9],
        "monte_carlo_trials": 2,
        "denial_rounds": 1,
    }
    body.update(update)
    return Settings(**body)


# --- the timing --------------------------------------------------------------


def test_call_stats_per_model_and_role() -> None:
    clock = CallClock()
    for seconds in (0.1, 0.2, 0.3, 0.4, 1.0):
        clock.record("a/m", "answer", seconds)
    clock.record("j/one", "judge", 2.0, failed=True)

    assert clock.stats() == [
        {
            "model": "a/m",
            "role": "answer",
            "count": 5,
            "failed": 0,
            "mean_s": 0.4,
            "p90_s": 1.0,
            "max_s": 1.0,
            "total_s": 2.0,
        },
        {
            "model": "j/one",
            "role": "judge",
            "count": 1,
            "failed": 1,
            "mean_s": 2.0,
            "p90_s": 2.0,
            "max_s": 2.0,
            "total_s": 2.0,
        },
    ]
    assert p90([float(n) for n in range(1, 11)]) == 9.0
    assert p90([]) == 0.0


def test_a_timed_call_counts_failures_and_skips_what_was_no_call() -> None:
    clock = CallClock()

    def boom() -> str:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        clock.timed("a/m", "answer", boom)()
    clock.timed("j/one", "judge", lambda: "", counted=bool)()
    clock.timed("j/one", "judge", lambda: "bad", failed=lambda r: r == "bad")()

    stats = {(row["model"], row["role"]): row for row in clock.stats()}
    assert stats[("a/m", "answer")]["failed"] == 1
    assert stats[("j/one", "judge")]["count"] == 1
    assert stats[("j/one", "judge")]["failed"] == 1


def test_phases_are_kept_in_order_and_a_repeat_is_added_up() -> None:
    clock = JobClock()
    for phase in ("generate", "filter", "generate", "evaluate"):
        clock.enter(phase)
    clock.enter("evaluate")

    timing = clock.payload(
        passes=[
            PassTime(arm="closed_book", block="direct", model="a/m", seconds=1.234)
        ],
        concurrency={"model": 16, "endpoint": 2},
    )

    assert [p["phase"] for p in timing["phases"]] == ["generate", "filter", "evaluate"]
    assert timing["passes"] == [
        {
            "arm": "closed_book",
            "block": "direct",
            "model": "a/m",
            "s": 1.23,
            "questions": 0,
            "stopped": "",
        }
    ]
    assert timing["calls"] == []
    assert timing["concurrency"] == {"model": 16, "endpoint": 2}
    assert timing["total_s"] >= 0


def test_the_job_row_sums_the_steps_of_passes_running_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporter = jobs.Reporter("pytest-steps")
    monkeypatch.setattr(reporter, "_write", lambda **k: None)
    first, second = reporter.watcher("p1"), reporter.watcher("p2")

    first(Progress(total=10, done=3))
    second(Progress(total=5, done=2))
    first(Progress(total=10, done=4))
    reporter.pass_done(2, "p2")
    reporter.phase(JobPhase.EVALUATE)

    assert (reporter.step_done, reporter.step_total) == (6, 15)
    assert reporter.passes == 1
    assert [p["phase"] for p in reporter.timing()["phases"]] == ["evaluate"]


# --- the passes --------------------------------------------------------------


def test_every_pass_runs_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    stand = _Stand(monkeypatch, subjects=("a/m1", "b/m2"))
    running = 0
    peak = 0

    async def one_pass(space: Any, mode: Any, **kwargs: Any) -> list[Any]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        running -= 1
        return []

    monkeypatch.setattr(scheduler, "arun_pass", one_pass)
    conf = _conf(
        arms=[ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT],
        blocks=[EvalBlock.DIRECT, EvalBlock.DENIAL_LOOP],
    )

    started = time.monotonic()
    out = scheduler.measure(SPACE, conf)

    assert peak == out.passes == 8
    assert time.monotonic() - started < 0.4
    # Plan order: block, arm, model.
    assert [(t.block, t.arm, t.model) for t in out.pass_times][:3] == [
        ("direct", "closed_book", stand.subjects[0].model),
        ("direct", "closed_book", stand.subjects[1].model),
        ("direct", "model_with_context", stand.subjects[0].model),
    ]
    assert all(t.seconds >= 0.04 for t in out.pass_times)


def test_the_passes_share_the_model_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    stand = _Stand(monkeypatch, pairs=6, delay=0.02, subjects=("a/m1", "b/m2"))
    conf = _conf(
        concurrency=3,
        arms=[ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT],
        blocks=[EvalBlock.DIRECT, EvalBlock.MONTE_CARLO],
    )

    out = scheduler.measure(SPACE, conf)

    assert stand.peak == 3
    assert out.passes == 8 and out.failures == []
    assert out.asked == 8 * 6
    stats = {(row["model"], row["role"]): row for row in out.clock.stats()}
    # Direct answers (cache shared with nothing else here) plus 4 repeats each.
    assert stats[("a/m1", "answer")]["count"] == 2 * 6 + 2 * 6 * 4
    assert stats[("j/one", "judge")]["count"] > 0
    assert {t.questions for t in out.pass_times} == {6}


def test_a_refused_model_stands_down_in_the_passes_already_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand = _Stand(monkeypatch, pairs=20, delay=0.01, subjects=("bad/name", "a/m1"))
    stand.refuse.add("bad/name")
    conf = _conf(concurrency=4, blocks=[EvalBlock.DIRECT, EvalBlock.DENIAL_LOOP])

    out = scheduler.measure(SPACE, conf)

    # Both its passes started together; neither asked the whole set.
    assert stand.asked("bad/name") < 20
    assert stand.asked("a/m1") >= 20
    assert sum("bad/name" in line for line in out.failures) == 1
    stopped = [t for t in out.pass_times if t.model == "bad/name"]
    assert stopped and all("refused" in t.stopped for t in stopped)


def test_a_refused_judge_stands_down_and_the_panel_goes_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand = _Stand(monkeypatch, pairs=10, delay=0.01, judges=("j/one", "bad/judge"))
    stand.refuse.add("bad/judge")
    conf = _conf(concurrency=2)

    out = scheduler.measure(SPACE, conf)

    assert stand.asked("bad/judge") <= 2
    assert stand.asked("j/one") == 10
    assert any("bad/judge" in line for line in out.failures)


def test_the_failure_streak_belongs_to_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that has gone quiet fails in every pass; the streak counts them all."""
    stand = _Stand(monkeypatch, pairs=10, delay=0.005)
    stand.fail.add("a/m1")
    conf = _conf(
        concurrency=2,
        max_consecutive_failures=4,
        arms=[ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT],
    )

    out = scheduler.measure(SPACE, conf)

    # Two passes of ten: a per-pass streak would ask 8 at least.
    assert stand.asked("a/m1") <= 6
    assert all("in a row failed" in t.stopped for t in out.pass_times)


def test_a_shared_streak_stops_every_member_and_resets_on_success() -> None:
    streak = Streak()
    one = Progress(total=10, give_up_after=3, shared=streak)
    two = Progress(total=10, give_up_after=3, shared=streak)
    streak.members += [one, two]

    one.step(failed=True)
    two.step(failed=True)
    one.step()
    two.step(failed=True)
    assert not one.stopped and streak.count == 1

    one.step(failed=True)
    two.step(failed=True)
    assert one.stopped and two.stopped


def test_a_cancel_stops_the_passes_in_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    stand = _Stand(monkeypatch, pairs=40, delay=0.01, subjects=("a/m1", "b/m2"))
    monkeypatch.setattr(parallel.Launch, "HALT_EVERY", 0.01)
    conf = _conf(concurrency=2)
    started = time.monotonic()

    class Owner:
        def planned(self, passes: int) -> None: ...

        def phase(self, phase: JobPhase, message: str = "") -> None: ...

        def pass_started(
            self, index: int, arm: str, block: str, model: str
        ) -> None: ...

        def pass_done(self, index: int, label: str) -> None: ...

        def watcher(self, label: str) -> Any:
            return None

        def stop_requested(self) -> bool:
            return time.monotonic() - started > 0.1

    scheduler.measure(SPACE, conf, observer=Owner())

    # Two passes of forty questions, an answer and a verdict each.
    assert len(stand.calls) < 2 * 40 * 2 / 2


# --- Monte Carlo ---------------------------------------------------------------


def test_the_repeats_of_one_question_go_side_by_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand = _Stand(monkeypatch, pairs=1, delay=0.05)
    conf = _conf(
        concurrency=16,
        blocks=[EvalBlock.MONTE_CARLO],
        monte_carlo_temperatures=[0.3, 0.9],
        monte_carlo_trials=3,
    )

    started = time.monotonic()
    out = scheduler.measure(SPACE, conf)
    took = time.monotonic() - started

    # One question: the first answer and judge, then six repeats of an answer
    # and a grade each. In turn that is 14 calls; side by side about 4.
    assert stand.peak >= 6
    assert took < 14 * 0.05
    assert out.graded == 1


def test_the_repeats_keep_the_plan_order() -> None:
    conf = _conf(monte_carlo_temperatures=[0.3, 0.9], monte_carlo_trials=2)
    plan = monte_carlo_plan(conf)
    assert plan == [0.3, 0.3, 0.9, 0.9]

    outcome = tally_monte_carlo(
        [
            Trial(0.3, "A", True),
            None,
            Trial(0.9, "a", False),
            Trial(0.9, "B", True),
        ]
    )

    assert [e["trial"] for e in outcome.log] == [1, 2, 3]
    assert [e["temperature"] for e in outcome.log] == [0.3, 0.9, 0.9]
    assert outcome.by_temperature == {"0.3": 1.0, "0.9": 0.5}
    assert outcome.consistency == round(2 / 3, 4)
    assert outcome.note == "failed attempts: 1"


# --- rebuild: older cohorts' leftovers -------------------------------------------


def _db_ready() -> bool:
    from syft_benchmark.db import QaPair, session_scope

    try:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE.key))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


@pytest.mark.skipif(not _db_ready(), reason="no benchmark database")
@pytest.mark.parametrize("mode", [DatasetMode.REBUILD, DatasetMode.ROLLING])
def test_a_rebuild_does_not_screen_older_cohorts(
    monkeypatch: pytest.MonkeyPatch, mode: DatasetMode
) -> None:
    from syft_benchmark.db import QaPair, session_scope
    from syft_benchmark.generation import filter_stage

    rows = [
        QaPair(
            id=f"pytest-cohort-{cohort}",
            space=SPACE.key,
            generator="qa",
            task_type="factual",
            doc_id="doc-1",
            question=f"Question {cohort}?",
            answer="Answer",
            context="Answer.",
            status=PairStatus.PENDING.value,
            model="gen/model",
            question_hash=cohort,
            cohort=cohort,
            meta={},
        )
        for cohort in ("20260101-0000", "20261001-0000")
    ]
    ids = [row.id for row in rows]
    with session_scope() as session:
        session.add_all(rows)
    screened: list[str] = []
    monkeypatch.setattr(
        filter_stage.Screening, "screen", lambda self, row: screened.append(row.id)
    )
    try:
        report = filter_stage.filter_pending(
            SPACE, settings=_conf(dataset_mode=mode, filter_model=None)
        )
    finally:
        with session_scope() as session:
            session.execute(delete(QaPair).where(QaPair.space == SPACE.key))

    if mode is DatasetMode.REBUILD:
        assert screened == ["pytest-cohort-20261001-0000"]
        assert "1 pending from older cohorts not screened" in report.notes
    else:
        assert sorted(screened) == ids
