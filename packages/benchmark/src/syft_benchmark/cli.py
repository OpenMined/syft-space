"""The benchmark's command line.

The commands mirror the pipeline's stages and are deliberately invoked
separately. Publishing is not stitched onto the tail of a run: a run can be
interrupted halfway, and there is no point publishing half the results —
checking is the owner's internal business, publishing metrics is a statement
made outwards.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy import case, func, select

from syft_benchmark.config import (
    ARM_LETTER,
    ContextMode,
    ContextSource,
    DatasetMode,
    EvalBlock,
    ExpectedBehavior,
    Settings,
    SpaceConfig,
    Verdict,
    check_model_host,
    env_settings,
    get_settings,
)
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.db.models import Result
from syft_benchmark.generation import (
    GENERATORS,
    enabled_generators,
    generate_for_space,
    spacy_available,
)
from syft_benchmark.generation import cohort as cohort_store
from syft_benchmark.generation.rotation import BadPeriod, parse_period
from syft_benchmark.llm import (
    JudgeConflict,
    Provider,
    catalog,
    check_model_available,
    generator_provider,
    judge_providers,
    openrouter,
    subject_providers,
)
from syft_benchmark.publish import payload_for
from syft_benchmark.publish import publish as publish_metrics
from syft_benchmark.publish import retract as retract_metrics
from syft_benchmark.report import (
    Metrics,
    build_docx,
    export_audit,
    judges_seen,
    models_seen,
    render_markdown,
    stability,
    summarize,
)
from syft_benchmark.report.card import RETRIEVAL
from syft_benchmark.report.card import build as build_card
from syft_benchmark.runs import (
    MODEL_ARMS,
    RunCache,
    arm_blocker,
    endpoint_mode,
    endpoint_retriever,
    questionset,
    run_pass,
)
from syft_benchmark.runs.console import (
    export_judging,
    export_questions,
    import_answers,
    import_judging,
)
from syft_benchmark.runs.execute import active_pairs, pick_pairs
from syft_benchmark.runs.questionset import SliceMismatch
from syft_benchmark.runs.resume import window_start
from syft_benchmark.runs.status import collect as collect_status
from syft_benchmark.sources import ChromaClient, ChromaError, load_documents

app = typer.Typer(
    name="syft-benchmark",
    help="An honesty benchmark for Syft Space endpoints.",
    no_args_is_help=True,
    add_completion=False,
)

SpaceKeys = Annotated[
    list[str] | None, typer.Argument(help="Space keys; empty — all of them")
]


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


def _slug(name: str) -> str:
    """A model name in a form fit for a file name."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name)


def _targets(space: list[str] | None) -> list[tuple[Settings, SpaceConfig]]:
    """Resolve keys from the command line into nodes and their settings.

    The registry is the targets table — the one the service reads and the Space
    writes to when an endpoint is opted into measuring. ``config/spaces.json``
    still works and is still read, but only to fill an empty table: one live
    registry, one set of addresses, one place to edit them.

    The settings that come back are the node's, not the installation's: the
    Space's instrument and the node's probe are already applied, so a command
    here measures what the same node measures when the UI launches it.
    """
    from syft_benchmark.control import targets as registry

    try:
        found = registry.resolve(space)
    except KeyError as e:
        typer.secho(str(e.args[0]), fg=typer.colors.YELLOW)
        raise typer.Exit(code=1) from e
    if not found:
        typer.secho(
            "there are no nodes in the registry — a Space adds one when an "
            "endpoint is opted into measuring, or seed the table with "
            "config/spaces.json (see config/spaces.example.json)",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)
    return found


@app.command()
def spaces() -> None:
    """Show the Space registry and the current settings."""
    settings = get_settings()

    typer.echo(f"database      {settings.database_url}")
    typer.echo(f"Ollama        {settings.ollama_url}")
    typer.echo(f"generator     {settings.generator_model}")
    typer.echo(f"judge         {settings.judge_model}")
    typer.echo(
        "external models "
        + (
            "ALLOWED: " + ", ".join(settings.external_hosts)
            if settings.allow_external_models
            else "forbidden"
        )
    )
    typer.echo("")

    for _, space in _targets(None):
        chroma = (
            f"{space.chroma_host}:{space.chroma_port}"
            if space.chroma_port
            else f"docker exec {space.container}"
        )
        collection = f"  collection: {space.collection}" if space.collection else ""
        typer.echo(
            f"{space.key:12} {space.url}  ->  /{space.endpoint}   "
            f"chroma: {chroma}{collection}"
        )


@app.command()
def models(
    query: Annotated[str, typer.Argument(help="Part of a name; empty — all")] = "",
    vendor: Annotated[str, typer.Option(help="One vendor only")] = "",
    refresh: Annotated[
        bool, typer.Option(help="Fetch the provider's list afresh and store it")
    ] = False,
    write: Annotated[
        Path | None,
        typer.Option(
            help="Also write the fetched list to a file — the shipped snapshot"
        ),
    ] = None,
    limit: Annotated[int, typer.Option(help="How many to print")] = 40,
) -> None:
    """Show the model catalogue, and refresh it when asked.

    The refresh is a call outside the perimeter, so it happens on this explicit
    word. ``--write`` regenerates the snapshot that ships with the code.
    """
    settings = get_settings()

    if refresh:
        check_model_host(openrouter.MODELS_URL, settings)
        document = openrouter.snapshot()
        entries = document.get("models") or []
        catalog.replace(document, settings)
        typer.echo(f"fetched {len(entries)} models from {document['source']}")
        if write is not None:
            write.write_text(
                json.dumps(document, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            typer.echo(f"written  {write}")

    catalogue = catalog.load(settings)
    for source, when in sorted(catalogue.fetched.items()):
        typer.echo(f"{source:12} fetched {when or 'unknown'}")
    typer.echo(f"{'':12} {len(catalogue.models)} models, {len(catalogue.pins)} pins")
    typer.echo("")

    found = catalogue.search(query=query, vendor=vendor, limit=limit)
    for entry in found:
        price = entry.pricing.get("prompt") or "-"
        typer.echo(f"{entry.id:52} {entry.vendor:16} {price:>14} $/token in")
    typer.echo("")
    typer.echo(f"{len(found)} shown")


@app.command()
def upstreams(
    space: Annotated[str, typer.Option(help="One Space only; empty — all")] = "",
    days: Annotated[int, typer.Option(help="How far back to look; 0 — all time")] = 30,
    min_rows: Annotated[int, typer.Option(help="Hide upstreams seen fewer times")] = 5,
) -> None:
    """Who actually served the calls, and how the verdicts fell out per upstream.

    The table for deciding whether a router's choice of host matters here: if
    the wrong answers cluster on one, there is something to pin.

    Raw counts of stored verdicts, NOT the report's shares — a failed call and
    an honestly wrong answer are both a miss here. Read it to compare upstreams
    with each other, never to state how good a model is.
    """
    settings = get_settings()

    def table(who: str, name_col: Any, host_col: Any) -> None:
        rows = session.execute(
            select(
                name_col,
                host_col,
                func.count().label("n"),
                func.sum(case((Result.verdict == Verdict.CORRECT.value, 1), else_=0)),
                func.sum(case((Result.verdict == Verdict.ABSTAIN.value, 1), else_=0)),
            )
            .where(*conditions, host_col != "")
            .group_by(name_col, host_col)
            .order_by(name_col, func.count().desc())
        ).all()

        typer.echo(who)
        if not rows:
            typer.echo(
                "  nothing routed — a local model, or no run since this "
                "was first recorded"
            )
            typer.echo("")
            return
        for model, host, total, correct, abstain in rows:
            if total < min_rows:
                continue
            typer.echo(
                f"  {model[:44]:44} {host[:18]:18} {total:6}  "
                f"correct {correct / total:5.1%}  abstain {abstain / total:5.1%}"
            )
        typer.echo("")

    conditions = []
    if space:
        conditions.append(Result.space == space)
    if days > 0:
        since = datetime.now(UTC) - timedelta(days=days)
        conditions.append(Result.created_at >= since)

    with session_scope(settings) as session:
        table("models under test", Result.model, Result.served_by)
        table("judges", Result.judge_model, Result.judge_served_by)

    typer.echo(
        "One host per row. A model split across hosts whose columns differ is "
        "the case for pinning; one whose columns agree is the case against."
    )


@app.command()
def chunks(
    space: Annotated[str, typer.Argument(help="The Space key")],
    collection: Annotated[
        str | None,
        typer.Option(help="Collection name; by default the one the node carries"),
    ] = None,
) -> None:
    """Read the Space's index and show how much material there is for questions.

    A diagnostic command: it checks that there is a road to the node's ChromaDB
    and that there are usable chunks in it — before any generation, which costs
    hours.
    """
    settings, target = _targets([space])[0]

    client = ChromaClient(target, settings)
    # The node's own collection first, exactly as the generation pipeline
    # resolves it. Falling back to the key before it would look at a collection
    # no Space ever creates: a key is an endpoint's slug, and a collection name
    # takes no hyphens and arrives with a prefix in front of it.
    name = collection or target.collection or target.key
    try:
        collection_id = client.collection_id(name)
        if collection_id is None:
            available = ", ".join(str(c.get("name")) for c in client.collections())
            typer.secho(
                f'node "{target.key}" has no collection "{name}" '
                f"(available: {available or '-'})",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(code=1)
        total = client.count(collection_id)
        documents = load_documents(client, collection_id)
    except ChromaError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e

    usable = sum(len(d.chunks) for d in documents)
    typer.echo(f"transport   {client.transport}")
    typer.echo(f"collection  {name}")
    typer.echo(f"chunks      {total}, of them usable {usable}")
    typer.echo(f"documents   {len(documents)}")
    typer.echo("")
    for doc in documents[:10]:
        typer.echo(f"  {len(doc.chunks):3}  {doc.title[:70]}")
    if len(documents) > 10:
        typer.echo(f"  ... and {len(documents) - 10} more")


@app.command()
def doctor() -> None:
    """Check that everything a run depends on is in place."""
    from syft_benchmark.control import targets as target_registry

    settings = get_settings()
    problems = 0
    registry: list[tuple[Settings, SpaceConfig]] = []

    # The database first: without it nothing works, and its absence later looks
    # like a dozen different errors in the middle of a run. The schema is
    # checked by a column from the latest migration — connecting is not enough,
    # it has to be upgraded too.
    try:
        with session_scope(settings) as session:
            session.execute(select(func.count()).select_from(QaPair)).scalar()
            session.execute(select(QaPair.cohort).limit(1)).all()
        typer.echo("[ok]   database and schema are in place")
    except Exception as exc:  # noqa: BLE001 - show the cause, whatever it is
        typer.secho(
            f"[no]   database: {exc}\n"
            f"       docker compose up -d && uv run alembic upgrade head",
            fg=typer.colors.YELLOW,
        )
        problems += 1

    # The registry is the table. It is read here rather than through _targets
    # so that an empty one is a line in this report instead of the end of it:
    # the point of a check is to say everything that is wrong at once.
    try:
        registry = target_registry.resolve()
        if registry:
            typer.echo(f"[ok]   registry: {len(registry)} node(s) in the table")
        else:
            typer.secho(
                "[no]   the registry is empty: no Space has opted an endpoint "
                "into measuring, and there is no config/spaces.json to seed it",
                fg=typer.colors.YELLOW,
            )
            problems += 1
    except Exception as exc:  # noqa: BLE001 - the database is reported above
        typer.secho(f"[no]   registry: {exc}", fg=typer.colors.YELLOW)
        problems += 1

    # Every role is checked against ITS OWN provider: the address and the key
    # may differ per role, and a check against the shared settings would speak
    # about a different connection than the one the real call will take.
    roles = [("generator", generator_provider(settings))]
    judges = judge_providers(settings)
    for number, provider in enumerate(judges, start=1):
        label = "judge" if len(judges) == 1 else f"judge {number}"
        roles.append((label, provider))

    for role, provider in roles:
        try:
            check_model_available(provider.model, settings, provider)
            typer.echo(f"[ok]   {role}: {provider.model}")
        except Exception as e:  # noqa: BLE001 - show the cause, whatever it is
            typer.secho(f"[no]   {role} {provider.model}: {e}", fg=typer.colors.YELLOW)
            problems += 1

    # The arms are checked against the endpoint's mode: the owner decides what
    # is available at all — raw hands back chunks only, summary hands back prose
    # only and strips references. An incompatibility has to be named here, not
    # discovered from the zeros in a report after a run that costs hours.
    # Each node against ITS OWN settings, for the same reason the roles are
    # checked against their own providers: the arms may be set on the Space or
    # on the endpoint, and a check against the installation's defaults would
    # pass a node that is configured to run an arm it cannot.
    for node_conf, target in registry:
        mode = endpoint_mode(target)
        if not mode:
            typer.secho(
                f"[?]    {target.key}: the endpoint's mode was not read — "
                f"arm compatibility is unknown",
                fg=typer.colors.YELLOW,
            )
            continue
        typer.echo(f"[ok]   {target.key}: the endpoint is in {mode} mode")
        for arm in node_conf.arms:
            blocker = arm_blocker(arm, mode, node_conf.context_source)
            if blocker:
                typer.secho(
                    f"[no]   {target.key} / arm {ARM_LETTER.get(arm.value, '?')} "
                    f"{arm.value}: {blocker}",
                    fg=typer.colors.YELLOW,
                )
                problems += 1

    if problems:
        raise typer.Exit(code=1)
    typer.secho("everything is in place", fg=typer.colors.GREEN)


@app.command()
def generators() -> None:
    """Show the generators: what each one builds and how it is judged."""
    settings = get_settings()

    generator = generator_provider(settings)
    judges = judge_providers(settings)

    typer.echo("--- model roles")
    for provider in (generator, *judges, *subject_providers(settings)):
        where = "outside" if provider.is_external else "inside the perimeter"
        vendor = provider.vendor or "local"
        typer.echo(f"{provider.role:12} {provider.model:36} {where:20} {vendor}")
    typer.echo("")
    typer.echo(
        "arms                  "
        + ", ".join(f"{ARM_LETTER.get(a.value, '?')} {a.value}" for a in settings.arms)
    )
    typer.echo(f"arm C context         {settings.context_source.value}")
    typer.echo(f"chunks in the prompt  {settings.context_docs}")
    typer.echo(
        f"retrieval             top-{settings.retrieval_top_k}, "
        f"threshold {settings.similarity_threshold}"
    )
    typer.echo(f"methodology profile   {settings.methodology_profile}")
    typer.echo(
        "audit log             "
        + ("kept" if settings.audit_log else "OFF — verdicts cannot be checked")
    )
    typer.echo("")
    typer.echo(f"judge policy          {settings.judge_policy.value}")
    typer.echo(f"evaluation blocks     {', '.join(b.value for b in settings.blocks)}")
    typer.echo(
        f"concurrency           {settings.concurrency} to the models, "
        f"{settings.endpoint_concurrency} to the endpoint"
    )
    typer.echo(
        "repeated questions    "
        + (
            "not asked again"
            if settings.reuse_answers
            else "asked again — the cache is off"
        )
    )
    typer.echo(
        f"item set              {settings.dataset_mode.value}"
        + (
            f", period {settings.document_window_days} d."
            if settings.document_window_days
            else ", the whole corpus"
        )
        + (f", cap {settings.dataset_max_pairs}" if settings.dataset_max_pairs else "")
    )
    typer.echo(
        "resuming              "
        + (
            f"on by default, window {settings.resume_window_hours} h"
            if settings.resume
            else f"behind --resume, window {settings.resume_window_hours} h"
        )
    )
    typer.echo(f"pressure rounds       {settings.denial_rounds}")
    typer.echo(
        "temperatures          "
        + ", ".join(str(x) for x in settings.monte_carlo_temperatures)
        + f"  x{settings.monte_carlo_trials}"
    )
    typer.echo("")
    typer.echo(f"extractive mode       {settings.extractive_mode}")
    typer.echo(
        "spaCy                 "
        + ("installed" if spacy_available() else "not installed — the LLM path")
    )
    active = enabled_generators(settings.disabled_generators)
    typer.echo(f"generators enabled    {len(active)} of {len(GENERATORS)}")
    if settings.disabled_generators:
        typer.echo(f"disabled              {', '.join(settings.disabled_generators)}")
    typer.echo("")
    typer.echo(f"{'key':24}{'class':12}{'scope':10}{'grading':11}{'expected':17}source")
    for key, spec in GENERATORS.items():
        source = "spaCy or LLM" if not spec.needs_llm else "LLM"
        # The correct behaviour belongs next to the generator: for control
        # items it is not "answer", and that is the main thing to know about
        # them.
        typer.echo(
            f"{key:24}{spec.task_type:12}{spec.scope:10}{spec.grading:11}"
            f"{spec.expected.value:17}{source}"
        )
    control = [k for k, s in GENERATORS.items() if s.is_control]
    if control:
        typer.echo("")
        typer.echo(
            "control generators ("
            + ", ".join(control)
            + ") check their questions against live retrieval: without a "
            "reachable endpoint their items are rejected"
        )


@app.command()
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
                "How many units (chunks or documents) to hand to EVERY "
                "generator. This is not a number of items and not a percentage"
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
    """Stage 1: build items from new chunks and documents.

    The set comes in two kinds. **incremental** — it accumulates: new material
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

    for node_conf, target in _targets(space):
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
            # Control questions are checked with the same retrieval that is
            # later measured: "there is no answer" only means something
            # relative to this endpoint, not to an abstract corpus.
            retrieve=endpoint_retriever(target, settings),
            new_cohort=new_cohort,
            cohort_label=cohort_label,
        )
        typer.echo(
            f"units {outcome.units_seen}, items {outcome.pairs_made} "
            f"(usable {outcome.pairs_active}, rejected {outcome.pairs_rejected}), "
            f"duplicates {outcome.duplicates}, failures {outcome.failures}"
        )
        for key, count in sorted(outcome.by_generator.items()):
            typer.echo(f"  {key:24} {count}")
        if outcome.cohort:
            typer.echo(f"  cohort {outcome.cohort}")
        if outcome.rotation is not None:
            typer.echo(f"  set: {outcome.rotation.line()}")
        for note in outcome.notes[:10]:
            typer.echo(f"  {note}")


@app.command()
def evaluate(
    space: SpaceKeys = None,
    mode: Annotated[
        list[ContextMode] | None,
        typer.Option(
            "--mode",
            "-m",
            help="Arm: closed_book (A), open_book (B), model_with_context (C)",
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
    """Stages 2-4: ask the questions and judge the answers.

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

    for node_conf, target in _targets(space):
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
        # under test nor on the block: arm B has already gone for the
        # retrieval, arm C needs the very same one, and so do all nine models
        # inside it. Were the cache created inside a run, each would start from
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
        # Pressure requires a dialogue, and the endpoint's API is single-turn:
        # it takes one question as a string. In arm C a model answers, and
        # there is a dialogue there — pressure applies and means something.
        # Repeats at different temperatures are available everywhere and are
        # therefore not skipped.
        if chosen_block is EvalBlock.DENIAL_LOOP and mode is ContextMode.OPEN_BOOK:
            typer.echo(
                f"--- {target.name}: denial_loop does not apply to the endpoint "
                f"(its API is single-turn)"
            )
            continue

        targets: list[Provider | None] = (
            list(subjects) if mode in MODEL_ARMS else [None]
        )
        for subject in targets:
            who = subject.model if subject else target.endpoint
            typer.echo(
                f"--- {target.name} / {ARM_LETTER.get(mode.value, '?')} "
                f"{mode.value} / {chosen_block.value} [{who}]"
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


@app.command()
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
    settings, target = _targets([space])[0]
    rows = active_pairs(target.key, settings)
    if not rows:
        typer.echo(f"{target.name}: no active items — run generate first")
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


@app.command()
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
    settings, target = _targets([space])[0]

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


@app.command()
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
    for settings, target in _targets(space):
        # The window comes from the node's settings too: what counts as "the
        # measurement under way" is the resume window, and a Space may hold its
        # own.
        since = None if all_time else window_start(settings)
        pairs = active_pairs(target.key, settings)
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


@app.command()
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
    """Stage 5: fold the verdicts into metrics and a report.

    Markdown reads in a console and compares line by line between runs; --docx
    builds a document for a person out of the same metrics — with charts, an
    explanation of the quantities and a conclusion.
    """
    collected: list[Metrics] = []
    for _, target in _targets(space):
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


@app.command()
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
    _, target = _targets([space])[0]
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


@app.command()
def publish(
    space: SpaceKeys = None,
    dry_run: Annotated[
        bool, typer.Option(help="Show what would have been sent")
    ] = False,
) -> None:
    """Stage 5: hand the card to the Space to publish.

    The arm is chosen by the kind of product, not by a setting. For an endpoint
    in ``raw`` mode arm B does not exist at all — it retrieves, it does not
    answer — and a setting would leave such a node without a single number
    despite excellent retrieval. Its product is measured by how well retrieval
    hits and by whether the material it hands out pushes someone else's model
    into fabrication.
    """
    for _, target in _targets(space):
        # What goes to the storefront is the direct check: the numbers of the
        # blocks are the owner's internal analytics.
        card = build_card(target.key, target.endpoint)
        if card is None:
            typer.echo(f"{target.key}: no verdicts — nothing to publish")
            continue

        kind = "retrieves" if card.kind == RETRIEVAL else "answers"
        score = f"{card.score:.0%}" if card.score is not None else "-"
        fabrication = f"{card.fabrication:.0%}" if card.fabrication is not None else "-"
        typer.echo(
            f"{target.key} ({kind}, arm {card.arm}): "
            f"{card.score_label} {score}, fabrications {fabrication}, "
            f"questions {card.trust.samples if card.trust else 0}"
        )
        if card.models:
            low, high = card.spread or (card.models[0].accuracy,) * 2
            typer.echo(
                f"  with the models under test ({len(card.models)}): "
                f"from {low:.0%} to {high:.0%}"
            )
        if card.trust and not card.trust.reliable:
            typer.secho(
                "  it will reach the storefront with a note:",
                fg=typer.colors.YELLOW,
            )
            for note in card.trust.doubts:
                typer.secho(f"    {note}", fg=typer.colors.YELLOW)

        if dry_run:
            typer.echo(
                "  payload: "
                + json.dumps(payload_for(card), ensure_ascii=False, indent=2).replace(
                    "\n", "\n  "
                )
            )
            continue

        outcome = publish_metrics(target, card)
        colour = typer.colors.GREEN if outcome.ok else typer.colors.YELLOW
        typer.secho(f"  {outcome.detail}", fg=colour)


@app.command()
def retract(
    space: Annotated[str, typer.Argument(help="The Space key")],
) -> None:
    """Retract the published metrics through the Space."""
    _, target = _targets([space])[0]
    outcome = retract_metrics(target)
    colour = typer.colors.GREEN if outcome.ok else typer.colors.YELLOW
    typer.secho(outcome.detail, fg=colour)


@app.command("export-questions")
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
    _, target = _targets([space])[0]
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


@app.command("import-answers")
def import_answers_cmd(
    space: Annotated[str, typer.Argument(help="The Space key")],
    source: Annotated[Path, typer.Argument(help="File with the answers from the chat")],
    model: Annotated[
        str, typer.Option(help="What answered — it goes into the report")
    ] = "console",
) -> None:
    """Parse the pasted answers, judge them and record them as a run."""
    _, target = _targets([space])[0]
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
    )
    if outcome.missing:
        typer.echo(f"answers with no pair in the dataset: {outcome.missing}")


@app.command("export-judging")
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
        typer.Option("--only-pending", help="Only the answers without a verdict"),
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
    settings, target = _targets([space])[0]
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


@app.command("import-judging")
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
    settings, target = _targets([space])[0]
    outcome = import_judging(target.key, verdicts, judge, settings=settings)

    for note in outcome.notes:
        typer.echo(note)
    typer.echo(
        f"{target.name}: judged {outcome.matched}, "
        f"correct {outcome.correct}, incorrect {outcome.hallucinate}"
        + (f", not found {outcome.missing}" if outcome.missing else "")
    )
    for run_id in outcome.run_ids:
        typer.echo(f"  run {run_id}")


@app.command()
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
    """The full daily cycle: generation, both runs, the report, publishing.

    --resume makes sense for a one-off launch: the cycle runs for hours, and
    both a node reboot and a spent balance have time to cut it short. An endless
    schedule does not need the flag — every step there measures afresh, that is
    what makes it a step.
    """
    from syft_benchmark.scheduler import run_cycle, run_forever

    # Resolved here so that an unknown key is refused before the first cycle
    # rather than in the middle of the night. A schedule then re-resolves them
    # itself: what the UI changes between cycles has to reach the next one.
    nodes = _targets(space)
    if not every:
        run_cycle(nodes, resume=resume)
        return
    run_forever([node.key for _, node in nodes], every=every, at=at)


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="The address to listen on")] = "",
    port: Annotated[int, typer.Option(help="The port")] = 0,
    reload: Annotated[
        bool, typer.Option("--reload", help="Restart when the code is edited")
    ] = False,
) -> None:
    """Raise the control API: targets, settings and launching runs from the UI.

    The same process also holds the job queue. There is no point separating
    them: the queue is strictly sequential, and a measurement spends almost all
    its time waiting on a socket.
    """
    import uvicorn

    settings = get_settings()
    if not settings.control_token:
        typer.secho(
            "BENCH_CONTROL_TOKEN is not set — the API will come up, but to "
            "everything except /health it will answer that it is not configured",
            fg=typer.colors.YELLOW,
        )
    uvicorn.run(
        "syft_benchmark.control.app:create_app",
        factory=True,
        host=host or settings.control_host,
        port=port or settings.control_port,
        reload=reload,
    )


# --- the installation's settings and its secrets -----------------------------
#
# The store is where a setting is written, so the console needs a way in — or an
# installation without a UI would be one where nothing can be changed.

settings_app = typer.Typer(help="The installation's own settings — the bottom layer")
secrets_app = typer.Typer(help="Provider keys and Space tokens, sealed")
app.add_typer(settings_app, name="settings")
app.add_typer(secrets_app, name="secrets")


@settings_app.command("show")
def settings_show() -> None:
    """What this installation has overridden, and what it comes to.

    The overrides and the effective values are shown apart on purpose: "top-5
    because nobody changed it" and "top-5 because somebody chose it" look the
    same and are not, and only the second survives a change to the default.
    """
    from syft_benchmark.db import store

    overrides = store.read(env_settings())
    if not overrides:
        typer.secho("nothing is overridden — every setting is at its default", dim=True)
    for field, value in sorted(overrides.items()):
        typer.echo(f"{field} = {json.dumps(value, ensure_ascii=False)}")


@settings_app.command("set")
def settings_set(
    field: Annotated[str, typer.Argument(help="The setting's name")],
    value: Annotated[str, typer.Argument(help="The value, as JSON or as plain text")],
) -> None:
    """Override one setting for the whole installation.

    The value is read as JSON where it is JSON — so a list and a number arrive
    as a list and a number — and as text otherwise, because `default` is a
    perfectly good setting value and quoting it would be a trap.
    """
    from syft_benchmark.db import store

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value

    conf = env_settings()
    current = store.read(conf)
    current[field] = parsed
    try:
        store.write(conf, current)
    except (store.SettingRejected, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"{field} = {json.dumps(parsed, ensure_ascii=False)}", fg=typer.colors.GREEN
    )


@settings_app.command("unset")
def settings_unset(
    field: Annotated[str, typer.Argument(help="The setting's name")],
) -> None:
    """Drop an override, putting the setting back to its default."""
    from syft_benchmark.db import store

    conf = env_settings()
    current = store.read(conf)
    if field not in current:
        typer.secho(f"{field} was not overridden", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    del current[field]
    store.write(conf, current)
    typer.secho(f"{field} is back to its default", fg=typer.colors.GREEN)


@secrets_app.command("keygen")
def secrets_keygen() -> None:
    """Print a fresh master key.

    It exists so that nobody invents one. A key typed by a person is a
    password, and a password is not 256 bits of anything.
    """
    from syft_benchmark.db.crypto import new_key

    typer.echo(f"BENCH_SECRET_KEY={new_key()}")


@secrets_app.command("list")
def secrets_list() -> None:
    """Which secrets are stored and when they were last set.

    Not the values. They go in and do not come out — not here, not through the
    API — and the only thing that needs one is the call it authorises.
    """
    from syft_benchmark.db import store

    conf = env_settings()
    stored = store.secrets(conf)
    if not stored:
        typer.secho("no secrets are stored", dim=True)
    for item in stored:
        typer.echo(f"{item.name:30} set {item.updated_at:%Y-%m-%d %H:%M} UTC")

    # The ones that are not stored but are in force anyway. Leaving them unsaid
    # would let "the keys are encrypted" be believed about a key in a file.
    for name in store.env_secrets(conf):
        typer.secho(
            f"{name:30} from the environment, in the clear", fg=typer.colors.YELLOW
        )


@secrets_app.command("set")
def secrets_set(
    name: Annotated[str, typer.Argument(help="llm_api_key, judge_key, target:<key>…")],
    value: Annotated[
        str, typer.Option(help="The secret; omitted, it is read from stdin")
    ] = "",
) -> None:
    """Store one secret, sealed.

    Reading from stdin is the point of the option being optional: a key passed
    as an argument is a key in the shell history and in the process list of
    every user on the machine.
    """
    from syft_benchmark.db import store
    from syft_benchmark.db.crypto import SecretsNotConfigured

    secret = value or sys.stdin.read().strip()
    if not secret:
        typer.secho("nothing was given to store", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    try:
        store.set_secret(env_settings(), name, secret)
    except SecretsNotConfigured as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(f"{name} is stored", fg=typer.colors.GREEN)


@secrets_app.command("unset")
def secrets_unset(
    name: Annotated[str, typer.Argument(help="The secret's name")],
) -> None:
    """Remove a secret."""
    from syft_benchmark.db import store

    if not store.clear_secret(env_settings(), name):
        typer.secho(f"there is no secret called {name!r}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    typer.secho(f"{name} is gone", fg=typer.colors.GREEN)


@secrets_app.command("rotate")
def secrets_rotate() -> None:
    """Re-seal every secret under the active master key.

    The step in the middle of a rotation: make the new key active, move the old
    one into BENCH_SECRET_KEYS_RETIRED, run this, and only then throw the old
    key away. Rows already on the active key are skipped, so an interrupted
    rotation is finished by running it again.
    """
    from syft_benchmark.db import store
    from syft_benchmark.db.crypto import SecretsNotConfigured, SecretUnreadable

    try:
        moved = store.rotate(env_settings())
    except (SecretsNotConfigured, SecretUnreadable) as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(f"re-sealed: {moved}", fg=typer.colors.GREEN)


def main() -> None:
    # The Windows console code page (cp866/cp1251) does not cover even part of
    # the characters that show up in the output, and printing such a character
    # kills the command with UnicodeEncodeError. We switch the stream to UTF-8:
    # replacing an unprintable character with a question mark is an acceptable
    # price, falling over in the middle of a run is not.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    app()


if __name__ == "__main__":
    main()
