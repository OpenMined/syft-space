"""Reading the verdicts back: the report and the audit export."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from syft_benchmark.cli.common import SpaceKeys, resolve_nodes
from syft_benchmark.config import ContextMode, EvalBlock, ExpectedBehavior
from syft_benchmark.report import (
    Metrics,
    build_docx,
    export_audit,
    judges_seen,
    models_seen,
    render_markdown,
    summarize,
)


def report(
    space: SpaceKeys = None,
    out: Annotated[
        Path | None, typer.Option(help="Where to put the Markdown report")
    ] = None,
    docx: Annotated[
        Path | None,
        typer.Option(
            help="Where to put the document with charts and the conclusion (.docx)",
        ),
    ] = None,
) -> None:
    """Stage 6: fold the verdicts into metrics and a report.

    Markdown reads in a console and compares line by line between runs; --docx
    builds a document for a person out of the same metrics — with charts, an
    explanation of the quantities and a conclusion.
    """
    collected: list[Metrics] = []
    for _, target in resolve_nodes(space):
        for mode in ContextMode:
            for block in EvalBlock:
                # The models come from the data, not from the settings: a
                # manual run is recorded under its own name, and it has to make
                # it into the report. Split by judge too: without it the
                # panel's verdicts would merge, and the report would carry the
                # opinion of whoever judged last.
                for model in models_seen(target.key, mode, block):
                    for judge in judges_seen(target.key, mode, block):
                        # The halves of the set are counted apart: for a
                        # control question no right answer exists, and accuracy
                        # computed over both at once falls simply because there
                        # are more control questions.
                        for expected in ExpectedBehavior:
                            metrics = summarize(
                                target.key, mode, block, model, judge, expected
                            )
                            if metrics is not None:
                                collected.append(metrics)

    if not collected:
        typer.secho("no verdicts — run evaluate first", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    text = render_markdown(collected)
    typer.echo(text)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"report written: {out}")

    if docx is not None:
        written = build_docx(collected, docx)
        typer.echo(f"document written: {written}")
        typer.secho(
            "the document is built from aggregated numbers: it holds no "
            "questions, no reference answers and no corpus text. The raw "
            "records of the measurement are what the audit command hands out",
            fg=typer.colors.BLUE,
        )


def audit(
    space: Annotated[str, typer.Argument(help="The Space key")],
    out: Annotated[
        Path, typer.Option(help="Export file; .md — to read, otherwise JSON Lines")
    ] = Path("reports/audit.jsonl"),
    judge: Annotated[
        str | None, typer.Option(help="Keep the verdicts of one judge")
    ] = None,
    job: Annotated[
        str | None,
        typer.Option(help="Keep the records of one launch — its id from the history"),
    ] = None,
    no_context: Annotated[
        bool,
        typer.Option(
            "--no-context",
            help="Strip the chunk texts and the prompts — a verdict cannot be "
            "checked against such an export",
        ),
    ] = False,
) -> None:
    """Export the measurement's raw records for inspection.

    Metrics are shares over a judge model's verdicts, and they cannot be
    checked against the shares themselves. The export hands out the raw
    material: the question, the reference answer, the answers of every arm side
    by side, the prompts they were obtained with, and each judge's reasoning.

    --job checks one measurement instead of the node's whole history. Settings
    change between launches, and an export that mixed two of them would lay
    answers obtained at different thresholds side by side under one heading.
    """
    _, target = resolve_nodes([space])[0]
    outcome = export_audit(
        target.key, out, judge=judge, include_context=not no_context, job=job
    )

    typer.echo(
        f"questions {outcome.questions}, answers {outcome.answers} "
        f"(arms {', '.join(outcome.arms) or '-'}; "
        f"judges {', '.join(outcome.judges) or '-'})"
    )
    typer.echo(f"with prompts {outcome.with_prompts} of {outcome.answers}")
    if outcome.answers and not outcome.with_prompts:
        typer.secho(
            "not a single record holds a prompt: the run went with "
            "BENCH_AUDIT_LOG=false or before the log existed. They cannot be "
            "reconstructed after the fact — a prompt depends on the settings of "
            "the moment; such verdicts can only be rechecked by a new run",
            fg=typer.colors.YELLOW,
        )
    typer.echo(f"written: {outcome.path}")
    if not no_context:
        typer.secho(
            "WARNING: the export holds corpus text — reference answers quote the "
            "source, and arm C's prompt carries the retrieved chunks whole. "
            "Handle the file as you would the corpus itself.",
            fg=typer.colors.YELLOW,
        )
