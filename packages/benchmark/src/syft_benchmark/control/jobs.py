"""Jobs: the queue, progress and stopping.

A measurement runs for hours, and an HTTP request does not live that long. So
the launch is torn in two: the route puts a job in the queue and answers at
once, while a worker thread does the work, checking in on the same row. The
owner watches the row rather than waiting for a response.

The queue is shared and strictly sequential. This is not a simplification: a
measurement is bounded not by the processor but by the model provider and by
the node under test itself, and two jobs at once will speed up neither — they
will spoil both. A node answering under double load is not the same node that
answered yesterday, and the numbers will diverge for a reason of their own.

Stopping is a request, not a kill. A run finishes the current question and
exits by itself: half a measurement is data too, its verdicts are already in
the database, and cutting a write off mid-transaction would mean trading a
whole database for a few seconds of waiting.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from syft_benchmark.config import JobPhase, JobState, Settings
from syft_benchmark.control.compose import merge, settings_for
from syft_benchmark.control.schemas import RunRequest
from syft_benchmark.db import store
from syft_benchmark.db.models import Job, Run, Target
from syft_benchmark.db.session import session_scope
from syft_benchmark.publish import payload_for, publish
from syft_benchmark.report.card import build as build_card
from syft_benchmark.runs.parallel import Progress
from syft_benchmark.scheduler import measure

# How often the worker thread looks into the queue. A second is the delay
# between pressing the button and the work starting; a measurement runs for
# hours, seconds are no loss here, and polling the database in a tight loop
# would cost more than any gain.
POLL_SECONDS = 1.0

# A job checks in to the database no more often than once per this many
# seconds. A question takes seconds, and writing the row for each would mean
# hundreds of pointless transactions for the sake of a bar whose motion the eye
# cannot make out anyway.
BEAT_SECONDS = 2.0

# Our own reasons for a job not finishing — as codes. The job's row is read by
# someone else's UI, in their reader's language; the same rule by which the card
# hands out trust.flags. Anything that came from a failed call passes through as
# is: the text of someone else's exception cannot be enumerated, and hiding it
# is worse than showing it untranslated.
TARGET_GONE = "target_gone"
NO_CARD = "no_card"
PUBLISH_REFUSED = "publish_refused"
SERVICE_RESTARTED = "service_restarted"
NOTHING_GRADED = "nothing_graded"
NO_QUESTIONS = "no_questions"
NOTHING_GENERATED = "nothing_generated"

# How much of a failed call goes into the job's row beside the code. A
# provider's refusal says why in its first line; what follows is the request
# echoed back, and the row is read in a UI, not in a log.
SAMPLE_CHARS = 300


def _with_sample(code: str, sample: str) -> str:
    """A reason code and, when there is one, the failed call that explains it.

    A code alone cannot say which failure it was: a spent key, a model name
    with quotes still round it, a network that dropped and a node that is down
    all end a run with zero verdicts. Guessing at the cause in the wording
    would be worse than the code — the guess reads as a finding. So the code
    stays exactly as narrow as it is, and the text that distinguishes the
    causes travels beside it.

    The reasons are joined with semicolons and split apart again by whoever
    renders them, so a semicolon inside the sample would tear one reason into
    lines that mean nothing on their own.
    """
    text = " ".join(sample.split()).replace(";", ",")[:SAMPLE_CHARS]
    return f"{code}: {text}" if text else code


class Reporter:
    """A progress observer that writes into the job's row.

    It also carries cancellation into the measurement: the flag is read from the
    same row that progress is written to, and costs no separate trip to the
    database.
    """

    def __init__(self, job_id: str, settings: Settings | None = None) -> None:
        self.job_id = job_id
        self.settings = settings
        self.passes = 0
        self.total = 0
        self.current = ""
        self.cancelled = False
        self.arm = ""
        self.block = ""
        self.model = ""
        self.step_done = 0
        self.step_total = 0
        self._beat = 0.0

    # --- what the measurement calls ----------------------------------------
    def planned(self, passes: int) -> None:
        self.total = passes
        self._write(force=True)

    def phase(self, phase: JobPhase, message: str = "") -> None:
        self._write(phase=phase, message=message, force=True)

    def pass_started(self, index: int, arm: str, block: str, model: str) -> None:
        # The run has started, but how many questions it holds is not yet known:
        # that comes out after the items are picked. A zero here means "still
        # counting", not "nothing to ask", and until then there is nothing to
        # draw a bar from.
        self.arm, self.block, self.model = arm, block, model
        self.step_done = self.step_total = 0
        self._write(force=True)

    def pass_done(self, index: int, label: str) -> None:
        self.passes = index
        self.current = ""
        self._write(force=True)

    def watcher(self, label: str) -> Callable[[Progress], None]:
        def tick(progress: Progress) -> None:
            self.step_done = progress.done
            self.step_total = progress.total
            self._write()
            if self.cancelled:
                progress.stop("stopped by the owner")

        return tick

    def stop_requested(self) -> bool:
        """Whether the owner has asked for this measurement to stop.

        Asked of the database rather than remembered, because the phases differ
        in how much they report: generation writes no progress at all, so a
        flag that only ever arrived on the back of a write would never reach
        it. Once true it stays true, so the query is made at most once per
        answer.
        """
        if not self.cancelled:
            self._read_cancelled()
        return self.cancelled

    # --- writing -----------------------------------------------------------
    def _write(
        self,
        *,
        phase: JobPhase | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> None:
        """Record progress, and pick up a cancellation while we are here.

        The write is throttled, the read is not. Holding back an UPDATE nobody
        is waiting for, between two frames of a progress bar, costs nothing;
        holding back the cancellation flag costs questions asked and paid for
        after the owner pressed stop. Reading a row by its primary key is the
        cheap half of a trip this run makes anyway.
        """
        now = time.monotonic()
        writing = force or now - self._beat >= BEAT_SECONDS
        if writing:
            self._beat = now
        with session_scope(self.settings) as session:
            if writing:
                values: dict[str, object] = {
                    "done": self.passes,
                    "total": self.total,
                    "message": message if message is not None else self.current,
                    "arm": self.arm,
                    "block": self.block,
                    "model": self.model,
                    "step_done": self.step_done,
                    "step_total": self.step_total,
                }
                if phase is not None:
                    values["phase"] = phase.value
                session.execute(
                    update(Job).where(Job.id == self.job_id).values(**values)
                )
            row = session.get(Job, self.job_id)
            if row is not None and row.cancel_requested:
                self.cancelled = True

    def _read_cancelled(self) -> None:
        """Pick up the flag without writing anything."""
        with session_scope(self.settings) as session:
            row = session.get(Job, self.job_id)
            if row is not None and row.cancel_requested:
                self.cancelled = True


def enqueue(
    session: Session, target: Target, request: RunRequest, *, trigger: str = "manual"
) -> Job:
    """Put a measurement in the queue.

    A second job for the same target is not created — the one already standing
    there is returned. Otherwise a double press of the button would mean a
    double measurement of one node, and it is not fast with the first one as it
    is.
    """
    # Locks the target row for the rest of this transaction, so two concurrent
    # launches for the same target serialize on the check below instead of
    # both seeing "no active job" and both inserting one.
    session.execute(
        select(Target.key).where(Target.key == target.key).with_for_update()
    )
    active = session.scalars(
        select(Job)
        .where(Job.target == target.key)
        .where(Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]))
        .order_by(Job.created_at)
    ).first()
    if active is not None:
        return active

    job = Job(
        id=uuid.uuid4().hex,
        target=target.key,
        state=JobState.QUEUED.value,
        phase=JobPhase.PENDING.value,
        trigger=trigger,
        params=request.model_dump(mode="json", exclude_none=True),
    )
    session.add(job)
    session.flush()
    return job


def cancel(session: Session, job_id: str) -> bool:
    """Ask a job to stop.

    One standing in the queue is removed at once — no work has been done on it
    yet. A running one is marked and exits by itself, having finished the
    current question.
    """
    job = session.get(Job, job_id)
    if job is None or JobState(job.state).final:
        return False
    job.cancel_requested = True
    if job.state == JobState.QUEUED.value:
        job.state = JobState.CANCELLED.value
        job.finished_at = datetime.now(UTC)
    return True


def delete(session: Session, job_id: str) -> str:
    """Discard a finished job: its own row, its runs, and their verdicts.

    An owner's call, not a cascade — which is why it is a separate function
    rather than a foreign key: a job in progress is not touched, and the
    dataset (`qa_pairs`) is not either. That set belongs to the target, is
    shared by every job that ever measured it, and outlives any one of them —
    deleting a run's own data must not quietly thin out the question set every
    other job, past and future, is compared against.

    Returns:
        "deleted", "not_found", or "not_final" (still queued or running — ask
        it to stop first)
    """
    job = session.get(Job, job_id)
    if job is None:
        return "not_found"
    if not JobState(job.state).final:
        return "not_final"
    # `Result.run_id` cascades at the database level; deleting the runs is
    # enough to take their verdicts with them.
    session.execute(sa_delete(Run).where(Run.job_id == job_id))
    session.delete(job)
    return "deleted"


def execute(job_id: str, settings: Settings | None = None) -> None:
    """Carry out a job whole: the dataset, the runs, the card.

    Exceptions are not let out: the worker thread outlives a failed job and
    takes the next one, while the reason stays in the job's row. A dead thread
    would mean the "launch" button had quietly stopped working until the
    service was restarted.

    ``settings``, when given, is the base to read the installation's row on
    top of — never the installation's row itself. The worker thread hands in
    the same object for as long as the process lives, and it is not asked
    again here: ``store.apply`` re-reads the row on every call (cheap, since
    the row is cached until the next write), which is what lets an edit made
    in the settings form just before pressing "run" reach the run it was made
    for, rather than the row as it stood when the process started.
    """
    try:
        conf = store.apply(settings if settings is not None else Settings())
        with session_scope(conf) as session:
            job = session.get(Job, job_id)
            if job is None or job.state != JobState.QUEUED.value:
                return
            target = session.get(Target, job.target)
            if target is None:
                job.state = JobState.FAILED.value
                job.phase = JobPhase.DONE.value
                job.error = TARGET_GONE
                job.finished_at = datetime.now(UTC)
                return
            request = RunRequest.model_validate(job.params or {})
            job.state = JobState.RUNNING.value
            job.started_at = datetime.now(UTC)
            node_conf, space = settings_for(target, conf)

        # The layers from the request itself lie on top of the ones saved on
        # the target and do not change the target: a trial run with a
        # different similarity threshold must not rewrite the setting the
        # ordinary nightly measurement will go by.
        extra = [x for x in (request.instrument, request.probe) if x is not None]
        if extra:
            node_conf = merge(node_conf, *extra)

        # None means "yes" — the ordinary shape of a launch that measures.
        # False is for a launch that only wants the question set refreshed:
        # the runs below, and the card built from them, describe an
        # evaluation that did not happen and have no business existing for
        # this one.
        want_evaluate = request.evaluate if request.evaluate is not None else True

        reporter = Reporter(job_id, conf)
        failures: list[str] = []
        card_payload: dict[str, Any] | None = None
        done = measure(
            space,
            node_conf,
            generate=request.generate,
            evaluate=want_evaluate,
            limit=request.limit,
            observer=reporter,
            job_id=job_id,
        )
        failures = list(done.failures)
        # Outside `want_evaluate` on purpose: a launch that only refreshes the
        # question set can fail this way too.
        if done.generated_nothing:
            failures.append(
                _with_sample(NOTHING_GENERATED, done.generation_failure_sample)
            )
        if want_evaluate:
            if done.had_nothing_to_ask:
                # The set is empty: the freshness window let no document through,
                # or generation has not reached this node yet. Without this line
                # the job would report "passed" without having asked a single
                # question.
                failures.append(NO_QUESTIONS)
            if done.measured_nothing:
                # A full pass over the set, zero verdicts — and without this line
                # the job would report "passed" after twenty seconds in which
                # nothing was measured. The failed call travels with it: the code
                # says only that nothing was graded, and the cause is in the text
                # the provider sent back.
                failures.append(_with_sample(NOTHING_GRADED, done.failure_sample))

            # The card is built from the verdicts that are in the database on
            # the same terms whether or not it is going anywhere: "how did this
            # run go" must not depend on the answer to "does anyone else get to
            # see it". A thin sample is not hidden but named — `trust.flags`
            # carries `few_samples`, and the reader sees how many questions the
            # numbers stand on. Cancelled is a different matter: a run cut off
            # halfway was not a statement.
            if not reporter.cancelled:
                reporter.phase(JobPhase.PUBLISH)
                card = build_card(space.key, space.endpoint, settings=node_conf)
                if card is None:
                    failures.append(NO_CARD)
                else:
                    card_payload = payload_for(card)
                    # Publishing — handing the card to the Space, and from
                    # there to whatever marketplace it is registered with — is
                    # the one part that is optional: the owner ticks it per
                    # run, and its refusal (benchmarks_mode off, an old Space)
                    # is a failure of that step alone, not of the measurement
                    # the card already describes.
                    if request.publish:
                        sent = publish(space, card)
                        if not sent.ok:
                            failures.append(f"{PUBLISH_REFUSED}: {sent.detail}")
    except Exception as exc:  # noqa: BLE001 - the owner needs the cause, not a traceback
        logger.exception(f"job {job_id} failed")
        _finish(job_id, JobState.FAILED, error=str(exc), settings=settings)
        return

    state = JobState.CANCELLED if reporter.cancelled else JobState.SUCCEEDED
    _finish(job_id, state, error="; ".join(failures), card=card_payload, settings=conf)


def _finish(
    job_id: str,
    state: JobState,
    *,
    error: str = "",
    card: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> None:
    """Close a job.

    Failed runs do not make a job a failure: the node may have rebooted in the
    middle of one arm while the others went through and gave numbers. A failure
    is when the job did not reach the end at all.

    ``card``, when given, is kept regardless of ``state`` or ``error``: a run
    that measured fine and only failed to publish still has a card, and it is
    the one place that says so.
    """
    with session_scope(settings) as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        job.state = state.value
        job.phase = JobPhase.DONE.value
        job.error = error
        job.card = card
        job.finished_at = datetime.now(UTC)
        # There is no separate "passed, but not whole" message here: it is
        # visible from the pair "state + a non-empty reason" itself, and a
        # phrase invented for it would be a third place where the same thing is
        # said differently.


def sweep(settings: Settings | None = None) -> int:
    """Close the jobs that outlived a restart of the process.

    A job that was running stopped together with the process, and there is
    nobody to continue it. A row in the "running" state after a restart is an
    eternally live measurement in the UI and a queue locked on that target
    forever.

    Returns:
        How many jobs were closed
    """
    with session_scope(settings) as session:
        stale = list(
            session.scalars(select(Job).where(Job.state == JobState.RUNNING.value))
        )
        for job in stale:
            job.state = JobState.FAILED.value
            job.phase = JobPhase.DONE.value
            job.error = SERVICE_RESTARTED
            job.finished_at = datetime.now(UTC)
        return len(stale)


class Worker:
    """The worker thread: takes one job from the queue at a time and runs it.

    A thread rather than a process: a measurement spends almost all its time
    waiting on a socket, and there is no point splitting the interpreter. A
    daemon, so as not to hold the process up on shutdown.
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
            target=self._loop, name="benchmark-worker", daemon=True
        )
        self._thread.start()
        logger.info("the job worker thread has started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _next(self) -> str | None:
        """The next job — if nothing is running right now."""
        with session_scope(self.settings) as session:
            running = session.scalars(
                select(Job.id).where(Job.state == JobState.RUNNING.value)
            ).first()
            if running is not None:
                return None
            return session.scalars(
                select(Job.id)
                .where(Job.state == JobState.QUEUED.value)
                .order_by(Job.created_at)
            ).first()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._next()
            except Exception as exc:  # noqa: BLE001 - the database may have blinked
                logger.warning(f"the job queue is unavailable: {exc}")
                job_id = None
            if job_id is None:
                self._stop.wait(POLL_SECONDS)
                continue
            execute(job_id, self.settings)
