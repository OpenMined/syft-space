"""Read-only commands that show the configuration, the catalogue and the nodes."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy import case, func, make_url, select

from syft_benchmark.cli.common import resolve_nodes
from syft_benchmark.config import (
    ARM_LETTER,
    Settings,
    SpaceConfig,
    Verdict,
    check_model_host,
    get_settings,
)
from syft_benchmark.control import targets as target_registry
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.db.models import Result
from syft_benchmark.generation import GENERATORS, enabled_generators
from syft_benchmark.llm import (
    catalog,
    check_model_available,
    generator_provider,
    judge_providers,
    openrouter,
    subject_providers,
)
from syft_benchmark.runs import arm_blocker, endpoint_mode
from syft_benchmark.sources import ChromaClient, ChromaError, load_documents


def spaces() -> None:
    """Show the Space registry and the current settings."""
    settings = get_settings()

    database = make_url(settings.database_url).render_as_string(hide_password=True)
    typer.echo(f"database      {database}")
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

    for _, space in resolve_nodes(None):
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
    settings, target = resolve_nodes([space])[0]

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


def doctor() -> None:
    """Check that everything a run depends on is in place."""
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

    # Read directly rather than through resolve_nodes, so that an empty registry
    # is a line in this report instead of the end of it: the point of a check is
    # to say everything that is wrong at once.
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
    active = enabled_generators(settings.disabled_generators)
    typer.echo(f"generators enabled    {len(active)} of {len(GENERATORS)}")
    if settings.disabled_generators:
        typer.echo(f"disabled              {', '.join(settings.disabled_generators)}")
    typer.echo("")
    typer.echo(f"{'key':24}{'class':12}{'scope':10}{'grading':11}expected")
    for key, spec in GENERATORS.items():
        # The correct behaviour belongs next to the generator: for control
        # items it is not "answer", and that is the main thing to know about
        # them.
        typer.echo(
            f"{key:24}{spec.task_type:12}{spec.scope:10}{spec.grading:11}"
            f"{spec.expected.value}"
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
