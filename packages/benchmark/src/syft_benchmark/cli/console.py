"""The manual path: questions and answers carried to a chat and back."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from syft_benchmark.cli.common import resolve_nodes
from syft_benchmark.runs.console import (
    export_judging,
    export_questions,
    import_answers,
    import_judging,
)


def export_questions_cmd(
    space: Annotated[str, typer.Argument(help="The Space key")],
    out: Annotated[Path, typer.Option(help="Where to put the text")] = Path(
        "reports/questions.txt"
    ),
    limit: Annotated[int, typer.Option(help="How many questions to export")] = 20,
) -> None:
    """Export questions for testing a model by hand through a chat.

    For models with no API: paste the exported text into a chat, save the reply
    to a file and parse it with the import-answers command.
    """
    _, target = resolve_nodes([space])[0]
    outcome = export_questions(target.key, out, limit=limit)
    if not outcome.exported:
        typer.secho("no active items — run generate first", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    typer.echo(f"questions exported: {outcome.exported} -> {out}")
    typer.echo("")
    typer.secho(
        "Limits of the manual path: the temperature cannot be set (so\n"
        "monte_carlo is impossible), the dialogue cannot be continued\n"
        "(denial_loop likewise), and what answers is a chat with its own system\n"
        "prompt, not the model. These numbers cannot be compared directly with a\n"
        "run through the API.",
        fg=typer.colors.YELLOW,
    )


def import_answers_cmd(
    space: Annotated[str, typer.Argument(help="The Space key")],
    source: Annotated[Path, typer.Argument(help="File with the answers from the chat")],
    model: Annotated[
        str, typer.Option(help="What answered — it goes into the report")
    ] = "console",
) -> None:
    """Parse the pasted answers, judge them and record them as a run."""
    _, target = resolve_nodes([space])[0]
    if not source.exists():
        typer.secho(f"no such file: {source}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    outcome = import_answers(target.key, source, model)
    for note in outcome.notes or []:
        typer.secho(note, fg=typer.colors.YELLOW)
    if not outcome.matched:
        raise typer.Exit(code=1)

    typer.echo(
        f"parsed {outcome.matched}, correct {outcome.correct}, "
        f"abstentions {outcome.abstain}, hallucinations {outcome.hallucinate}"
        + (f", incomplete {outcome.incomplete}" if outcome.incomplete else "")
        + (f", from the web {outcome.web_sourced}" if outcome.web_sourced else "")
        + (f", failures {outcome.failed}" if outcome.failed else "")
    )
    if outcome.missing:
        typer.echo(f"answers with no pair in the dataset: {outcome.missing}")


def export_judging_cmd(
    space: Annotated[str, typer.Argument(help="The Space key")],
    judge: Annotated[
        str, typer.Option(help="The judge's name; it goes into the report")
    ],
    out: Annotated[
        Path | None, typer.Option(help="Where to put the assignment")
    ] = None,
    only_pending: Annotated[
        bool,
        typer.Option(
            "--only-pending",
            help="Pending answers and those whose judge call failed",
        ),
    ] = False,
    limit: Annotated[int | None, typer.Option(help="How many to export")] = None,
) -> None:
    """Export the collected answers to be judged by a person or a chat.

    Nobody re-asks whoever answered: what is judged is what was recorded. That
    is why a console judge carries none of a console model's limits — it needs
    neither a temperature nor a dialogue — and the judge's line leaves the bill
    entirely: a subscription takes its place.

    One answer is exported once, even if there have already been three judges:
    the answer of whoever answered is one for the whole panel.
    """
    settings, target = resolve_nodes([space])[0]
    path = out or Path(f"reports/judging-{target.key}-{_slug(judge)}.md")

    outcome = export_judging(
        target.key,
        path,
        judge,
        only_pending=only_pending,
        limit=limit,
        settings=settings,
    )
    for note in outcome.notes:
        typer.echo(note)
    if not outcome.exported:
        raise typer.Exit(code=1)

    typer.echo(f"{target.name}: {outcome.exported} answers to judge -> {path}")
    typer.echo("")
    typer.echo("Next: paste the text into a chat, put the reply in a file and load it")
    typer.echo(
        f"  uv run syft-benchmark import-judging {target.key} "
        f"--judge {judge} --verdicts <file>"
    )


def import_judging_cmd(
    space: Annotated[str, typer.Argument(help="The Space key")],
    judge: Annotated[
        str, typer.Option(help="The judge's name; it goes into the report")
    ],
    verdicts: Annotated[Path, typer.Option(help="File with the verdicts")],
) -> None:
    """Record console verdicts as the grading of a separate judge.

    The verdicts land in the report on a par with the machine ones — and in the
    judges' agreement too: the point of a second judge is that the first can be
    compared against them. The settings snapshot and the profile are copied
    from the original run: what is judged is a recorded answer, obtained under
    the settings of that time.
    """
    settings, target = resolve_nodes([space])[0]
    outcome = import_judging(target.key, verdicts, judge, settings=settings)

    for note in outcome.notes:
        typer.echo(note)
    typer.echo(
        f"{target.name}: judged {outcome.matched}, "
        f"correct {outcome.correct}, abstentions {outcome.abstain}, "
        f"hallucinations {outcome.hallucinate}"
        + (f", incomplete {outcome.incomplete}" if outcome.incomplete else "")
        + (f", not found {outcome.missing}" if outcome.missing else "")
    )
    for run_id in outcome.run_ids:
        typer.echo(f"  run {run_id}")


def _slug(name: str) -> str:
    """A model name in a form fit for a file name."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name)
