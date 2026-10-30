"""The benchmark's command line.

The commands mirror the pipeline's stages and are invoked separately. Each
module holds one group of commands; this one registers them, in the order
``--help`` lists them.
"""

from __future__ import annotations

import sys

import typer

from syft_benchmark.cli import (
    console,
    dataset,
    diagnostics,
    installation,
    measure,
    reports,
    service,
)

app = typer.Typer(
    name="syft-benchmark",
    help="An honesty benchmark for Syft Space endpoints.",
    no_args_is_help=True,
    add_completion=False,
)

app.command()(diagnostics.spaces)
app.command()(diagnostics.models)
app.command()(diagnostics.upstreams)
app.command()(diagnostics.chunks)
app.command()(diagnostics.doctor)
app.command()(diagnostics.generators)
app.command()(dataset.generate)
app.command("filter")(dataset.filter_cmd)
app.command()(measure.evaluate)
app.command()(measure.judge)
app.command()(dataset.freeze)
app.command()(dataset.cohorts)
app.command()(measure.status)
app.command()(reports.report)
app.command()(reports.audit)
app.command("export-questions")(console.export_questions_cmd)
app.command("import-answers")(console.import_answers_cmd)
app.command("export-judging")(console.export_judging_cmd)
app.command("import-judging")(console.import_judging_cmd)
app.command()(measure.cycle)
app.command()(service.serve)
app.add_typer(installation.settings_app, name="settings")
app.add_typer(installation.secrets_app, name="secrets")


def main() -> None:
    """The ``syft-benchmark`` entry point."""
    # The Windows console code page (cp866/cp1251) cannot print every character
    # the output carries, and UnicodeEncodeError would kill the command mid-run;
    # an unprintable character becomes a question mark instead.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    app()
