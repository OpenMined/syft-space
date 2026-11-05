"""Asking and judging, what is collected so far, and the scheduled cycle."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import func, select

from syft_benchmark.cli.common import SpaceKeys, resolve_nodes
from syft_benchmark.config import (
    ARM_LETTER,
    ContextMode,
    ContextSource,
    EvalBlock,
    Settings,
    SpaceConfig,
)
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.generation import cohort as cohort_store
from syft_benchmark.llm import (
    JudgeConflict,
    Provider,
    judge_providers,
    subject_providers,
)
from syft_benchmark.runs import (
    RunCache,
    judge_pending,
    questionset,
    run_pass,
)
from syft_benchmark.runs.blocks import monte_carlo_skip_note, skips_monte_carlo
from syft_benchmark.runs.execute import active_pairs, evaluation_gate
from syft_benchmark.runs.gate import evaluable
from syft_benchmark.runs.questionset import SliceMismatch
from syft_benchmark.runs.resume import window_start
from syft_benchmark.runs.status import collect as collect_status
from syft_benchmark.scheduler import run_cycle, run_forever


def evaluate(
    space: SpaceKeys = None,
    mode: Annotated[
        list[ContextMode] | None,
        typer.Option(
            "--mode",
            "-m",
            help="Arm: closed_book (A), model_with_context (C)",
        ),
    ] = None,
    block: Annotated[
        list[EvalBlock] | None,
        typer.Option("--block", "-b", help="Way of checking; may be repeated"),
    ] = None,
    context_source: Annotated[
        ContextSource | None,
        typer.Option(help="What to mix into arm C; defaults to the settings"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            help=(
                "How many questions to ask per generator. A count, not a "
                "percentage: that way every kind of item is checked equally"
            )
        ),
    ] = None,
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            "-r",
            help="Continue an interrupted measurement without re-asking what is done",
        ),
    ] = False,
    question_set: Annotated[
        Path | None,
        typer.Option(help="A frozen slice of questions; with it --limit is not needed"),
    ] = None,
    defer_judging: Annotated[
        bool,
        typer.Option(
            "--defer-judging",
            help="Collect answers without calling the judge: verdicts come later",
        ),
    ] = False,
) -> None:
    """Stages 4-5: ask the questions and judge the answers.

    Without --mode every arm from the settings is taken, without --block every
    block. denial_loop applies to the arms where a model answers: it requires a
    dialogue, and the endpoint's API is single-turn.

    --resume continues an interrupted attempt: a question the judge already has
    a usable verdict for is not asked again. Failed calls are re-asked — they
    hold no verdict, and the report counts them as a hole anyway. Only runs of
    the same profile with the same settings snapshot are taken into account, no
    older than BENCH_RESUME_WINDOW_HOURS hours.
    """
    failures: list[str] = []

    for node_conf, target in resolve_nodes(space):
        # The node's settings — the installation's defaults with the Space's
        # instrument and this endpoint's probe already on them — and this
        # call's flags on top. The slice is one of the flags, but it is part of
        # the run's methodology rather than of the call: it also picks out what
        # has been covered and checks comparability, so it goes into the
        # settings and from there into every run's snapshot.
        settings = (
            node_conf.model_copy(update={"question_set": question_set})
            if question_set is not None
            else node_conf
        )
        typer.echo(f"--- {target.name}")
        held = evaluation_gate(target.key, settings)
        if held:
            # Nothing passed the web check: there is nothing to ask.
            typer.secho(f"{target.name}: {held}", fg=typer.colors.YELLOW)
            continue
        if settings.question_set is not None:
            typer.echo(f"frozen slice: {settings.question_set}")
            if limit is not None:
                # The slice is the whole sample. A limit on top of it would
                # select from what was already selected and would bring back
                # the very set drift the slice exists to prevent.
                typer.secho(
                    "  --limit does not apply with a slice: "
                    "the slice is the whole sample",
                    fg=typer.colors.YELLOW,
                )
        modes = tuple(mode) if mode else tuple(settings.arms)
        blocks = tuple(block) if block else tuple(settings.blocks)
        subjects = subject_providers(settings)
        judges = judge_providers(settings)
        if len(judges) > 1:
            typer.echo(
                "panel of judges: "
                + ", ".join(j.model for j in judges)
                + " — grading runs once per judge"
            )
        typer.echo(
            f"concurrency: {settings.concurrency} calls to the models, "
            f"{settings.endpoint_concurrency} to the endpoint"
        )
        if defer_judging:
            typer.echo(
                "deferred judging: answers are written without a verdict. "
                "To judge them: export-judging --only-pending, then import-judging"
            )
            if blocks != (EvalBlock.DIRECT,):
                # Pressure and repeats are judge calls inside the block again,
                # and there is nothing to defer them with: a block either
                # delivers its verdict as it goes or does not happen at all.
                typer.echo(
                    "  denial_loop and monte_carlo call the judge themselves and "
                    "are therefore skipped; only direct runs"
                )
                blocks = (EvalBlock.DIRECT,)

        resuming = resume or settings.resume
        if resuming:
            window = settings.resume_window_hours
            typer.echo(
                "resuming: what is done is not asked again"
                + (f" (window {window} h)" if window else " (no time window)")
            )

        # One cache for this node's whole launch, and that is the whole point
        # of it. The question to the endpoint depends neither on the model
        # under test nor on the block: every model in arm C needs the very
        # same retrieval. Were the cache created inside a run, each would start from
        # a blank sheet and go to the RAG again for what it already knows.
        #
        # Per node rather than per launch because there is nothing to share
        # between nodes — the retrieval is this endpoint's — and because
        # `reuse_answers` is a setting a Space may hold its own value of.
        cache = RunCache(enabled=settings.reuse_answers)

        for chosen_mode in modes:
            try:
                _evaluate_arm(
                    target,
                    chosen_mode,
                    blocks=blocks,
                    subjects=subjects,
                    judges=judges,
                    context_source=context_source,
                    limit=limit,
                    cache=cache,
                    resume=resuming,
                    settings=settings,
                    defer_judging=defer_judging,
                )
            except (SliceMismatch, JudgeConflict) as exc:
                # Both refusals are about configuration, not about a failure of
                # the rig, and both are fixed by hand. Repeat the run and the
                # refusal repeats, so we stop right away. A traceback does not
                # help here: it hides the cause behind a dozen pipeline frames.
                typer.secho(f"{target.name}: {exc}", fg=typer.colors.YELLOW)
                raise typer.Exit(code=1) from exc
            except Exception as exc:  # noqa: BLE001 - see below
                # Everything else is about the rig: the node rebooted, the
                # database blinked, the provider dropped the connection. Such a
                # failure would take the remaining arms and models with it, even
                # though what was recorded is already in the database and the
                # other measurements have nothing to do with it. We say so
                # loudly and move on; finishing what was skipped is `--resume`.
                failures.append(f"{target.key}/{chosen_mode.value}: {exc}")
                typer.secho(
                    f"{target.name} / {chosen_mode.value} failed: {exc}",
                    fg=typer.colors.YELLOW,
                )

        if cache.enabled:
            typer.echo(f"repeats avoided — {cache.savings.line()}")

    if failures:
        typer.echo("")
        typer.secho(f"runs that failed: {len(failures)}", fg=typer.colors.YELLOW)
        for note in failures:
            typer.echo(f"  {note}")
        keys = " ".join(space) if space else ""
        typer.echo(
            "  to finish: uv run syft-benchmark evaluate "
            + (f"{keys} " if keys else "")
            + "--resume"
        )
        raise typer.Exit(code=1)


def _evaluate_arm(
    target: SpaceConfig,
    mode: ContextMode,
    *,
    blocks: tuple[EvalBlock, ...],
    subjects: list[Provider],
    judges: list[Provider],
    context_source: ContextSource | None,
    limit: int | None,
    cache: RunCache,
    resume: bool,
    settings: Settings,
    defer_judging: bool,
) -> None:
    """Run one arm over one Space through every block."""
    for chosen_block in blocks:
        for subject in subjects:
            if skips_monte_carlo(chosen_block, subject, settings):
                typer.echo(f"--- {monte_carlo_skip_note(subject.model)}")
                continue
            typer.echo(
                f"--- {target.name} / {ARM_LETTER.get(mode.value, '?')} "
                f"{mode.value} / {chosen_block.value} [{subject.model}]"
            )
            # The panel lives inside a run: whoever answers is asked once and
            # graded by every judge, otherwise each would see its own answer.
            outcomes = run_pass(
                target,
                mode,
                limit=limit,
                subject=subject,
                block=chosen_block,
                judges=judges,
                context_source=context_source,
                cache=cache,
                resume=resume,
                settings=settings,
                defer_judging=defer_judging,
            )
            for outcome in outcomes:
                if len(outcomes) > 1:
                    typer.echo(f"  judge {outcome.judge}")
                typer.echo(
                    f"  asked {outcome.asked}, correct {outcome.correct}, "
                    f"abstentions {outcome.abstain}, hallucinations "
                    f"{outcome.hallucinate}, failures {outcome.failed}"
                    + (
                        f", incomplete {outcome.incomplete}"
                        if outcome.incomplete
                        else ""
                    )
                    + (
                        f", taken from the earlier attempt {outcome.resumed}"
                        if outcome.resumed
                        else ""
                    )
                    + (
                        f", awaiting the judge {outcome.deferred}"
                        if outcome.deferred
                        else ""
                    )
                )
                for note in outcome.notes:
                    typer.echo(f"    {note}")


def judge(
    space: SpaceKeys = None,
    limit: Annotated[
        int | None,
        typer.Option(help="How many pending answers to grade; all by default"),
    ] = None,
) -> None:
    """Stage 5 on its own: grade the answers a deferred pass left pending.

    `evaluate --defer-judging` records answers without calling a judge. This
    is the other half: it grades what is pending, and answers whose judge call
    failed, live, without re-asking the model, the same way
    `export-judging`/`import-judging` do by hand — a new run per (arm,
    source, block, model), a new result per verdict, nothing overwritten.
    """
    for node_conf, target in resolve_nodes(space):
        outcome = judge_pending(target, limit=limit, settings=node_conf)
        typer.echo(f"--- {target.name}")
        typer.echo(f"  {outcome.line()}")
        for note in outcome.notes:
            typer.echo(f"  {note}")


def status(
    space: SpaceKeys = None,
    all_time: Annotated[
        bool, typer.Option("--all-time", help="Look at every run, not at the window")
    ] = False,
) -> None:
    """What is collected, what is missing and what will finish it.

    The first question after an interruption is "what is there already". It is
    counted by the same rule the report counts by: a fresh verdict for every
    question, otherwise "collected" and "in the report" would diverge silently.

    The default window is the same as the one for resuming: what is shown is
    the measurement under way, not the node's whole history. --all-time removes
    the window.
    """
    for settings, target in resolve_nodes(space):
        # The window comes from the node's settings too: what counts as "the
        # measurement under way" is the resume window, and a Space may hold its
        # own.
        since = None if all_time else window_start(settings)
        pairs = evaluable(active_pairs(target.key, settings), settings)
        frozen = ""
        if settings.question_set is not None:
            frozen = str(settings.question_set)
            try:
                pairs = questionset.apply(
                    questionset.load(settings.question_set),
                    pairs,
                    space=target.key,
                    strict=False,
                )
            except questionset.SliceMismatch as exc:
                typer.echo(f"{target.name}: the slice did not apply — {exc}")
                frozen = f"{frozen} (NOT APPLIED)"

        state = collect_status(
            target.key,
            total=len(pairs),
            frozen=frozen,
            generators={pair.id: pair.generator for pair in pairs},
            settings=settings,
            since=since,
        )

        counts = _dataset_counts(target.key, settings)
        typer.echo("")
        typer.echo(
            f"{target.name}: {state.total} items in the sample, "
            + (f"slice {state.frozen}" if state.frozen else "the slice is not frozen")
        )
        current = cohort_store.current(target.key, settings)
        typer.echo(
            f"  set {settings.dataset_mode.value}"
            + (f", cohort {current}" if current else "")
            + (
                f", period {settings.document_window_days} d."
                if settings.document_window_days
                else ""
            )
            + ": in the measurement "
            + str(counts.get("active", 0))
            + (f", left the set {counts['retired']}" if counts.get("retired") else "")
            + (f", rejected {counts['rejected']}" if counts.get("rejected") else "")
        )
        if not state.passes:
            typer.echo("  nothing has been collected yet")
            typer.echo("")
            typer.echo(f"  uv run syft-benchmark evaluate {target.key}")
            continue

        for entry in state.passes:
            typer.echo(
                f"  {entry.arm} {entry.context_mode.value:20} "
                f"{entry.block.value:12} {entry.model:28} "
                f"judge {entry.judge:22} {entry.line()}"
            )
        if state.coverage:
            lagging = {slow.generator for slow in state.uneven}
            typer.echo("")
            typer.echo("  Coverage by item type (verdicts out of those needed):")
            for covered in state.coverage:
                mark = "  <- lagging" if covered.generator in lagging else ""
                typer.echo(
                    f"    {covered.generator:26} "
                    f"{covered.graded:5}/{covered.expected:<5}"
                    f" {covered.share:>4.0%}{mark}"
                )

        typer.echo("")
        typer.echo("  What will finish it:")
        for step in state.advice():
            typer.echo(f"    {step}")


def _dataset_counts(space: str, settings: Settings) -> dict[str, int]:
    """How many items are in which state.

    What has dropped out of the set is counted apart from what was rejected:
    the first is a decision of the freshness window and is reversible, the
    second is a verdict on the reference answer and is not.
    """
    with session_scope(settings) as session:
        rows = session.execute(
            select(QaPair.status, func.count())
            .where(QaPair.space == space)
            .group_by(QaPair.status)
        ).all()
    return {str(row[0]): int(row[1]) for row in rows}


def cycle(
    space: SpaceKeys = None,
    every: Annotated[
        str, typer.Option(help="Interval: 24h, 6h, 90m; empty — a single run")
    ] = "",
    at: Annotated[str, typer.Option(help="Time of day HH:MM for a daily step")] = "",
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            "-r",
            help="Finish an interrupted cycle without re-asking what is done",
        ),
    ] = False,
) -> None:
    """The full daily cycle: generation, both runs, the report.

    --resume makes sense for a one-off launch: the cycle runs for hours, and
    both a node reboot and a spent balance have time to cut it short. An endless
    schedule does not need the flag — every step there measures afresh, that is
    what makes it a step.
    """
    # Resolved here so that an unknown key is refused before the first cycle
    # rather than in the middle of the night. A schedule then re-resolves them
    # itself: what the UI changes between cycles has to reach the next one.
    nodes = resolve_nodes(space)
    if not every:
        report = run_cycle(nodes, resume=resume)
        for path in report.written:
            typer.echo(f"report: {path}")
        return
    run_forever([node.key for _, node in nodes], every=every, at=at)
