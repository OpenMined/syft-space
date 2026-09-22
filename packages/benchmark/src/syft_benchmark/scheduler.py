"""The whole daily cycle.

The order of the steps is not arbitrary. Generation goes first because the runs
have to go over a fresh dataset. Run A goes before B: it is cheaper (one model
call against a request to the endpoint with retrieval), and if the model is
unreachable that comes to light before the long part. Publishing comes last and
as a separate step, so that an interrupted cycle does not put out half the
results.

One Space failing does not stop the rest: the node may simply have been rebooting.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from loguru import logger

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    JobPhase,
    Settings,
    SpaceConfig,
    get_settings,
)
from syft_benchmark.generation import enabled_generators, generate_for_space
from syft_benchmark.llm import (
    check_perimeter,
    judge_providers,
    subject_providers,
)
from syft_benchmark.publish import publish
from syft_benchmark.report import Metrics, build_docx, render_markdown, summarize
from syft_benchmark.report.card import build as build_card
from syft_benchmark.runs import MODEL_ARMS, Progress, RunCache, run_pass

REPORTS_DIR = Path("reports")


@dataclass(slots=True)
class CycleReport:
    """What one cycle did."""

    started_at: datetime
    spaces: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    generated: int = 0
    published: int = 0
    report_path: Path | None = None
    document_path: Path | None = None


@dataclass(slots=True)
class Measured:
    """What came out of measuring one node."""

    metrics: list[Metrics] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
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
    """Who to report the progress of the measurement to.

    Created for the sake of launching from the UI: the daily cycle makes do with a
    log, while an owner who pressed a button needs to see what the measurement is
    on right now and to be able to stop it. Both requirements are satisfied by one
    and the same object, because it is one question — "what is happening and shall
    we carry on".
    """

    def planned(self, passes: int) -> None:
        """How many runs are ahead. Known before the first question."""

    def phase(self, phase: JobPhase, message: str = "") -> None:
        """The measurement has moved on to the next part of the work."""

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


def _plan(conf: Settings, subjects: int) -> int:
    """How many runs this configuration will give on one node.

    Computed before the work starts and by exactly the same enumeration as the
    measurement itself: a share of work done computed by a different rule will
    sooner or later diverge from the work and show "7 of 6".
    """
    total = 0
    for block in conf.blocks:
        for mode in conf.arms:
            if block is EvalBlock.DENIAL_LOOP and mode is ContextMode.OPEN_BOOK:
                continue
            total += subjects if mode in MODEL_ARMS else 1
    return total


def measure(
    space: SpaceConfig,
    conf: Settings,
    *,
    cache: RunCache | None = None,
    resume: bool = False,
    generate: bool | None = None,
    evaluate: bool = True,
    limit: int | None = None,
    observer: Observer | None = None,
    job_id: str | None = None,
) -> Measured:
    """Measure one node in full: the dataset, then all the runs.

    Taken out of the cycle so that there stays one path of execution. The daily
    cycle and the "launch" button differ in who called and who is reported to, not
    in what happens to the node; two implementations of one measurement would
    diverge within a month, and diverge silently.

    Args:
        space: The node under test
        conf: The settings, already assembled for this node
        cache: The shared cache of the launch; None — its own, for this node only
        resume: Finish what was interrupted, without re-asking what is done
        generate: Whether to build the dataset; None — as the settings say
        evaluate: Whether to ask and grade after building the dataset. False is
            for a launch that only wants a fresh question set and nothing asked
            against it yet — building the set is cheap, asking a model about
            every item in it is not, and the two are worth separating for
            exactly that reason
        limit: How many questions to ask in a run; None — all the active ones
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

    # The names the provider refused outright. A refusal is about the name, the
    # key or the money, and no later pass changes any of those — but each pass
    # asked in that name costs a whole set of questions and the time to ask
    # them. On the rig one misspelt model name went through every pass of every
    # arm and came back eighteen minutes later with nothing to show.
    #
    # The failure streak inside a pass cannot stand in for this. It counts
    # within one pass and starts again at the next, and a trial run's pass is
    # shorter than the threshold it counts to — so on the very run meant to be
    # a quick probe the streak never fires at all.
    refused: set[str] = set()

    # Generation goes first: the runs have to go over a fresh dataset. It is
    # switched off by a setting — for example when the corpus is closed to the
    # generator and the dataset is filled separately.
    if conf.generate_in_cycle if generate is None else generate:
        if observer is not None:
            observer.phase(JobPhase.GENERATE)
        try:
            made = generate_for_space(
                space,
                generators=enabled_generators(conf.disabled_generators),
                settings=conf,
                should_stop=observer.stop_requested if observer else None,
            )
            out.generated = made.pairs_active
            # Nothing built AND something refused: nothing built on its own
            # means no new chunks since the last pass.
            out.generated_nothing = bool(made.failures) and made.pairs_made == 0
            out.generation_failure_sample = made.failure_sample
            logger.info(
                f"{space.key}: items {made.pairs_made}, fit {made.pairs_active}, "
                f"failed calls {made.failures}"
            )
            if observer is not None:
                observer.phase(
                    JobPhase.GENERATE,
                    f"{made.pairs_active} of {made.pairs_made} fit into "
                    "the measurement",
                )
        except Exception as exc:  # noqa: BLE001 - the index may have been unreachable
            out.failures.append(f"{space.key}/generate: {exc}")
            logger.warning(f"{space.key} generation failed: {exc}")

    # Stopped during generation: the runs are the expensive half, and starting
    # them because the cheap half happened to finish first would answer a
    # button press with more spending.
    if observer is not None and observer.stop_requested():
        return out

    if not evaluate:
        return out

    if observer is not None:
        # Planned only now: a launch that stops here (evaluate=False) never
        # asks a question, and a pass count announced for it would draw a bar
        # that no further write ever moves.
        observer.planned(_plan(conf, len(subjects)))
        observer.phase(JobPhase.EVALUATE)

    for block in conf.blocks:
        # The order of the arms is not arbitrary: A is the cheapest of all and
        # discovers an unreachable model before the long part, while C comes after
        # B because it reuses the same endpoint call in meaning, not in code.
        for mode in conf.arms:
            # Pressure requires a dialogue, and the endpoint API is single-shot: it
            # takes one question as a string. Repeats at different temperatures are
            # available to an endpoint and are therefore not skipped.
            if block is EvalBlock.DENIAL_LOOP and mode is ContextMode.OPEN_BOOK:
                continue
            for subject in subjects if mode in MODEL_ARMS else [None]:
                if subject is not None and subject.model in refused:
                    continue
                # A judge the provider refused is stood down the same way. The
                # panel is shared by every pass, so one refused judge must not
                # end the measurement while the others can still grade.
                panel = [seat for seat in judges if seat.model not in refused]
                if judges and not panel:
                    out.failures.append(
                        f"{space.key}: the provider refused every judge — "
                        f"an answer nobody can grade is not worth asking for"
                    )
                    return out

                # Where the decision to carry on is actually taken. Progress
                # stops a run from within, one question at a time, and that is
                # the right grain for "this answerer is not answering" — a run
                # so stopped is followed by the next one, which is fresh and
                # knows nothing, and only a refusal is carried across by the
                # set above. Asked here, before the pass exists at all, a
                # cancellation costs nothing further: no questions are
                # dispatched, so none are paid for.
                if observer is not None and observer.stop_requested():
                    return out

                label = f"{space.key}/{mode.value}/{block.value}"
                if subject is not None:
                    label += f" [{subject.model}]"
                out.passes += 1
                if observer is not None:
                    observer.pass_started(
                        out.passes,
                        mode.value,
                        block.value,
                        subject.model if subject else "",
                    )
                try:
                    # The panel is handled inside the run: the answerer is asked
                    # once and assessed by all the judges.
                    outcomes = run_pass(
                        space,
                        mode,
                        limit=limit,
                        settings=conf,
                        subject=subject,
                        block=block,
                        judges=panel,
                        cache=shared,
                        resume=resume or conf.resume,
                        watch=observer.watcher(label) if observer else None,
                        job_id=job_id,
                    )
                except Exception as exc:  # noqa: BLE001 - the node may have rebooted
                    out.failures.append(f"{label}: {exc}")
                    logger.warning(f"{label} failed: {exc}")
                    if observer is not None:
                        observer.pass_done(out.passes, label)
                    continue

                for outcome in outcomes:
                    out.asked += outcome.asked
                    out.graded += outcome.graded
                    out.failed += outcome.failed
                    out.resumed += outcome.resumed
                    if not out.failure_sample and outcome.failure_sample:
                        out.failure_sample = outcome.failure_sample
                    if outcome.refused and outcome.refused not in refused:
                        refused.add(outcome.refused)
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
                        + (
                            f", from the previous attempt {outcome.resumed}"
                            if outcome.resumed
                            else ""
                        )
                    )
                    metrics = summarize(
                        space.key,
                        mode,
                        block,
                        subject.model if subject else None,
                        outcome.judge,
                    )
                    if metrics is not None:
                        out.metrics.append(metrics)
                if observer is not None:
                    observer.pass_done(out.passes, label)

    return out


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
        # charts and the analyst paragraph is a layer on top of it — being left
        # without published metrics over that would be a trade in the wrong direction.
        try:
            report.document_path = build_docx(
                collected, REPORTS_DIR / f"benchmark-{stamp}.docx", settings=conf
            )
        except Exception as exc:  # noqa: BLE001 - the Markdown report is already there
            report.failures.append(f"document: {exc}")
            logger.warning(f"the document was not assembled: {exc}")

    # The direct test is what gets published: the block figures are the owner
    # internal analytics. The arm is chosen by the card itself, by the kind of
    # product: a retrieval node has no arm B, and a setting would leave it with
    # nothing.
    for node_conf, space in nodes:
        card = build_card(space.key, space.endpoint, settings=node_conf)
        if card is None:
            continue
        sent = publish(space, card)
        if sent.ok:
            report.published += 1
        else:
            logger.info(f"{space.key}: not published — {sent.detail}")

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
            f"published {report.published}, failures {len(report.failures)}"
        )
        moment = next_fire(interval, at)
        logger.info(f"next cycle: {moment:%Y-%m-%d %H:%M}")
        time.sleep(max(0.0, (moment - datetime.now()).total_seconds()))
