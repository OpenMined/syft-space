"""Filter decisions stamped on a pair, one per job that decided on it.

``meta.screening`` is a list of records ``{stage, outcome, note, reason,
job_id, at}`` (plus ``web``, the web check record, for that stage, and
``gate``, the control gate's call, for the control stage). A job's
Filter list is every pair carrying a record with its id, including pairs an
earlier job wrote. The writer job stays ``qa_pairs.job_id``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SCREENING = "screening"

# Stages and outcomes of a decision.
GROUNDING = "grounding"
CONTROL = "control"
WEB_CHECK = "web_check"
STAGES = (GROUNDING, CONTROL, WEB_CHECK)

KEPT = "kept"
REMOVED = "removed"
FAILED = "failed"
SKIPPED = "skipped"
OUTCOMES = (KEPT, REMOVED, FAILED, SKIPPED)

# How many records a pair keeps; the oldest go first.
_KEPT_RECORDS = 20


def record(
    *,
    job_id: str,
    stage: str,
    outcome: str,
    note: str = "",
    reason: str | None = None,
    web: dict[str, Any] | None = None,
    gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One decision, stamped now."""
    entry: dict[str, Any] = {
        "stage": stage,
        "outcome": outcome,
        "note": note,
        "reason": reason,
        "job_id": job_id,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if web is not None:
        entry["web"] = web
    if gate is not None:
        entry["gate"] = gate
    return entry


def stamped(
    meta: dict[str, Any] | None, entry: dict[str, Any] | None
) -> dict[str, Any]:
    """``{"screening": [...]}`` with ``entry`` appended; empty with no entry."""
    if entry is None:
        return {}
    earlier = [r for r in (meta or {}).get(SCREENING) or [] if isinstance(r, dict)]
    return {SCREENING: [*earlier, entry][-_KEPT_RECORDS:]}


def of_job(meta: dict[str, Any] | None, job_id: str) -> dict[str, Any] | None:
    """The latest decision ``job_id`` made on this pair; None — it made none."""
    found = [
        r
        for r in (meta or {}).get(SCREENING) or []
        if isinstance(r, dict) and r.get("job_id") == job_id
    ]
    return found[-1] if found else None


def outcome_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(OUTCOMES, 0)
    for entry in entries:
        outcome = str(entry.get("outcome") or "")
        if outcome in counts:
            counts[outcome] += 1
    return counts
