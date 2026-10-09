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

from syft_benchmark.config import JobKind, JobPhase, JobState, Settings, SpaceConfig
from syft_benchmark.control.compose import merge, settings_for
from syft_benchmark.control.schemas import FilterRequest, JudgeRequest, RunRequest
from syft_benchmark.db import store
from syft_benchmark.db.models import Job, Run, Target
from syft_benchmark.db.run_cache import invalidate_run
from syft_benchmark.db.session import session_scope
from syft_benchmark.generation import filter_and_rotate
from syft_benchmark.llm.cost import CostMeter, cost_meter, openrouter_spend
from syft_benchmark.publish import payload_for, publish
from syft_benchmark.report import run_view
from syft_benchmark.report.card import build as build_card
from syft_benchmark.runs import endpoint_retriever, judge_pending
from syft_benchmark.runs.parallel import Progress
from syft_benchmark.runs.timing import CallClock, JobClock, PassTime
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

# The job's evaluation plan in its params (report API, "Progress plan").
PROGRESS_PLAN = "progress_plan"

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
        # Questions done / planned per pass; the passes run at the same time,
        # and the job row shows their sum.
        self._steps: dict[str, tuple[int, int]] = {}
        # Questions per pass from the plan; None — no plan, the total is the
        # sum of what the passes have reported (a judge job).
        self._per_pass: int | None = None
        self._finished: set[str] = set()
        # Where the time went, kept with the job when it ends.
        self.clock = JobClock()
        self.pass_times: list[PassTime] = []
        self.calls: CallClock | None = None
        self.concurrency: dict[str, int] | None = None

    # --- what the measurement calls ----------------------------------------
    def planned(self, passes: int) -> None:
        self.total = passes
        self._write(force=True)

    def phase(self, phase: JobPhase, message: str = "") -> None:
        self.clock.enter(phase.value)
        self._write(phase=phase, message=message, force=True)

    def plan(self, plan: dict[str, Any]) -> None:
        """Fix the step total for the whole evaluation and keep the plan."""
        self._per_pass = int(plan["questions"])
        self.step_total = int(plan["steps"])
        with session_scope(self.settings) as session:
            job = session.get(Job, self.job_id)
            if job is not None:
                job.params = {**(job.params or {}), PROGRESS_PLAN: plan}
        self._write(force=True)

    def pass_started(self, index: int, arm: str, block: str, model: str) -> None:
        # The pass that started last; the step counts span every pass.
        self.arm, self.block, self.model = arm, block, model
        self._write(force=True)

    def pass_done(self, index: int, label: str) -> None:
        # Passes end in any order: this counts them.
        self.passes += 1
        self.current = ""
        # Ended early or not, the pass is all its share of the plan now.
        self._finished.add(label)
        self._sum_steps()
        self._write(force=True)

    def watcher(self, label: str) -> Callable[[Progress], None]:
        def tick(progress: Progress) -> None:
            self._steps[label] = (progress.done, progress.total)
            self._sum_steps()
            self._write()
            if self.cancelled:
                progress.stop("stopped by the owner")

        return tick

    def _sum_steps(self) -> None:
        """step_done/step_total over every pass; with a plan, never backwards."""
        if self._per_pass is None:
            self.step_done = sum(done for done, _ in self._steps.values())
            self.step_total = sum(total for _, total in self._steps.values())
            return
        share = self._per_pass
        # A pass asks fewer than planned when it resumes: those count as done.
        counted = sum(
            min(share, done + max(0, share - total))
            for label, (done, total) in self._steps.items()
            if label not in self._finished
        )
        counted += share * len(self._finished)
        self.step_done = max(self.step_done, min(self.step_total, counted))

    def timing(self) -> dict[str, Any]:
        """The job's ``timing`` (report API, "Timing")."""
        return self.clock.payload(
            passes=self.pass_times,
            calls=self.calls.stats() if self.calls is not None else [],
            concurrency=self.concurrency,
        )

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
    session: Session,
    target: Target,
    request: RunRequest | FilterRequest | JudgeRequest,
    *,
    kind: JobKind = JobKind.PIPELINE,
    trigger: str = "manual",
) -> Job:
    """Put a job in the queue.

    A second job for the same target is not created — the one already standing
    there is returned, whatever kind it is: the queue is one per target
    regardless of what the job does, since a filter or a judge pass reads and
    writes the same rows a measurement would.
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
        kind=kind.value,
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
    """Carry out a job: what it does from here depends on its kind.

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
            kind = job.kind or JobKind.PIPELINE.value
            params = {
                k: v
                for k, v in (job.params or {}).items()
                if k not in run_view.SNAPSHOT_KEYS and k != PROGRESS_PLAN
            }
            job.state = JobState.RUNNING.value
            job.started_at = datetime.now(UTC)
            node_conf, space = settings_for(target, conf)

        reporter = Reporter(job_id, conf)
        reporter.concurrency = {
            "model": node_conf.concurrency,
            "endpoint": node_conf.endpoint_concurrency,
        }
        with cost_meter(job_id=job_id) as meter:
            before = _spend(node_conf)
            try:
                if kind == JobKind.FILTER.value:
                    _execute_filter(job_id, space, node_conf, params, reporter=reporter)
                elif kind == JobKind.JUDGE.value:
                    _execute_judge(job_id, space, node_conf, params, reporter=reporter)
                else:
                    _execute_pipeline(
                        job_id,
                        space,
                        node_conf,
                        params,
                        base_settings=conf,
                        reporter=reporter,
                    )
            finally:
                _record_cost(job_id, before, _spend(node_conf), meter, conf)
                _record_timing(job_id, reporter, conf)
    except Exception as exc:  # noqa: BLE001 - the owner needs the cause, not a traceback
        logger.exception(f"job {job_id} failed")
        _finish(job_id, JobState.FAILED, error=str(exc), settings=settings)


def _execute_pipeline(
    job_id: str,
    space: SpaceConfig,
    node_conf: Settings,
    params: dict[str, Any],
    *,
    base_settings: Settings,
    reporter: Reporter | None = None,
) -> None:
    """The original, uninterrupted run: generate, filter, evaluate, the card.

    Also what a lone generate, a lone evaluate and either console-facing
    group are — all of it is one call to ``measure()``, distinguished only by
    which of ``RunRequest``'s booleans are set.
    """
    request = RunRequest.model_validate(params)

    # The layers from the request itself lie on top of the ones saved on the
    # target and do not change the target: a trial run with a different
    # similarity threshold must not rewrite the setting the ordinary nightly
    # measurement will go by.
    extra = [x for x in (request.instrument, request.probe) if x is not None]
    if extra:
        node_conf = merge(node_conf, *extra)
    _snapshot_judging(job_id, node_conf, base_settings)

    # None means "yes" — the ordinary shape of a launch that measures. False
    # is for a launch that only wants the question set refreshed: the runs
    # below, and the card built from them, describe an evaluation that did
    # not happen and have no business existing for this one.
    want_evaluate = request.evaluate if request.evaluate is not None else True

    if reporter is None:
        reporter = Reporter(job_id, base_settings)
    card_payload: dict[str, Any] | None = None
    done = measure(
        space,
        node_conf,
        generate=request.generate,
        filter=request.filter,
        evaluate=want_evaluate,
        defer_judging=request.defer_judging,
        limit=request.limit,
        observer=reporter,
        job_id=job_id,
    )
    reporter.pass_times = done.pass_times
    reporter.calls = done.clock
    failures = list(done.failures)
    # Outside `want_evaluate` on purpose: a launch that only refreshes the
    # question set can fail this way too.
    if done.generated_nothing:
        failures.append(_with_sample(NOTHING_GENERATED, done.generation_failure_sample))
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
        # halfway was not a statement. Deferred is a third: there is not a
        # single verdict yet to build anything from — that is judge_stage's
        # job, once the owner runs it.
        if not reporter.cancelled and not request.defer_judging:
            reporter.phase(JobPhase.PUBLISH)
            card = build_card(space.key, space.endpoint, settings=node_conf, job=job_id)
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

    state = JobState.CANCELLED if reporter.cancelled else JobState.SUCCEEDED
    _finish(
        job_id,
        state,
        error="; ".join(failures),
        message="; ".join(done.notes),
        card=card_payload,
        settings=base_settings,
    )


def _execute_filter(
    job_id: str,
    space: SpaceConfig,
    node_conf: Settings,
    params: dict[str, Any],
    *,
    reporter: Reporter,
) -> None:
    """Screen this target's pending pairs on their own — no fresh generate."""
    base_settings = reporter.settings
    request = FilterRequest.model_validate(params)
    _snapshot_judging(job_id, node_conf, base_settings)
    reporter.phase(JobPhase.FILTER)
    outcome = filter_and_rotate(
        space,
        generator=request.generator,
        cohort=request.cohort,
        limit=request.limit,
        settings=node_conf,
        retrieve=endpoint_retriever(space, node_conf),
        should_stop=reporter.stop_requested,
        job_id=job_id,
    )
    reporter.phase(JobPhase.FILTER, outcome.line())
    state = JobState.CANCELLED if reporter.cancelled else JobState.SUCCEEDED
    summary = [f"filter: {outcome.line()}"]
    if outcome.rotation is not None:
        summary.append(f"set: {outcome.rotation.line()}")
    _finish(
        job_id,
        state,
        error="; ".join(outcome.notes),
        message="; ".join(summary),
        settings=base_settings,
    )


def _execute_judge(
    job_id: str,
    space: SpaceConfig,
    node_conf: Settings,
    params: dict[str, Any],
    *,
    reporter: Reporter,
) -> None:
    """Grade this target's pending verdicts on their own — no fresh evaluate."""
    base_settings = reporter.settings
    request = JudgeRequest.model_validate(params)
    _snapshot_judging(job_id, node_conf, base_settings)
    reporter.phase(JobPhase.JUDGE)
    outcome = judge_pending(
        space,
        limit=request.limit,
        settings=node_conf,
        should_stop=reporter.stop_requested,
        watch=reporter.watcher(f"{space.key}/judging"),
    )
    reporter.phase(JobPhase.JUDGE, outcome.line())
    state = JobState.CANCELLED if reporter.cancelled else JobState.SUCCEEDED
    _finish(job_id, state, error="; ".join(outcome.notes), settings=base_settings)


def _spend(conf: Settings) -> float | None:
    """The OpenRouter keys' spend so far; None — not OpenRouter or unreadable."""
    try:
        return openrouter_spend(conf)
    except Exception:  # noqa: BLE001 - the cost line is never worth a failed job
        logger.exception("OpenRouter spend could not be read")
        return None


def _record_cost(
    job_id: str,
    before: float | None,
    after: float | None,
    meter: CostMeter,
    settings: Settings,
) -> None:
    """Keep what the job spent in its params (``run_view.COST``).

    ``total_usd`` is the sum of ``by_role``: the calls made for the writer,
    the web check, the tested models and the judges; ``usd_calls`` is every
    priced call, untagged ones included.
    """
    usd = (
        round(max(0.0, after - before), 6)
        if before is not None and after is not None
        else None
    )
    by_role = {role: round(usd_, 6) for role, usd_ in meter.by_role.items()}
    cost = {
        "spend_before": before,
        "spend_after": after,
        "usd": usd,
        "usd_calls": round(meter.total_usd, 6),
        "total_usd": round(sum(meter.by_role.values()), 6),
        "by_role": by_role,
    }
    try:
        with session_scope(settings) as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.params = {**(job.params or {}), run_view.COST: cost}
    except Exception:  # noqa: BLE001 - as above
        logger.exception(f"job {job_id}: its cost was not recorded")


def _record_timing(job_id: str, reporter: Reporter, settings: Settings) -> None:
    """Keep where the job's time went in its params (``run_view.TIMING``).

    ``total_s`` is the job's own time: finished (or now) minus started.
    """
    try:
        timing = reporter.timing()
        with session_scope(settings) as session:
            job = session.get(Job, job_id)
            if job is not None:
                if job.started_at is not None:
                    end = job.finished_at or datetime.now(UTC)
                    timing["total_s"] = round((end - job.started_at).total_seconds(), 2)
                job.params = {**(job.params or {}), run_view.TIMING: timing}
    except Exception:  # noqa: BLE001 - the timing is never worth a failed job
        logger.exception(f"job {job_id}: its timing was not recorded")


def _snapshot_judging(job_id: str, conf: Settings, settings: Settings | None) -> None:
    """Keep the judge panel and policy the job runs with in its params."""
    with session_scope(settings) as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.params = {**(job.params or {}), **run_view.judging_snapshot(conf)}


def _finish(
    job_id: str,
    state: JobState,
    *,
    error: str = "",
    message: str | None = None,
    card: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> None:
    """Close a job.

    ``message``, when given, replaces the last progress line: on a finished
    job it carries notes that are not failures (a skipped block). None leaves
    what the last phase said.

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
        if message is not None:
            job.message = message
        job.card = card
        job.finished_at = datetime.now(UTC)
        invalidate_run(session, job_id)
        # There is no separate "passed, but not whole" message here: it is
        # visible from the pair "state + a non-empty reason" itself, and a
        # phrase invented for it would be a third place where the same thing is
        # said differently.
    run_view.warm(job_id, settings)


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
