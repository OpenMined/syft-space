"""Building, screening, freezing and comparing the question set."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from syft_benchmark.cli.common import SpaceKeys, resolve_nodes
from syft_benchmark.config import ARM_LETTER, ContextMode, DatasetMode, EvalBlock
from syft_benchmark.generation import (
    GENERATORS,
    enabled_generators,
    filter_and_rotate,
    generate_for_space,
)
from syft_benchmark.generation import cohort as cohort_store
from syft_benchmark.generation.rotation import BadPeriod, parse_period
from syft_benchmark.report import stability
from syft_benchmark.runs import endpoint_retriever, questionset
from syft_benchmark.runs.execute import active_pairs, pick_pairs
from syft_benchmark.runs.gate import evaluable, nothing_passed


def generate(
    space: SpaceKeys = None,
    generator: Annotated[
        list[str] | None,
        typer.Option(
            "--generator",
            "-g",
            help="A generator; may be repeated. Empty — the default line-up",
        ),
    ] = None,
    collection: Annotated[
        str | None, typer.Option(help="Collection name; defaults to the Space key")
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            help=(
                "The question budget per kind for this run, in place of "
                "chunks_per_run: each kind writes at most limit x pairs_per_chunk"
            )
        ),
    ] = None,
    all_generators: Annotated[
        bool, typer.Option("--all", help="Run every generator, disabled ones included")
    ] = False,
    mode: Annotated[
        DatasetMode | None,
        typer.Option(help="How the set behaves over time; defaults to the settings"),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option(
            "--period",
            "-p",
            help="How far back to take documents: 1d, 7d, 2w, 1m; 0 — the whole corpus",
        ),
    ] = None,
    max_pairs: Annotated[
        int | None,
        typer.Option(help="Cap on active items in the set; 0 — no cap"),
    ] = None,
    new_cohort: Annotated[
        bool,
        typer.Option(
            "--new-cohort",
            help="Build the question pool afresh from the same material",
        ),
    ] = False,
    cohort_label: Annotated[
        str, typer.Option("--cohort", help="Cohort name; empty — date and time")
    ] = "",
) -> None:
    """Stage 2: build items from new chunks and documents.

    The set comes in three kinds. **incremental** — it accumulates: new material
    adds items, the earlier ones stay in the measurement. That is how you
    measure a stable corpus, where the right answer does not go stale.

    **rolling** — it moves with time: the measurement holds what grew out of
    the documents of the last --period. What leaves the window leaves the set
    but is NOT deleted: verdicts from earlier runs hang on it. What comes back
    into the window returns without another call to the generator.

    **rebuild** (which is what --new-cohort does) — takes THE SAME material and
    builds a fresh question pool from it, as a separate cohort. This is the way
    to answer "are the questions themselves any good": one material, the same
    models, the same judge — if the metrics diverge, it is the questions and the
    reference answers. It makes most sense to change the generator model while
    you are at it: two passes of one model reproduce its mistakes as well.

    --period sets the span in both cases: `1d` — yesterday, `7d` or `1w` — the
    week, `1m` — the month, `0` — the whole corpus. It counts back from "now",
    not from midnight. A rebuild WITHOUT a period rebuilds the set over the
    whole corpus and costs a full generation pass — on a live node that is
    usually not what anyone wants.

    The comparison between cohorts is shown by the `cohorts` command.
    """
    # The flags first, and only the flags: what they change is the same for
    # every node, while everything they change it on top of belongs to the node
    # and is fetched with it below.
    overrides: dict[str, object] = {}
    if mode is not None:
        overrides["dataset_mode"] = mode
    if period is not None:
        try:
            overrides["document_window_days"] = parse_period(period)
        except BadPeriod as exc:
            typer.secho(str(exc), fg=typer.colors.YELLOW)
            raise typer.Exit(code=1) from exc
    if max_pairs is not None:
        overrides["dataset_max_pairs"] = max_pairs

    asked: tuple[str, ...] | None = None
    if all_generators:
        asked = tuple(GENERATORS)
    elif generator:
        unknown = [key for key in generator if key not in GENERATORS]
        if unknown:
            typer.secho(
                f"unknown generators: {', '.join(unknown)} "
                f"(available: {', '.join(GENERATORS)})",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(code=1)
        asked = tuple(generator)

    for node_conf, target in resolve_nodes(space):
        # The node's settings, then the flags on top: a flag is the most
        # specific thing said about this run, so it wins over the layers, and
        # the layers win over the installation's defaults.
        settings = node_conf.model_copy(update=overrides) if overrides else node_conf
        # By default — every generator except the ones this node disables.
        chosen = asked or enabled_generators(settings.disabled_generators)
        if not chosen:
            typer.secho(
                f"{target.key}: every generator is turned off by the "
                f"disabled_generators setting",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(code=1)

        rebuilding = new_cohort or settings.dataset_mode is DatasetMode.REBUILD
        typer.echo(f"--- {target.name}  [{', '.join(chosen)}]")
        typer.echo(
            f"set: {settings.dataset_mode.value}"
            + (" + rebuild" if new_cohort else "")
            + (
                f", period {settings.document_window_days} d."
                if settings.document_window_days
                else ", the whole corpus"
            )
            + (
                f", cap {settings.dataset_max_pairs} items"
                if settings.dataset_max_pairs
                else ""
            )
        )
        if rebuilding and not settings.document_window_days:
            typer.secho(
                "rebuilding over the whole corpus: this is a full generation pass. "
                "Bound it by a period if you did not mean that: --period 7d",
                fg=typer.colors.YELLOW,
            )

        outcome = generate_for_space(
            target,
            generators=chosen,
            collection=collection,
            limit=limit,
            settings=settings,
            new_cohort=new_cohort,
            cohort_label=cohort_label,
        )
        typer.echo(
            f"units {outcome.units_seen}, items {outcome.pairs_made} pending"
            + (" — run `filter` to screen them" if outcome.pairs_made else "")
            + f", duplicates {outcome.duplicates}, failures {outcome.failures}"
        )
        for key, count in sorted(outcome.by_generator.items()):
            typer.echo(f"  {key:24} {count}")
        if outcome.cohort:
            typer.echo(f"  cohort {outcome.cohort}")
        if outcome.rotation is not None:
            typer.echo(f"  set: {outcome.rotation.line()}")
        for note in outcome.notes[:10]:
            typer.echo(f"  {note}")


def filter_cmd(
    space: SpaceKeys = None,
    generator: Annotated[
        str | None,
        typer.Option("--generator", "-g", help="Screen only this generator's pairs"),
    ] = None,
    cohort: Annotated[
        str | None, typer.Option("--cohort", help="Screen only this cohort")
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(help="How many pending pairs to screen; all by default"),
    ] = None,
) -> None:
    """Stage 2: decide which pending pairs are fit to measure with.

    Everything `generate` builds lands `pending`; this is what turns a
    pending pair `active` or `rejected` — grounding for an ordinary item,
    live retrieval for a control one. Only pending pairs are ever touched: an
    existing verdict stands until the console overturns it by hand.
    """
    for node_conf, target in resolve_nodes(space):
        outcome = filter_and_rotate(
            target,
            generator=generator,
            cohort=cohort,
            limit=limit,
            settings=node_conf,
            # "There is no answer" means something only relative to this
            # endpoint, not to an abstract corpus, so the control gate is
            # checked against this same endpoint's own retrieval.
            retrieve=endpoint_retriever(target, node_conf),
        )
        typer.echo(f"--- {target.name}")
        typer.echo(f"  {outcome.line()}")
        if outcome.rotation is not None:
            typer.echo(f"  set: {outcome.rotation.line()}")
        for note in outcome.notes[:10]:
            typer.echo(f"  {note}")


def freeze(
    space: Annotated[str, typer.Argument(help="The Space key")],
    out: Annotated[Path, typer.Option(help="Where to put the slice")],
    limit: Annotated[
        int | None,
        typer.Option(
            help=(
                "How many items to take into the slice from EVERY generator; "
                "empty — all the active ones"
            )
        ),
    ] = None,
) -> None:
    """Freeze a slice of questions: that very set, not "roughly the same one".

    The set is alive: generate adds items every cycle, rejection pulls pairs
    out of the active ones, the labelling of the control half gets refined. As
    long as "which questions" is decided by selection on the fly, two runs take
    different sets — and a difference in the numbers between them means not
    what was measured but that the set has grown.

    The slice pins identifiers together with a fingerprint of the question and
    the reference answer: a pair survives regeneration, its text does not, and
    without the fingerprint the substitution would stay silent.

    Rebuilding the slice makes sense for a NEW measurement. In the middle of an
    ongoing one it means changing the set underneath answers already collected.
    """
    settings, target = resolve_nodes([space])[0]
    active = active_pairs(target.key, settings)
    if not active:
        typer.echo(f"{target.name}: no active items — run generate first")
        raise typer.Exit(code=1)
    # Only questions that passed the web check are ever asked.
    rows = evaluable(active, settings)
    if not rows:
        typer.echo(f"{target.name}: {nothing_passed(len(active), settings)}")
        raise typer.Exit(code=1)

    picked = pick_pairs(rows, limit)
    data = questionset.build(
        target.key,
        picked,
        selection={"limit": limit, "of_active": len(rows)},
    )
    questionset.write(out, data)

    typer.echo(f"{target.name}: a slice of {len(picked)} items -> {out}")
    by_generator: dict[str, int] = {}
    by_half: dict[str, int] = {}
    for pair in picked:
        by_generator[pair.generator] = by_generator.get(pair.generator, 0) + 1
        by_half[pair.expected_behavior] = by_half.get(pair.expected_behavior, 0) + 1
    for key, count in sorted(by_half.items()):
        typer.echo(f"  half {key:20} {count}")
    for key, count in sorted(by_generator.items()):
        typer.echo(f"  {key:28} {count}")
    typer.echo("")
    typer.echo("To run against it:")
    typer.echo(f"  uv run syft-benchmark evaluate {target.key} --question-set {out}")


def cohorts(
    space: Annotated[str, typer.Argument(help="The Space key")],
    mode: Annotated[
        ContextMode, typer.Option("--mode", "-m", help="The arm to compare on")
    ] = ContextMode.CLOSED_BOOK,
    block: Annotated[EvalBlock, typer.Option("--block", "-b")] = EvalBlock.DIRECT,
    model: Annotated[str | None, typer.Option(help="The model under test")] = None,
    judge: Annotated[str | None, typer.Option(help="The judge")] = None,
) -> None:
    """The set's cohorts and the comparison between them.

    Same material, other questions.

    The benchmark measures a model with questions it wrote itself — and that is
    its weak spot. Checking them directly is impossible: that would take other
    questions. Indirectly it can be done: build a second pool from THE SAME
    material and compare. The corpus, the endpoint, the models under test and
    the judge are the same; only the questions change.

    If the numbers match, the difference between models speaks about the
    models. If they diverge, it speaks about the questions, and it is the
    generator that needs looking at.
    """
    settings, target = resolve_nodes([space])[0]

    known = cohort_store.listing(target.key, settings)
    if not known:
        typer.echo(f"{target.name}: no items — run generate first")
        raise typer.Exit(code=1)

    typer.echo(f"{target.name}: cohorts {len(known)}")
    for entry in known:
        built = entry.first_seen.strftime("%Y-%m-%d %H:%M") if entry.first_seen else "-"
        share = f"{entry.rejected / entry.pairs:.0%}" if entry.pairs else "-"
        typer.echo(
            f"  {entry.name:18} {built:16} items {entry.pairs:5}"
            f"  in the measurement {entry.active:5}  rejected {share:>5}"
            f"  [{entry.models}]"
        )

    comparison = stability.compare(target.key, mode, block, model, judge)
    if comparison is None:
        typer.echo("")
        typer.echo(
            "Nothing to compare: only one cohort has verdicts. "
            "Build a second pool from the same material:"
        )
        typer.echo(f"  uv run syft-benchmark generate {target.key} --new-cohort")
        typer.echo(
            "  (it makes most sense to change BENCH_GENERATOR_MODEL while you "
            "are at it — two passes of one model reproduce its mistakes as well)"
        )
        return

    typer.echo("")
    typer.echo(
        f"Comparison: {ARM_LETTER.get(mode.value, '?')} {mode.value} / "
        f"{block.value}" + (f" / {model}" if model else "")
    )
    for run in comparison.runs:
        typer.echo(
            f"  {run.cohort.name:18} items {run.metrics.graded:5}"
            f"  accuracy {run.metrics.accuracy:>5.0%}"
            f"  fabrications {run.metrics.hallucination_rate:>5.0%}"
            f"  abstentions {run.metrics.abstain_rate:>5.0%}"
        )

    typer.echo("")
    typer.echo(f"  accuracy spread between cohorts — {comparison.spread:.0%}")
    if comparison.suspect:
        typer.secho(
            "  the material is one and the same and the numbers diverged: this "
            "is not about the model under test but about the questions and the "
            "reference answers",
            fg=typer.colors.YELLOW,
        )
        typer.echo("  look at the rejection share and the items of the odd cohort:")
        typer.echo(
            f"    uv run syft-benchmark audit {target.key} "
            f"--out reports/audit-{target.key}.jsonl"
        )
    else:
        typer.echo("  the set is stable: the question pool does not move the numbers")
    if not comparison.built_by_different_generators:
        typer.echo(
            "  the cohorts were built by one generator — that is a repeat, not "
            "an independent check; for that you need a cohort from ANOTHER model"
        )
