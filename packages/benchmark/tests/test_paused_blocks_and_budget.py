"""The temporary pause of the expensive blocks, and the per-job spending cap."""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import ContextMode, EvalBlock, Settings, SpaceConfig
from syft_benchmark.control import jobs
from syft_benchmark.llm.cost import cost_meter
from syft_benchmark.scheduler import measure

SPACE = SpaceConfig(key="pytest-space", url="http://localhost:0", endpoint="kb")


@pytest.fixture
def passes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """One subject model; every pass asked is recorded by its block."""
    asked: list[str] = []

    class Provider:
        def __init__(self, model: str) -> None:
            self.model = model

    monkeypatch.setattr(
        "syft_benchmark.scheduler.subject_providers", lambda conf: [Provider("model-a")]
    )
    monkeypatch.setattr(
        "syft_benchmark.scheduler.judge_providers", lambda conf: [Provider("judge")]
    )

    async def fake_run_pass(space: Any, mode: Any, **kwargs: Any) -> list[Any]:
        asked.append(kwargs["block"].value)
        return []

    monkeypatch.setattr("syft_benchmark.scheduler.arun_pass", fake_run_pass)
    return asked


def test_denial_loop_and_monte_carlo_are_not_run_even_when_chosen(
    passes: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "syft_benchmark.scheduler.PAUSED_BLOCKS",
        frozenset({EvalBlock.DENIAL_LOOP, EvalBlock.MONTE_CARLO}),
    )
    conf = Settings(
        arms=[ContextMode.CLOSED_BOOK],
        blocks=[EvalBlock.DIRECT, EvalBlock.DENIAL_LOOP, EvalBlock.MONTE_CARLO],
        generate_in_cycle=False,
    )

    out = measure(SPACE, conf)

    assert passes == ["direct"]
    assert "paused: denial_loop, monte_carlo" in out.notes


def test_a_job_is_stopped_once_its_calls_reach_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(jobs, "MAX_JOB_USD", 1.0)
    reporter = jobs.Reporter("pytest-cap")

    with cost_meter(job_id="pytest-cap") as meter:
        meter.add(0.6, "subjects")
        reporter._check_budget()
        assert reporter.cancelled is False
        assert reporter.budget_problem() == []

        meter.add(0.5, "judges")
        reporter._check_budget()

    assert reporter.cancelled is True
    assert reporter.budget_problem() == ["over_budget: $1.10 spent, the cap is $1"]


def test_a_run_summary_says_who_stopped_the_job() -> None:
    from syft_benchmark.control.report_routes import _stopped
    from syft_benchmark.db.models import Job

    def job(state: str, error: str = "") -> Job:
        return Job(id="j", target="t", state=state, error=error)

    capped = job("cancelled", "over_budget: $100.12 spent, the cap is $100")
    assert _stopped(capped) == "spending_cap"
    assert _stopped(job("cancelled")) == "owner"
    assert _stopped(job("succeeded", "over_budget: stale")) is None
