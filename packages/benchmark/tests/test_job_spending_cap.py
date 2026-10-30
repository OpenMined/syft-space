"""The per-job spending cap."""

from __future__ import annotations

from syft_benchmark.config import Settings
from syft_benchmark.control import jobs
from syft_benchmark.llm.cost import cost_meter


def test_a_job_is_stopped_once_its_calls_reach_the_cap() -> None:
    reporter = jobs.Reporter("pytest-cap", Settings())
    reporter.max_usd = 1.0

    with cost_meter(job_id="pytest-cap") as meter:
        meter.add(0.6, "subjects")
        reporter._check_budget()
        assert reporter.cancelled is False
        assert reporter.budget_problem() == []

        meter.add(0.5, "judges")
        reporter._check_budget()

    assert reporter.cancelled is True
    assert reporter.budget_problem() == ["over_budget: $1.10 spent, the cap is $1"]


def test_the_cap_defaults_to_100_usd_and_zero_means_none() -> None:
    assert jobs.Reporter("pytest-cap-default", Settings()).max_usd == 100.0
    reporter = jobs.Reporter("pytest-no-cap", Settings(max_job_usd=0))

    with cost_meter(job_id="pytest-no-cap") as meter:
        meter.add(10_000.0, "subjects")
        reporter._check_budget()

    assert reporter.cancelled is False


def test_a_run_summary_says_who_stopped_the_job() -> None:
    from syft_benchmark.control.report_routes import _stopped
    from syft_benchmark.db.models import Job

    def job(state: str, error: str = "") -> Job:
        return Job(id="j", target="t", state=state, error=error)

    capped = job("cancelled", "over_budget: $100.12 spent, the cap is $100")
    assert _stopped(capped) == "spending_cap"
    assert _stopped(job("cancelled")) == "owner"
    assert _stopped(job("succeeded", "over_budget: stale")) is None
