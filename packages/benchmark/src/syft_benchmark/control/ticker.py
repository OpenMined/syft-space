"""The schedule, executed.

A target has carried ``schedule`` and ``schedule_at`` since the settings form
had them, and nothing read the fields: the owner set a nightly measurement and
nothing ever happened. The only thing that ran on a schedule was
``syft-benchmark cycle`` on the host — a second process, outside the service,
that a container leaves behind.

So the schedule moves in here, beside the queue. This thread decides *when*, the
worker decides *what next*, and both go through the same table, so a scheduled
measurement differs from a pressed button only by ``trigger``.

**The hour is UTC**, because nothing else can be honest: a container knows
nothing of the owner's night, and a service that took its own clock for it would
shift every schedule the day the host moved.

The planned moment is stored rather than recomputed — see ``Target.next_run_at``
for why.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from syft_benchmark.config import Settings, get_settings
from syft_benchmark.control.jobs import enqueue
from syft_benchmark.control.schemas import RunRequest
from syft_benchmark.db.models import Target
from syft_benchmark.db.session import session_scope
from syft_benchmark.scheduler import next_fire, parse_interval

# Finer than any schedule anybody sets — the shortest interval that makes sense
# here is hours — and a tick is one indexed query.
TICK_SECONDS = 30.0

# The trigger written on a job this thread creates. A nightly measurement and
# one somebody started by hand are the same work but not the same fact.
SCHEDULE = "schedule"


def plan(target: Target, *, now: datetime) -> datetime | None:
    """When this target should next be measured, or None if it should not be.

    Args:
        now: The present moment, timezone-aware and in UTC
    """
    if not target.enabled or not target.schedule:
        return None
    try:
        interval = parse_interval(target.schedule)
    except ValueError:
        logger.warning(
            f"target {target.key}: the schedule {target.schedule!r} cannot be read "
            f"— expected a form such as 24h, 6h or 90m; the target is not scheduled"
        )
        return None
    if interval <= 0:
        logger.warning(
            f"target {target.key}: the schedule {target.schedule!r} is not a "
            f"positive interval; the target is not scheduled"
        )
        return None
    try:
        return next_fire(interval, target.schedule_at, now=now)
    except ValueError:
        logger.warning(
            f"target {target.key}: the hour {target.schedule_at!r} cannot be read "
            f"— expected HH:MM in UTC; the target is not scheduled"
        )
        return None


def tick(session: Session, *, now: datetime | None = None) -> list[str]:
    """One pass over the schedule: plan what has no plan, start what is due.

    A target seen for the first time is planned forward and not measured on that
    pass. One whose moment is in the past is measured once and planned forward
    from now: three nights missed are one measurement overdue, not three owed.

    Args:
        session: The open session; the caller commits
        now: The present moment; None — this one, in UTC

    Returns:
        The keys of the targets a measurement was queued for
    """
    moment = now or datetime.now(UTC)
    started: list[str] = []

    for target in session.scalars(select(Target).where(Target.enabled.is_(True))):
        if not target.schedule:
            # A schedule taken off leaves no plan behind: otherwise switching it
            # back on a month later would fire against a moment long past.
            target.next_run_at = None
            continue

        upcoming = plan(target, now=moment)
        if upcoming is None:
            target.next_run_at = None
            continue

        if target.next_run_at is None:
            target.next_run_at = upcoming
            logger.info(
                f"target {target.key}: scheduled every {target.schedule}"
                + (f" at {target.schedule_at} UTC" if target.schedule_at else "")
                + f", first at {target.next_run_at:%Y-%m-%d %H:%M} UTC"
            )
            continue

        if target.next_run_at > moment:
            continue

        # A measurement that outran its own schedule is not overtaken: enqueue
        # returns the job already standing there. The plan moves forward anyway,
        # so the target does not try again on every tick.
        job = enqueue(session, target, RunRequest(), trigger=SCHEDULE)
        target.next_run_at = upcoming
        started.append(target.key)
        logger.info(
            f"target {target.key}: the schedule fired, job {job.id}; "
            f"next at {target.next_run_at:%Y-%m-%d %H:%M} UTC"
        )

    return started


class Ticker:
    """The thread that watches the schedule.

    Separate from the worker: that one is busy for hours with a measurement, and
    a schedule looked at only between jobs is looked at exactly when it need not
    be.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="benchmark-ticker", daemon=True
        )
        self._thread.start()
        logger.info("the schedule thread has started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        conf = self.settings or get_settings()
        while not self._stop.is_set():
            try:
                with session_scope(conf) as session:
                    tick(session)
            except Exception as exc:  # noqa: BLE001 - the database may have blinked
                # The thread outlives a failed pass: a schedule that stopped
                # until the next restart is worse than one that missed a window,
                # because nobody would notice.
                logger.warning(f"the schedule could not be read: {exc}")
            self._stop.wait(TICK_SECONDS)
