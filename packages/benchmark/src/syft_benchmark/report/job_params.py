"""What a job keeps about its launch: the ``jobs.params`` snapshot, times, state.

The snapshot freezes the judging panel, the web check gate, the article window,
the cost, the build stats and the timing, so a run is reported as it was
launched, not as the settings read today.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from syft_benchmark.config import JobState, ManualStatusPriority, Settings
from syft_benchmark.db.models import Job
from syft_benchmark.db.session import session_scope

ACTIVE_STATES = (JobState.QUEUED.value, JobState.RUNNING.value)

# Keys of the snapshot a job carries in ``jobs.params``.
JUDGE_PANEL = "judge_panel"
JUDGE_POLICY = "judge_policy"
PRIMARY_JUDGE = "primary_judge"
# The web check gate the launch asked through.
WEB_CHECK_MODEL = "web_check_model"
WEB_CHECK_JUDGE = "web_check_judge"
MANUAL_PRIORITY = "manual_status_priority"
# The article window of a pipeline launch (``document_window_days``).
WINDOW_DAYS = "window_days"
# What the job spent: {spend_before, spend_after, usd, usd_calls, total_usd,
# by_role} (report API, "Cost and time").
COST = "cost"
# The build per kind (``pipeline.KindStats.as_dict``).
GENERATION = "generation"
# Where the job's time went (``runs.timing``; report API, "Timing").
TIMING = "timing"
SNAPSHOT_KEYS = frozenset(
    {
        JUDGE_PANEL,
        JUDGE_POLICY,
        PRIMARY_JUDGE,
        WEB_CHECK_MODEL,
        WEB_CHECK_JUDGE,
        MANUAL_PRIORITY,
        WINDOW_DAYS,
        COST,
        GENERATION,
        TIMING,
    }
)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def is_finished(job: Job) -> bool:
    return job.state not in ACTIVE_STATES


def configured_panel(settings: Settings) -> list[str]:
    """The judges as configured, primary first."""
    return list(dict.fromkeys(settings.judge_models or [settings.judge_model]))


def web_check_judge(settings: Settings) -> str:
    """The web check judge: ``filter_judge_model``, else Judge 1; empty without
    a web check model."""
    if not settings.filter_model:
        return ""
    if settings.filter_judge_model:
        return settings.filter_judge_model
    panel = configured_panel(settings)
    return panel[0] if panel else ""


def judging_snapshot(settings: Settings) -> dict[str, Any]:
    """The judging and the web check gate a launch goes by, for ``jobs.params``."""
    return {
        JUDGE_PANEL: configured_panel(settings),
        JUDGE_POLICY: settings.judge_policy.value,
        WEB_CHECK_MODEL: settings.filter_model or "",
        WEB_CHECK_JUDGE: web_check_judge(settings),
        MANUAL_PRIORITY: settings.manual_status_priority.value,
    }


def dataset_snapshot(settings: Settings) -> dict[str, Any]:
    """The article window a pipeline launch builds and asks from."""
    return {WINDOW_DAYS: settings.document_window_days}


def window_days_of(job: Job) -> int | None:
    """The job's article window in days; None when not recorded."""
    days = (job.params or {}).get(WINDOW_DAYS)
    return days if isinstance(days, int) and not isinstance(days, bool) else None


def job_panel(job: Job) -> list[str]:
    """The judges configured when the job ran, primary first; empty if unknown."""
    panel = (job.params or {}).get(JUDGE_PANEL)
    if not isinstance(panel, list):
        return []
    return [j for j in dict.fromkeys(panel) if isinstance(j, str) and j]


def job_gate(job: Job) -> Settings | None:
    """The web check gate of the job's launch; None for a job without a snapshot."""
    params = job.params or {}
    if WEB_CHECK_MODEL not in params:
        return None
    return Settings.model_construct(
        filter_model=str(params.get(WEB_CHECK_MODEL) or "") or None,
        manual_status_priority=ManualStatusPriority(
            params.get(MANUAL_PRIORITY) or ManualStatusPriority.FILTER.value
        ),
    )


def record_generation(
    job_id: str, kinds: list[dict[str, Any]], settings: Settings | None = None
) -> None:
    """Keep the job's per-kind build stats in its params."""
    with session_scope(settings) as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.params = {**(job.params or {}), GENERATION: kinds}


def generation_of(job: Job) -> list[dict[str, Any]]:
    """The job's per-kind build stats; empty when none were kept."""
    kinds = (job.params or {}).get(GENERATION)
    return [k for k in kinds if isinstance(k, dict)] if isinstance(kinds, list) else []


def how_tested(job: Job) -> dict[str, Any]:
    """The job's web check model and judge, and what it spent (``method``)."""
    params = job.params or {}
    cost = params.get(COST)
    return {
        WEB_CHECK_MODEL: str(params.get(WEB_CHECK_MODEL) or "") or None,
        WEB_CHECK_JUDGE: str(params.get(WEB_CHECK_JUDGE) or "") or None,
        COST: _cost(cost) if isinstance(cost, dict) else None,
    }


def _cost(cost: dict[str, Any]) -> dict[str, Any]:
    """The stored cost; ``total_usd`` and ``by_role`` null where not recorded."""
    by_role = cost.get("by_role")
    return {
        **cost,
        "total_usd": cost.get("total_usd"),
        "by_role": dict(by_role) if isinstance(by_role, dict) else None,
    }


def job_times(job: Job) -> dict[str, Any]:
    """When the job started and finished, and how long it took (seconds);
    null while unknown."""
    took = (
        round((job.finished_at - job.started_at).total_seconds(), 2)
        if job.started_at is not None and job.finished_at is not None
        else None
    )
    return {
        "started_at": iso(job.started_at),
        "finished_at": iso(job.finished_at),
        "duration_s": took,
    }


def timing_of(job: Job) -> dict[str, Any] | None:
    """The job's phase, pass and call timings; None when not kept."""
    timing = (job.params or {}).get(TIMING)
    return dict(timing) if isinstance(timing, dict) else None
