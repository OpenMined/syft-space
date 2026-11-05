"""Measuring a node, and the scheduled cycle over every node.

``measure`` is the one execution path for a node — build the dataset, screen
it, then run every pass — shared by the console cycle and jobs launched from
the UI. ``run_cycle``/``run_forever`` walk the registry on a schedule. One
Space failing does not stop the rest: the node may simply have been rebooting.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    JobPhase,
    Settings,
    SpaceConfig,
    get_settings,
)
from syft_benchmark.generation import (
    FilterSummary,
    enabled_generators,
    filter_and_rotate,
    generate_for_space,
)
from syft_benchmark.llm import (
    Provider,
    check_perimeter,
    judge_providers,
    subject_providers,
)
from syft_benchmark.report import Metrics, build_docx, render_markdown, summarize
from syft_benchmark.report.job_params import record_generation
from syft_benchmark.runs import (
    Progress,
    RunCache,
    arun_pass,
    endpoint_retriever,
    evaluation_gate,
)
from syft_benchmark.runs.blocks import monte_carlo_skip_note, skips_monte_carlo
from syft_benchmark.runs.execute import _active_pairs
from syft_benchmark.runs.parallel import Launch, Pool
from syft_benchmark.runs.timing import CallClock, PassTime

REPORTS_DIR = Path("reports")


@dataclass(slots=True)
class CycleReport:
    """What one cycle did."""

    started_at: datetime
    spaces: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    generated: int = 0
    report_path: Path | None = None
    document_path: Path | None = None

    @property
    def written(self) -> list[Path]:
        """The report files this cycle wrote."""
        return [p for p in (self.report_path, self.document_path) if p is not None]


@dataclass(slots=True)
class Measured:
    """What came out of measuring one node."""

    metrics: list[Metrics] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    # What the measurement chose not to do, by design rather than by failure,
    # and the stage summaries; the job's final message.
    notes: list[str] = field(default_factory=list)
    generated: int = 0
    passes: int = 0

    # How many questions were asked, how many judged and how many calls failed.
    # Counted because "the run reached the end" and "the run measured something"
    # are different things: a model provider that is down gives a full pass over
    # the set, zero verdicts and a thoroughly reassuring result.
    asked: int = 0
    graded: int = 0
    failed: int = 0
    resumed: int = 0

    # The text of one failed call, whichever came first. Without it every cause
    # reaches the owner as the same "nothing was graded", and the one line that
    # says which stays in the database.
    failure_sample: str = ""

    # The same question, asked of the cheap half. An empty set and a set nobody
    # could build look the same from outside and are opposite in what they ask
    # of the owner.
    generated_nothing: bool = False
    generation_failure_sample: str = ""

    # The names the provider refused outright; their remaining passes are
    # skipped.
    refused: set[str] = field(default_factory=set)
    # Where the evaluation's time went: per pass, and per model call.
    pass_times: list[PassTime] = field(default_factory=list)
    clock: CallClock = field(default_factory=CallClock)

    @property
    def measured_nothing(self) -> bool:
        """Questions were asked and not a single verdict came out."""
        return self.asked > 0 and self.graded == 0

    @property
    def had_nothing_to_ask(self) -> bool:
        """There were runs and there turned out to be nothing to ask.

        Usually this is an empty set: the freshness window let no document through,
        or generation has not reached this node yet. A resumed run does not land
        here — there too no questions were asked, but because verdicts for them
        already exist, and that is exactly the opposite case.
        """
        return self.passes > 0 and self.asked == 0 and self.resumed == 0


class Observer(Protocol):
    """Who to report the progress of the measurement to, and who may stop it.

    The daily cycle passes none and logs; a job launched from the UI passes
    its reporter.
    """

    def planned(self, passes: int) -> None:
        """How many runs are ahead. Known before the first question."""

    def phase(self, phase: JobPhase, message: str = "") -> None:
        """The measurement has moved on to the next part of the work."""

    def plan(self, plan: dict[str, Any]) -> None:
        """The whole evaluation, pass by pass (report API, "Progress plan").

        Known before the first question.
        """

    def pass_started(self, index: int, arm: str, block: str, model: str) -> None:
        """Another run has started, and here is what it is busy with.

        As fields, not as a string: a string of the form
        "space/closed_book/direct [model]" is read only by someone who knows how it
        is built, and in another language it is not displayed at all.
        """

    def pass_done(self, index: int, label: str) -> None:
        """The run is finished, we move on to the next."""

    def watcher(self, label: str) -> Callable[[Progress], None] | None:
        """An observer of progress within a run, if one is needed."""

    def stop_requested(self) -> bool:
        """Whether the owner has asked for the measurement to stop.

        Asked rather than told, because the phases differ in how much they
        report. A run reports on every question and could be handed the answer
        along the way; generation reports nothing at all and would never learn
        it had been cancelled.
        """
        return False


def measure(
    space: SpaceConfig,
    conf: Settings,
    *,
    cache: RunCache | None = None,
    resume: bool = False,
    generate: bool | None = None,
    filter: bool | None = None,  # noqa: A002 - the console-facing name for the phase
    evaluate: bool = True,
    defer_judging: bool = False,
    limit: int | None = None,
    observer: Observer | None = None,
    job_id: str | None = None,
) -> Measured:
    """Measure one node in full: the dataset, then all the runs.

    The one path of execution: the daily cycle and a launched job differ in who
    called and who is reported to, not in what happens to the node.

    Args:
        space: The node under test
        conf: The settings, already assembled for this node
        cache: The shared cache of the launch; None — its own, for this node only
        resume: Finish what was interrupted, without re-asking what is done
        generate: Whether to build the dataset; None — as the settings say.
            Every item it builds lands ``pending`` — nothing here decides on
            its own whether one is fit
        filter: Whether to screen pending pairs into active or rejected right
            after building; None — follow ``generate``, so a launch that built
            a dataset also decides what of it is fit. A launch that only wants
            to build ("just show me what came out") passes this explicitly
            ``False``
        evaluate: Whether to ask and grade after building the dataset. False is
            for a launch that only wants a fresh question set and nothing asked
            against it yet — building the set is cheap, asking a model about
            every item in it is not, and the two are worth separating for
            exactly that reason
        defer_judging: Collect the answers without calling a judge, leaving
            every ``Result`` with ``verdict = pending`` for ``judge_stage`` to
            grade afterwards
        limit: A trial run's size: how many questions to build from each
            generator and then ask of each. None — build as the settings say
            and ask every active question
        observer: Who to report progress to
        job_id: The launch this measurement belongs to. It is written on every run
            it opens, and that is what later makes the report and the audit of
            THIS measurement possible rather than of the node in general. None —
            the console: such runs belong to no job

    Returns:
        The metrics of all the runs, what failed, and how many items were added
    """
    out = Measured()
    shared = cache if cache is not None else RunCache(enabled=conf.reuse_answers)
    # Before anything is asked: a role pointing outside the perimeter is found
    # here rather than in the third hour of the measurement.
    check_perimeter(conf)
    subjects = subject_providers(conf)
    judges = judge_providers(conf)

    # Generation goes first: the runs have to go over a fresh dataset. It is
    # switched off by a setting — for example when the corpus is closed to the
    # generator and the dataset is filled separately.
    generate_effective = conf.generate_in_cycle if generate is None else generate
    filter_effective = generate_effective if filter is None else filter
    # The same retrieval the control gate is checked with during the build and
    # in the filter pass: "there is no answer" is meaningful only relative to
    # this endpoint, not to an abstract corpus.
    retrieve = endpoint_retriever(space, conf) if filter_effective else None
    # Questions written by the build were checked as they were written.
    streamed: FilterSummary | None = None
    if generate_effective:
        if observer is not None:
            observer.phase(JobPhase.GENERATE)

        def built(message: str) -> None:
            """Where the build has got to, for whoever is watching it.

            Through `phase` rather than `watcher`: a watcher reports a
            position within one run of the measurement, and generation is
            not one — kinds are written in parallel and checked as they go.
            """
            if observer is not None:
                observer.phase(JobPhase.GENERATE, message)

        try:
            made = generate_for_space(
                space,
                generators=enabled_generators(conf.disabled_generators),
                settings=conf,
                should_stop=observer.stop_requested if observer else None,
                job=job_id or "",
                # The same cap on both halves of a trial: build this many
                # questions per generator, then ask those. One number, so that
                # "two each" means two built and two asked rather than two
                # asked out of the usual fifty built.
                per_generator=limit,
                on_progress=built if observer is not None else None,
                # Each question is checked as soon as it is written; the
                # filter pass below takes what is left and recomputes the set.
                screen=filter_effective,
                retrieve=retrieve,
            )
            streamed = made.screened
            if job_id:
                record_generation(job_id, made.kind_rows(), conf)
            # Nothing built AND something refused: nothing built on its own
            # means no new chunks since the last pass.
            out.generated_nothing = bool(made.failures) and made.pairs_made == 0
            out.generation_failure_sample = made.failure_sample
            logger.info(
                f"{space.key}: items {made.pairs_made} pending, "
                f"failed calls {made.failures}"
            )
            out.notes.append(f"wrote {made.pairs_made} questions")
        except Exception as exc:  # noqa: BLE001 - the index may have been unreachable
            out.failures.append(f"{space.key}/generate: {exc}")
            logger.warning(f"{space.key} generation failed: {exc}")

    # Stopped during generation: filtering and the runs are the expensive
    # halves, and starting either because the cheap half happened to finish
    # first would answer a button press with more spending.
    if observer is not None and observer.stop_requested():
        return out

    if filter_effective:
        if observer is not None:
            observer.phase(JobPhase.FILTER)
        try:
            filtered = filter_and_rotate(
                space,
                settings=conf,
                retrieve=retrieve,
                should_stop=observer.stop_requested if observer else None,
                rotate_anyway=generate_effective,
                job_id=job_id or "",
            )
            if streamed is not None:
                filtered.absorb(streamed)
            out.generated = filtered.active
            logger.info(f"{space.key}: filtering — {filtered.line()}")
            if observer is not None:
                observer.phase(JobPhase.FILTER, filtered.line())
            out.notes.append(f"filter: {filtered.line()}")
            if filtered.rotation is not None:
                out.notes.append(f"set: {filtered.rotation.line()}")
        except Exception as exc:  # noqa: BLE001 - the index may have been unreachable
            out.failures.append(f"{space.key}/filter: {exc}")
            logger.warning(f"{space.key} filtering failed: {exc}")

    if observer is not None and observer.stop_requested():
        return out

    if not evaluate:
        return out

    held = evaluation_gate(space.key, conf)
    if held:
        # Active questions exist and none passed the web check: nothing to ask.
        out.failures.append(f"{space.key}: {held}")
        return out

    # A skipped monte_carlo block is not a pass.
    specs: list[tuple[ContextMode, EvalBlock, Provider]] = []
    skipped_mc: list[str] = []
    for block in conf.blocks:
        for mode in conf.arms:
            for subject in subjects:
                if skips_monte_carlo(block, subject, conf):
                    note = monte_carlo_skip_note(subject.model)
                    if note not in out.notes:
                        out.notes.append(note)
                    if subject.model not in skipped_mc:
                        skipped_mc.append(subject.model)
                    continue
                specs.append((mode, block, subject))

    if observer is not None:
        # Planned only now: a launch that stops here (evaluate=False) never
        # asks a question, and a pass count announced for it would draw a bar
        # that no further write ever moves. The count is the passes about to
        # run, so the share of work done cannot drift from the work.
        passes = len(specs)
        observer.planned(passes)
        # Every pass asks the same set, so the whole extent is known now.
        questions = len(_active_pairs(space.key, limit, conf))
        observer.plan(
            {
                "questions": questions,
                "models": [subject.model for subject in subjects],
                "conditions": [mode.value for mode in conf.arms],
                "checks": [block.value for block in conf.blocks],
                "skipped_monte_carlo": skipped_mc,
                "steps": passes * questions,
                "started_at": datetime.now(UTC).isoformat(),
            }
        )
        observer.phase(JobPhase.EVALUATE)

    # Every pass runs at once, under the one model lane and the one endpoint
    # lane, so no lane idles through a pass's slow tail. The cache makes the
    # passes of one question share their calls.
    async def evaluate_all() -> None:
        pool = Pool(conf, clock=out.clock)
        launch = Launch(
            conf, halt=observer.stop_requested if observer is not None else None
        )
        try:
            ran = await asyncio.gather(
                *(
                    _one_pass(
                        space,
                        conf,
                        mode,
                        block,
                        subject,
                        judges=judges,
                        out=out,
                        pool=pool,
                        launch=launch,
                        cache=shared,
                        limit=limit,
                        resume=resume,
                        defer_judging=defer_judging,
                        observer=observer,
                        job_id=job_id,
                    )
                    for mode, block, subject in specs
                )
            )
            out.pass_times = [timed for timed in ran if timed is not None]
        finally:
            pool.close()

    if specs:
        asyncio.run(evaluate_all())
    return out


async def _one_pass(
    space: SpaceConfig,
    conf: Settings,
    mode: ContextMode,
    block: EvalBlock,
    subject: Provider,
    *,
    judges: list[Provider],
    out: Measured,
    pool: Pool,
    launch: Launch,
    cache: RunCache,
    limit: int | None,
    resume: bool,
    defer_judging: bool,
    observer: Observer | None,
    job_id: str | None,
) -> PassTime | None:
    """One pass of the launch, alongside the others; None — not started."""
    # A name the provider refused outright is not asked in passes still to
    # come. A refusal is about the name, the key or the money, and no later
    # pass changes any of those — but each pass asked in that name costs a
    # whole set of questions and the time to ask them.
    if subject.model in launch.refused:
        return None
    # A judge the provider refused is stood down the same way. The panel is
    # shared by every pass, so one refused judge must not end the measurement
    # while the others can still grade.
    panel = [seat for seat in judges if seat.model not in launch.refused]
    if judges and not panel:
        failure = (
            f"{space.key}: the provider refused every judge — "
            f"an answer nobody can grade is not worth asking for"
        )
        if failure not in out.failures:
            out.failures.append(failure)
        return None

    # Asked before the pass exists at all, a cancellation costs nothing
    # further: no questions are dispatched, so none are paid for.
    if observer is not None and observer.stop_requested():
        return None

    label = f"{space.key}/{mode.value}/{block.value} [{subject.model}]"
    out.passes += 1
    index = out.passes
    if observer is not None:
        observer.pass_started(index, mode.value, block.value, subject.model)
    timed = PassTime(arm=mode.value, block=block.value, model=subject.model)
    started = time.monotonic()
    try:
        # The panel is handled inside the run: the answerer is asked once and
        # assessed by all the judges.
        outcomes = await arun_pass(
            space,
            mode,
            pool=pool,
            cache=cache,
            limit=limit,
            settings=conf,
            subject=subject,
            block=block,
            judges=panel,
            resume=resume or conf.resume,
            defer_judging=defer_judging,
            watch=observer.watcher(label) if observer else None,
            job_id=job_id,
            launch=launch,
        )
    except Exception as exc:  # noqa: BLE001 - the node may have rebooted
        out.failures.append(f"{label}: {exc}")
        logger.warning(f"{label} failed: {exc}")
        timed.seconds = time.monotonic() - started
        timed.stopped = str(exc)[:200]
        if observer is not None:
            observer.pass_done(index, label)
        return timed
    timed.seconds = time.monotonic() - started

    for outcome in outcomes:
        timed.questions = max(timed.questions, outcome.asked)
        if outcome.stopped and not timed.stopped:
            timed.stopped = outcome.stopped
        out.asked += outcome.asked
        out.graded += outcome.graded
        out.failed += outcome.failed
        out.resumed += outcome.resumed
        if not out.failure_sample and outcome.failure_sample:
            out.failure_sample = outcome.failure_sample
        if outcome.refused and outcome.refused not in out.refused:
            out.refused.add(outcome.refused)
            launch.refused.add(outcome.refused)
            out.failures.append(
                f"{space.key}: the provider refused "
                f"{outcome.refused} outright, and the passes still "
                f"to come in that name were not asked"
            )
            logger.warning(
                f"{label}: {outcome.refused} was refused outright — "
                f"its remaining passes are skipped"
            )
        logger.info(
            f"{label}/{outcome.judge}: asked {outcome.asked}, "
            f"correct {outcome.correct}, abstentions {outcome.abstain}, "
            f"hallucinations {outcome.hallucinate}"
            + (f", incomplete {outcome.incomplete}" if outcome.incomplete else "")
            + (
                f", from the previous attempt {outcome.resumed}"
                if outcome.resumed
                else ""
            )
        )
        metrics = summarize(space.key, mode, block, subject.model, outcome.judge)
        if metrics is not None:
            out.metrics.append(metrics)
    if observer is not None:
        observer.pass_done(index, label)
    return timed


def parse_interval(text: str) -> float:
    """An interval of the form 24h, 90m, 3600s, in seconds.

    Raises:
        ValueError: an unreadable notation
    """
    raw = text.strip().lower()
    if not raw:
        raise ValueError("empty interval")
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if raw[-1] in units:
        return float(raw[:-1]) * units[raw[-1]]
    return float(raw)


def next_fire(interval_s: float, at: str, *, now: datetime | None = None) -> datetime:
    """When to fire next.

    ``at`` sets the time of day for the daily step: the cycle should land at night,
    when the rig is free, and not at the moment it happened to be started for the
    first time.
    """
    moment = now or datetime.now()
    if at and abs(interval_s - 86400) < 1:
        hour, _, minute = at.partition(":")
        target = moment.replace(
            hour=int(hour), minute=int(minute or 0), second=0, microsecond=0
        )
        if target <= moment:
            target += timedelta(days=1)
        return target
    return moment + timedelta(seconds=interval_s)


def run_cycle(
    nodes: list[tuple[Settings, SpaceConfig]],
    settings: Settings | None = None,
    *,
    resume: bool = False,
) -> CycleReport:
    """One full pass over all the nodes.

    Generation goes first and is switched on by the ``generate_in_cycle`` setting:
    it reads the sources, and on a paid provider it is usually switched off, with
    the dataset filled by a separate deliberate launch.

    Args:
        nodes: The nodes the cycle goes over, each with the settings it is
            measured by — the pairs ``control.targets.resolve`` hands out, so
            that a node's instrument and probe reach a cycle exactly as they
            reach a run launched from the UI
        settings: The installation's settings, for what is not any one node's
            business — the document built over all of them
        resume: Finish an interrupted cycle without re-asking what is done. Not fit
            for a step of an endless schedule: there every step measures afresh,
            that is what a step is
    """
    conf = settings or get_settings()
    report = CycleReport(started_at=datetime.now())
    collected: list[Metrics] = []

    for node_conf, space in nodes:
        report.spaces.append(space.key)
        # The cache lives for the whole of one node's pass: the endpoint retrieval
        # for a question is one for all the arms, blocks and models under test, and
        # asking for it afresh on every run would mean paying for the same work
        # dozens of times. It is not shared between nodes — the retrieval belongs to
        # one endpoint — and `reuse_answers` is a setting a Space may hold its own
        # value of.
        cache = RunCache(enabled=node_conf.reuse_answers)
        done = measure(space, node_conf, cache=cache, resume=resume)
        report.failures.extend(done.failures)
        report.generated += done.generated
        collected.extend(done.metrics)
        if cache.enabled:
            logger.info(f"{space.key}: repeats avoided — {cache.savings.line()}")

    if collected:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = report.started_at.strftime("%Y%m%d-%H%M")
        path = REPORTS_DIR / f"benchmark-{stamp}.md"
        path.write_text(render_markdown(collected), encoding="utf-8")
        report.report_path = path

        # The document is assembled by the same cycle, but its failure does not
        # bring the cycle down: the Markdown is already written, and drawing the
        # charts and the analyst paragraph is a layer on top of it — losing
        # the Markdown over that would be a trade in the wrong direction.
        try:
            report.document_path = build_docx(
                collected, REPORTS_DIR / f"benchmark-{stamp}.docx", settings=conf
            )
        except Exception as exc:  # noqa: BLE001 - the Markdown report is already there
            report.failures.append(f"document: {exc}")
            logger.warning(f"the document was not assembled: {exc}")

    return report


def run_forever(
    keys: list[str] | None = None,
    *,
    every: str = "24h",
    at: str = "",
    settings: Settings | None = None,
) -> None:
    """Run the cycle on a schedule until stopped.

    The first run goes immediately: waiting a day to find out that the settings are
    wrong is a poor way to discover it.

    Keys rather than nodes, and they are resolved afresh before every cycle. A
    schedule runs for weeks, and in those weeks a threshold is raised, a judge is
    replaced and an endpoint is taken out of the measurement — all of it from the
    UI, into the same table. A snapshot taken at the first cycle would go on
    measuring yesterday's configuration and say nothing about it.

    Args:
        keys: Which nodes; empty — every one of them, as of each cycle
        every: The interval between cycles
        at: The hour of the day for a daily step
        settings: The installation's settings; the process's own by default
    """
    from syft_benchmark.control.targets import resolve

    interval = parse_interval(every)
    while True:
        report = run_cycle(resolve(keys, settings), settings)
        logger.info(
            f"cycle finished: nodes {len(report.spaces)}, "
            f"failures {len(report.failures)}"
        )
        for path in report.written:
            logger.info(f"report written: {path}")
        moment = next_fire(interval, at)
        logger.info(f"next cycle: {moment:%Y-%m-%d %H:%M}")
        time.sleep(max(0.0, (moment - datetime.now()).total_seconds()))
