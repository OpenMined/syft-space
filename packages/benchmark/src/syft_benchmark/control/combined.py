"""Combined runs: checking, making, growing and dropping them, and the
ticker's combining per period.

A combined run is a ``Job`` of kind ``combined``, finished at creation, whose
members (``combined_members``) are leaf jobs; naming a combined run as a
member takes its members instead. Members must be finished, measured, of one
target and measured the same way: one ``settings_hash`` or, for jobs without
one, one judging snapshot and the same runs with the same ``Run.params``.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from syft_benchmark.config import JobPhase, JobState
from syft_benchmark.control.schemas import COMBINE_PERIOD_HOURS
from syft_benchmark.db.models import CombinedMember, Job, Result, Run, Target
from syft_benchmark.db.run_cache import invalidate_run
from syft_benchmark.report import job_params
from syft_benchmark.report.combined_view import (
    COMBINED,
    COMBINED_AT,
    MEMBERS,
    ORIGIN,
    ORIGIN_AUTO,
    ORIGIN_MANUAL,
    PERIOD,
    PERIOD_START,
    TITLE,
    is_combined,
    member_ids,
    member_jobs,
)
from syft_benchmark.report.run_view import ARM_OF
from syft_benchmark.runs.judge_stage import OWNER_OVERRIDE

# How far back the ticker combines periods it has not dealt with.
LOOKBACK = timedelta(days=7)

# The judging snapshot compared for jobs without a settings hash.
JUDGING_FIELDS = (
    job_params.JUDGE_PANEL,
    job_params.JUDGE_POLICY,
    job_params.WEB_CHECK_MODEL,
    job_params.WEB_CHECK_JUDGE,
)


class UnknownJob(LookupError):
    """A job id that is not a job of this target."""

    def __init__(self, job_id: str) -> None:
        super().__init__(job_id)
        self.job_id = job_id


class TooFew(ValueError):
    """Fewer than two distinct leaf jobs."""


class NotCombinable(ValueError):
    """The jobs differ in what makes runs comparable."""

    def __init__(self, differences: list[dict[str, Any]]) -> None:
        super().__init__(f"{len(differences)} differences")
        self.differences = differences


def leaves(session: Session, target: str, job_ids: Sequence[str]) -> list[Job]:
    """The leaf jobs ``job_ids`` name, combined runs flattened to their
    members, without repeats, oldest first.

    Raises:
        UnknownJob: an id is not a job of ``target``
    """
    found: dict[str, Job] = {}
    for job_id in job_ids:
        job = session.get(Job, job_id)
        if job is None or job.target != target:
            raise UnknownJob(job_id)
        if is_combined(job):
            for member in member_jobs(session, job.id):
                found.setdefault(member.id, member)
        else:
            found.setdefault(job.id, job)
    return sorted(found.values(), key=lambda j: (j.created_at, j.id))


def _measured(session: Session, job_ids: Sequence[str]) -> set[str]:
    """Those of ``job_ids`` that have runs."""
    return set(
        session.scalars(
            select(Run.job_id).where(Run.job_id.in_(list(job_ids))).distinct()
        )
    )


def _difference(
    field: str, jobs: Sequence[Job], values: dict[str, Any]
) -> dict[str, Any]:
    return {
        "field": field,
        "values": [{"job_id": j.id, "value": values.get(j.id)} for j in jobs],
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _differs(values: dict[str, Any]) -> bool:
    return len({_canonical(v) for v in values.values()}) > 1


def _run_methods(session: Session, job_id: str) -> dict[str, list[Any]]:
    """``"arm / block / model"`` -> the distinct ``Run.params`` of the job's
    measured runs."""
    out: dict[str, dict[str, Any]] = defaultdict(dict)
    for mode, block, model, params in session.execute(
        select(Run.context_mode, Run.block, Run.model, Run.params).where(
            Run.job_id == job_id,
            Run.context_mode.in_(list(ARM_OF)),
            Run.judge_model != OWNER_OVERRIDE,
        )
    ):
        out[f"{mode} / {block} / {model}"][_canonical(params or {})] = params or {}
    return {key: [found[k] for k in sorted(found)] for key, found in out.items()}


def differences(session: Session, jobs: Sequence[Job]) -> list[dict[str, Any]]:
    """What keeps ``jobs`` from being combined: ``[{field, values: [{job_id,
    value}]}]``; empty — nothing."""
    out: list[dict[str, Any]] = []

    def add(field: str, values: dict[str, Any]) -> None:
        out.append(_difference(field, jobs, values))

    if any(j.state in job_params.ACTIVE_STATES for j in jobs):
        add("state", {j.id: j.state for j in jobs})
    measured = _measured(session, [j.id for j in jobs])
    if len(measured) < len(jobs):
        add("measured", {j.id: j.id in measured for j in jobs})
    if len({j.target for j in jobs}) > 1:
        add("target", {j.id: j.target for j in jobs})

    params = {j.id: j.params or {} for j in jobs}
    hashes = {j.id: params[j.id].get(job_params.SETTINGS_HASH) for j in jobs}
    if all(hashes.values()):
        if _differs(hashes):
            found = _snapshot_differences(jobs)
            if found:
                out.extend(found)
            else:
                add(job_params.SETTINGS_HASH, hashes)
        return out

    for name in JUDGING_FIELDS:
        values = {j.id: params[j.id].get(name) for j in jobs}
        if _differs(values):
            add(name, values)
    methods = {j.id: _run_methods(session, j.id) for j in jobs}
    for key in sorted({k for m in methods.values() for k in m}):
        values = {j.id: methods[j.id].get(key) for j in jobs}
        if _differs(values):
            add(f"runs: {key}", values)
    return out


def _snapshot_differences(jobs: Sequence[Job]) -> list[dict[str, Any]]:
    """The hashed settings that differ, read from the snapshots."""
    snapshots: dict[str, dict[str, Any]] = {}
    for j in jobs:
        found = (j.params or {}).get(job_params.SETTINGS_SNAPSHOT)
        if not isinstance(found, dict):
            return []
        snapshots[j.id] = found
    keys = sorted({k for s in snapshots.values() for k in s} - job_params.HASH_EXCLUDED)
    out = []
    for key in keys:
        values = {job_id: s.get(key) for job_id, s in snapshots.items()}
        if _differs(values):
            out.append(_difference(key, jobs, values))
    return out


def repeated_questions(session: Session, job_ids: Sequence[str]) -> int:
    """Questions answered in the measured arms of more than one of the jobs."""
    seen: dict[str, set[str]] = defaultdict(set)
    for qa_id, job_id in session.execute(
        select(Result.qa_id, Run.job_id)
        .join(Run, Run.id == Result.run_id)
        .where(Run.job_id.in_(list(job_ids)), Run.context_mode.in_(list(ARM_OF)))
        .distinct()
    ):
        seen[qa_id].add(job_id)
    return sum(1 for jobs in seen.values() if len(jobs) > 1)


def check(session: Session, target: str, job_ids: Sequence[str]) -> dict[str, Any]:
    """Whether the jobs combine: ``{ok, members, settings_hash, differences,
    repeated_questions}``.

    Raises:
        UnknownJob: an id is not a job of ``target``
    """
    jobs = leaves(session, target, job_ids)
    found = differences(session, jobs)
    if len(jobs) < 2:
        found.insert(0, {"field": "members", "values": []})
    return {
        "ok": not found,
        "members": [j.id for j in jobs],
        "settings_hash": _shared_hash(jobs),
        "differences": found,
        "repeated_questions": repeated_questions(session, [j.id for j in jobs]),
    }


def _shared_hash(jobs: Sequence[Job]) -> str | None:
    hashes = {(j.params or {}).get(job_params.SETTINGS_HASH) for j in jobs}
    found = hashes.pop() if len(hashes) == 1 else None
    return found if isinstance(found, str) and found else None


def _checked(session: Session, jobs: list[Job]) -> list[Job]:
    if len(jobs) < 2:
        raise TooFew("a combined run needs at least two distinct runs")
    found = differences(session, jobs)
    if found:
        raise NotCombinable(found)
    return jobs


def _set_members(session: Session, combined: Job, jobs: Sequence[Job]) -> None:
    """Make ``jobs`` the members, oldest first, and the record's times span
    theirs."""
    session.execute(
        delete(CombinedMember).where(CombinedMember.combined_job_id == combined.id)
    )
    session.flush()
    for n, job in enumerate(jobs):
        session.add(
            CombinedMember(
                combined_job_id=combined.id, member_job_id=job.id, position=n
            )
        )
    started = [j.started_at for j in jobs if j.started_at is not None]
    finished = [j.finished_at for j in jobs if j.finished_at is not None]
    combined.created_at = min(j.created_at for j in jobs)
    combined.started_at = min(started) if started else None
    combined.finished_at = max(finished) if finished else None
    first = jobs[0].params or {}
    combined.params = {
        **(combined.params or {}),
        MEMBERS: [j.id for j in jobs],
        job_params.SETTINGS_HASH: _shared_hash(jobs),
        job_params.WEB_CHECK_MODEL: first.get(job_params.WEB_CHECK_MODEL),
        job_params.WEB_CHECK_JUDGE: first.get(job_params.WEB_CHECK_JUDGE),
    }
    session.flush()
    invalidate_run(session, combined.id)


def create(
    session: Session,
    target: str,
    job_ids: Sequence[str],
    *,
    title: str | None = None,
    origin: str = ORIGIN_MANUAL,
    period: str | None = None,
    period_start: datetime | None = None,
) -> Job:
    """A new combined run of the leaf jobs ``job_ids`` name.

    Raises:
        UnknownJob: an id is not a job of ``target``
        TooFew: fewer than two distinct leaf jobs
        NotCombinable: the jobs differ (its ``differences``)
    """
    jobs = _checked(session, leaves(session, target, job_ids))
    combined = Job(
        id=uuid.uuid4().hex,
        target=target,
        state=JobState.SUCCEEDED.value,
        phase=JobPhase.DONE.value,
        kind=COMBINED,
        trigger=origin,
        params={
            ORIGIN: origin,
            PERIOD: period,
            PERIOD_START: job_params.iso(period_start),
            TITLE: title or None,
            COMBINED_AT: datetime.now(UTC).isoformat(),
        },
    )
    session.add(combined)
    session.flush()
    _set_members(session, combined, jobs)
    return combined


def add_members(session: Session, combined: Job, job_ids: Sequence[str]) -> Job:
    """Add the leaf jobs ``job_ids`` name to a combined run.

    Raises:
        UnknownJob, TooFew, NotCombinable: as ``create``
    """
    jobs = leaves(
        session, combined.target, [*member_ids(session, combined.id), *job_ids]
    )
    _set_members(session, combined, _checked(session, jobs))
    return combined


def drop_member(session: Session, job: Job) -> None:
    """Take a job being deleted out of every combined run; one left with
    fewer than two members is deleted."""
    holders = session.scalars(
        select(CombinedMember.combined_job_id).where(
            CombinedMember.member_job_id == job.id
        )
    ).all()
    for combined_id in holders:
        combined = session.get(Job, combined_id)
        if combined is None:
            continue
        remaining = [m for m in member_jobs(session, combined_id) if m.id != job.id]
        if len(remaining) < 2:
            session.execute(
                delete(CombinedMember).where(
                    CombinedMember.combined_job_id == combined_id
                )
            )
            invalidate_run(session, combined_id)
            session.delete(combined)
        else:
            _set_members(session, combined, remaining)
    session.flush()


# --- combining per period ---------------------------------------------------


def _floor(moment: datetime, step: timedelta) -> datetime:
    midnight = datetime.combine(moment.date(), time.min, tzinfo=UTC)
    return midnight + ((moment - midnight) // step) * step


def period_title(period: str, start: datetime) -> str:
    when = start.strftime("%Y-%m-%d") if period == "24h" else f"{start:%Y-%m-%d %H:%M}"
    return f"{period} · {when}"


class PeriodCombiner:
    """Combines one target's runs over each closed period of its
    ``combine_periods`` not yet dealt with, at most ``LOOKBACK`` back.

    A period with a job still queued or running waits, and so do the later
    ones of that length. A period's finished, measured leaf jobs are grouped by
    ``settings_hash`` (jobs without one are left to combining by hand); each
    group of two or more becomes a combined run. ``target.combine_marks``
    keeps, per period length, the start of the last period dealt with.
    """

    def __init__(self, session: Session, target: Target, now: datetime) -> None:
        self.session = session
        self.target = target
        self.now = now
        self.made: list[str] = []

    def run(self) -> list[str]:
        """Combine what is due; the new combined runs' ids."""
        marks = dict(self.target.combine_marks or {})
        for period in self.target.combine_periods or []:
            hours = COMBINE_PERIOD_HOURS.get(period)
            if hours is None:
                continue
            step = timedelta(hours=hours)
            start = _floor(self.now - LOOKBACK, step)
            if mark := marks.get(period):
                start = max(start, datetime.fromisoformat(mark) + step)
            while start + step <= self.now and self._combine(period, start, step):
                marks[period] = start.isoformat()
                start += step
        if marks != (self.target.combine_marks or {}):
            self.target.combine_marks = marks
        return self.made

    def _combine(self, period: str, start: datetime, step: timedelta) -> bool:
        """Combine one period; False: a job of it is still active."""
        jobs = self.session.scalars(
            select(Job)
            .where(
                Job.target == self.target.key,
                Job.kind != COMBINED,
                Job.created_at >= start,
                Job.created_at < start + step,
            )
            .order_by(Job.created_at, Job.id)
        ).all()
        if any(j.state in job_params.ACTIVE_STATES for j in jobs):
            return False
        measured = _measured(self.session, [j.id for j in jobs])
        groups: dict[str, list[str]] = defaultdict(list)
        for job in jobs:
            found = (job.params or {}).get(job_params.SETTINGS_HASH)
            if job.id in measured and isinstance(found, str) and found:
                groups[found].append(job.id)
        for settings_hash, ids in groups.items():
            if len(ids) >= 2 and not self._made_before(period, start, settings_hash):
                self._create(period, start, ids)
        return True

    def _made_before(self, period: str, start: datetime, settings_hash: str) -> bool:
        for params in self.session.scalars(
            select(Job.params).where(
                Job.target == self.target.key, Job.kind == COMBINED
            )
        ):
            if (
                (params or {}).get(ORIGIN) == ORIGIN_AUTO
                and params.get(PERIOD) == period
                and params.get(PERIOD_START) == start.isoformat()
                and params.get(job_params.SETTINGS_HASH) == settings_hash
            ):
                return True
        return False

    def _create(self, period: str, start: datetime, ids: list[str]) -> None:
        where = (
            f"target {self.target.key}: the {period} period at "
            f"{start:%Y-%m-%d %H:%M} UTC"
        )
        try:
            combined = create(
                self.session,
                self.target.key,
                ids,
                title=period_title(period, start),
                origin=ORIGIN_AUTO,
                period=period,
                period_start=start,
            )
        except (TooFew, NotCombinable) as exc:
            logger.warning(f"{where} was not combined: {exc}")
            return
        self.made.append(combined.id)
        logger.info(f"{where}: combined {len(ids)} runs as {combined.id}")


def combine_due(
    session: Session, target: Target, *, now: datetime | None = None
) -> list[str]:
    """Combine what is due for ``target`` (``PeriodCombiner``); the new ids."""
    return PeriodCombiner(session, target, now or datetime.now(UTC)).run()


def combine_all(session: Session, *, now: datetime | None = None) -> list[str]:
    """``combine_due`` over every target that combines."""
    made: list[str] = []
    for target in session.scalars(select(Target).order_by(Target.key)):
        if target.combine_periods:
            made += combine_due(session, target, now=now)
    return made
