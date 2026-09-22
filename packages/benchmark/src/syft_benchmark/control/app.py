"""The control API: targets, settings and launching a measurement.

This is the only door through which the benchmark is driven from outside. Not a
single question and not a single reference answer passes through it — only
targets, settings and job state. The invariant is the same as for publishing:
shares, counters and identifiers leave the perimeter, while text born of
someone else's documents stays inside.

A key is mandatory. The launch route raises work worth hours and money, and an
open port would mean that anyone who reached the network could spend someone
else's budget. Without a key the service still comes up, answers ``/health``
and tells everything else that it is not configured — exactly like a Space with
benchmarks_mode off: not "you may not", but "there is nothing here".
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hmac import compare_digest
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import ValidationError
from sqlalchemy import select

from syft_benchmark.config import (
    ContextMode,
    EvalBlock,
    Settings,
    TextMetric,
    get_settings,
    stored_fields,
)
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.control import targets as registry
from syft_benchmark.control.check import Check, check
from syft_benchmark.control.compose import settings_for
from syft_benchmark.control.formfields import catalogue
from syft_benchmark.control.schemas import (
    Capabilities,
    Instrument,
    JobView,
    ModelCatalogView,
    Probe,
    ProviderInfo,
    RoleProvider,
    RunRequest,
    SecretValue,
    SecretView,
    SettingsDocument,
    TargetSpec,
    TargetView,
)
from syft_benchmark.control.ticker import Ticker
from syft_benchmark.db import store
from syft_benchmark.db.crypto import SecretsNotConfigured
from syft_benchmark.db.models import Job, Target
from syft_benchmark.db.session import session_scope
from syft_benchmark.db.store import SettingRejected
from syft_benchmark.generation import GENERATORS
from syft_benchmark.llm import catalog, judge_providers, subject_providers
from syft_benchmark.llm import openrouter as openrouter_catalogue
from syft_benchmark.llm.catalog import ModelEntry
from syft_benchmark.llm.ollama import installed_models
from syft_benchmark.llm.providers import ProviderKind, kind_for_url

# How many recent jobs to hand back per target. The history is there to show
# that yesterday's measurement failed — and is not needed deeper than a few
# screens.
JOBS_PER_TARGET = 20


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Raise the queue and the schedule, and clean up after the previous launch.

    The cleanup comes first. A job that was running when the process died is
    still in the "running" state, and there is nobody to continue it: without
    the cleanup that is an eternally live measurement in the UI and a queue
    locked on that target forever.
    """
    conf: Settings = app.state.settings
    # Said once, at startup, and never again: which provider keys are being
    # read from the environment in the clear rather than from the sealed store.
    # "It is encrypted at rest" must not be believed about a key that is not.
    store.warn_about_env_secrets(conf)
    closed = job_queue.sweep(conf)
    if closed:
        logger.warning(f"jobs closed that outlived the restart: {closed}")
    with session_scope(conf) as session:
        seeded = registry.seed(session, conf)
    if seeded:
        logger.info(f"targets carried over from the file: {seeded}")
    worker = job_queue.Worker(conf)
    worker.start()
    app.state.worker = worker
    # The schedule is watched by its own thread rather than by the worker: the
    # worker is busy for hours with one measurement, and a schedule looked at
    # only between jobs is looked at exactly when it does not need to be.
    ticker = Ticker(conf)
    ticker.start()
    app.state.ticker = ticker
    try:
        yield
    finally:
        ticker.stop()
        worker.stop()


def authorised(
    request: Request, authorization: Annotated[str, Header()] = ""
) -> Settings:
    """Check the key, and hand back a fresh read of the settings from the database.

    The settings are a row in the database and the API is what edits it: a
    route holding the object assembled at startup would answer /defaults with
    values the owner changed a minute ago and saw accepted.

    The bootstrap half — the key being checked here among it — does come from
    the object the app was built with. It is read from the environment and does
    not change while the process lives.
    """
    conf: Settings = request.app.state.settings
    if not conf.control_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "control is not configured: set BENCH_CONTROL_TOKEN",
        )
    token = authorization.removeprefix("Bearer ").strip()
    # Constant time. An ordinary `!=` returns as soon as two bytes differ, and
    # the time it takes is a measurement of how much of the key is right —
    # enough, over many requests, to find the rest of it a character at a time.
    if not compare_digest(token, conf.control_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "the key did not match")
    return store.apply(conf)


# The alias lives at module level deliberately: the annotations in this file are
# deferred, and declared inside create_app it would not resolve — FastAPI would
# take the settings for a request parameter and answer 422 instead of 401.
Guard = Annotated[Settings, Depends(authorised)]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the control API application."""
    conf = settings or get_settings()
    app = FastAPI(
        title="syft-benchmark control",
        version="1",
        summary="Targets, settings and launching measurements",
        lifespan=lifespan,
    )
    app.state.settings = conf

    if conf.control_origins:
        # The list is empty by default: the UI comes here from its own server,
        # not from a page in a browser, and allowing CORS "just in case" would
        # mean opening the launch of measurements to any open tab.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=conf.control_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- what this service is -----------------------------------------------

    @app.get("/health", summary="Is the service alive")
    def health() -> dict[str, Any]:
        """No key needed: this checks that somebody is at the address at all."""
        return {"service": "syft-benchmark", "control": bool(conf.control_token)}

    @app.get("/capabilities", response_model=Capabilities)
    def capabilities(conf: Guard) -> Capabilities:
        """What this installation can do.

        The list comes from here rather than being hard-wired into the UI:
        otherwise the settings form would offer a generator this installation
        does not have and a model nobody gave it a key for, and that would come
        to light an hour into a run.
        """
        return Capabilities(
            version="1",
            profile=conf.methodology_profile,
            arms=[m.value for m in ContextMode],
            blocks=[b.value for b in EvalBlock],
            generators=sorted(GENERATORS),
            subject_models=[p.model for p in subject_providers(conf)],
            judge_models=[p.model for p in judge_providers(conf)],
            text_metrics=[m.value for m in TextMetric],
            extractive_modes=["auto", "spacy", "llm"],
            external_models=conf.allow_external_models,
            provider=_provider(conf),
        )

    @app.get("/models", response_model=ModelCatalogView)
    def models(
        conf: Guard,
        q: str = "",
        vendor: str = "",
        supports: str = "",
        include_retired: bool = False,
        limit: int = 0,
    ) -> ModelCatalogView:
        """The models a form may offer, filtered as the picker asks.

        Filtered here rather than in the browser: what "supports temperature"
        means is a fact about how the monte_carlo block runs, and a second
        implementation elsewhere would drift from this one.

        Args:
            q: Free text over the identifier and the shown name
            vendor: One vendor only
            supports: Comma-separated request parameters the model must honour
            include_retired: Keep models the provider has dated for withdrawal
            limit: Cap on the answer; zero — everything

        Returns:
            The matching models, the vendors to filter by, the moving names and
            the age of each source.
        """
        needed = tuple(part.strip() for part in supports.split(",") if part.strip())
        catalogue_now = catalog.load(conf)
        found = catalogue_now.search(
            query=q,
            vendor=vendor,
            supports=needed,
            include_retired=include_retired,
        )
        # Asked for live: the list is one request away and always right.
        found = _local_models(conf, query=q, vendor=vendor) + found
        total = len(found)
        return ModelCatalogView(
            models=found[:limit] if limit > 0 else found,
            vendors=catalogue_now.vendors(),
            pins=catalogue_now.pins,
            fetched=catalogue_now.fetched,
            total=total,
        )

    @app.post("/models/refresh", response_model=ModelCatalogView)
    def refresh_models(conf: Guard) -> ModelCatalogView:
        """Fetch the provider's model list afresh and store it.

        An explicit action rather than a schedule: it is a call over the
        perimeter, so it happens when its owner asks for it.

        Raises:
            HTTPException: the perimeter forbids it, or the provider did not
                answer
        """
        from syft_benchmark.config import ExternalCallBlocked, check_model_host

        try:
            check_model_host(openrouter_catalogue.MODELS_URL, conf)
        except ExternalCallBlocked as blocked:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"{blocked}. The catalogue is public, but fetching it is still a "
                f"call outside: add the host to external_hosts, or keep the "
                f"snapshot that ships with the service",
            ) from blocked

        try:
            document = openrouter_catalogue.snapshot()
        except Exception as error:  # noqa: BLE001 — the provider's, not ours
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"the model list could not be fetched: {error}",
            ) from error

        fresh = catalog.replace(document, conf)
        logger.info(
            f"model catalogue refreshed: {len(document.get('models') or [])} models"
        )
        return ModelCatalogView(
            models=fresh.search(),
            vendors=fresh.vendors(),
            pins=fresh.pins,
            fetched=fresh.fetched,
            total=len(fresh.models),
        )

    @app.get("/schema", summary="The shape of the settings fields")
    def form_schema(conf: Guard) -> dict[str, Any]:
        """What a measurement is configured by: names, types, bounds, groups.

        There are no labels here: the wording belongs to whoever displays it,
        and in their reader's language — the same rule by which the card hands
        out codes rather than sentences.
        """
        return catalogue()

    @app.get("/defaults", summary="The installation's effective defaults")
    def defaults(conf: Guard) -> dict[str, Any]:
        """What an unset setting will turn out to be.

        Without this the form would show an empty field where a value is
        actually in force — and the owner would see "not configured" instead of
        "top-5".
        """
        dumped = conf.model_dump(mode="json")
        return {
            "instrument": Instrument(
                arms=conf.arms,
                blocks=conf.blocks,
                denial_rounds=conf.denial_rounds,
                monte_carlo_temperatures=conf.monte_carlo_temperatures,
                monte_carlo_trials=conf.monte_carlo_trials,
                context_source=conf.context_source,
                context_docs=conf.context_docs,
                generator_model=conf.generator_model,
                subject_models=[p.model for p in subject_providers(conf)],
                judge_model=conf.judge_model,
                judge_models=[p.model for p in judge_providers(conf)],
                judge_policy=conf.judge_policy,
                key_facts_threshold=conf.key_facts_threshold,
                answer_coverage_threshold=conf.answer_coverage_threshold,
                consistency_floor=conf.consistency_floor,
                text_metrics=conf.text_metrics,
                extractive_mode=conf.extractive_mode,
                methodology_profile=conf.methodology_profile,
                max_consecutive_failures=conf.max_consecutive_failures,
                reuse_answers=conf.reuse_answers,
                audit_log=conf.audit_log,
            ),
            "probe": Probe(
                dataset_mode=conf.dataset_mode,
                document_window_days=conf.document_window_days,
                dataset_max_pairs=conf.dataset_max_pairs,
                disabled_generators=conf.disabled_generators,
                chunks_per_run=conf.chunks_per_run,
                pairs_per_chunk=conf.pairs_per_chunk,
                min_chunk_chars=conf.min_chunk_chars,
                generate_in_cycle=conf.generate_in_cycle,
                retrieval_top_k=conf.retrieval_top_k,
                similarity_threshold=conf.similarity_threshold,
                endpoint_max_tokens=conf.endpoint_max_tokens,
                endpoint_temperature=conf.endpoint_temperature,
                endpoint_concurrency=conf.endpoint_concurrency,
            ),
            # The bottom layer, after the row has been applied. Asked of the
            # settings rather than listed again — a second list would fall
            # behind on the first field added. No secret can appear: the
            # question "may this be stored" is answered in one place.
            "installation": {field: dumped[field] for field in sorted(stored_fields())},
        }

    # --- the installation's own settings ------------------------------------

    @app.get("/settings", summary="What this installation has overridden")
    def get_settings_doc(conf: Guard) -> dict[str, Any]:
        """Only the overrides, not the effective values.

        The effective ones are what ``/defaults`` answers. Keeping them apart
        matters in the form: "top-5 because nobody changed it" and "top-5
        because somebody chose it" look the same and are not the same, and only
        the second survives a change to the built-in default.
        """
        return {"values": store.read(conf)}

    @app.put("/settings", summary="Replace this installation's overrides")
    def put_settings_doc(doc: SettingsDocument, conf: Guard) -> dict[str, Any]:
        """Write the whole document.

        The values are checked by building the settings with them applied, so a
        bound that only the model knows — a temperature above two, a negative
        window — is refused here rather than at three in the morning when the
        schedule fires.
        """
        try:
            written = store.write(conf, doc.values)
        except SettingRejected as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
            ) from exc
        except ValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, exc.errors(include_url=False)
            ) from exc
        return {"values": written}

    # --- secrets --------------------------------------------------------------
    #
    # They go in and never come out. What can be asked is whether there is one
    # and when it was set — the same thing a target's token has always said.

    @app.get("/credentials", response_model=list[SecretView])
    def list_secrets(conf: Guard) -> list[SecretView]:
        return [
            SecretView(name=item.name, updated_at=item.updated_at)
            for item in store.secrets(conf)
        ]

    @app.put("/credentials/{name}", status_code=status.HTTP_204_NO_CONTENT)
    def put_secret(name: str, body: SecretValue, conf: Guard) -> None:
        """Store one secret, sealed.

        With no master key configured this refuses rather than storing plain
        text. An installation with half its secrets encrypted and no record of
        which half is worse than one that said no.
        """
        if name in store.RESERVED_NAMES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{name!r} is read from the environment and is not stored here",
            )
        try:
            store.set_secret(conf, name, body.value)
        except SecretsNotConfigured as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    @app.delete("/credentials/{name}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_secret(name: str, conf: Guard) -> None:
        if not store.clear_secret(conf, name):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"there is no secret called {name!r}"
            )

    @app.post("/credentials/rotate", summary="Re-seal every secret")
    def rotate_secrets(conf: Guard) -> dict[str, Any]:
        """Move the stored secrets onto the active master key.

        The step in the middle of a rotation: the new key is made active, the
        old one moves to the retired list, this runs, and only then can the old
        key be thrown away. Rows already on the active key are skipped, so an
        interrupted rotation is finished by running it again.
        """
        try:
            return {"resealed": store.rotate(conf)}
        except SecretsNotConfigured as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    # --- targets ------------------------------------------------------------

    @app.get("/targets", response_model=list[TargetView])
    def list_targets(conf: Guard) -> list[TargetView]:
        with session_scope(conf) as session:
            rows = registry.all_targets(session)
            keys = [row.key for row in rows]
            # Which of them have a token, and each one's latest job — in one
            # query apiece rather than one per row.
            with_token = registry.tokens_for(session, keys)
            last_jobs = _last_jobs(session, keys)
            views = [
                registry.view(row, has_token=row.key in with_token) for row in rows
            ]
            for item in views:
                item.last_job = last_jobs.get(item.key)
            return views

    @app.get("/targets/{key}", response_model=TargetView)
    def get_target(key: str, conf: Guard) -> TargetView:
        with session_scope(conf) as session:
            row = _target_or_404(session, key)
            item = registry.view(row, has_token=registry.has_token(session, key))
            item.last_job = _last_job(session, key)
            return item

    @app.put("/targets/{key}", response_model=TargetView)
    def put_target(key: str, spec: TargetSpec, conf: Guard) -> TargetView:
        """Create a target or rewrite it whole.

        PUT rather than PATCH: a target's configuration is a document the owner
        sees on the screen all at once. A partial update would mean that a
        cleared checkbox could not be told from a field that was not sent, and
        clearing it would be impossible.
        """
        if spec.key != key:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"the key in the address ({key}) and in the body ({spec.key}) differ",
            )
        with session_scope(conf) as session:
            try:
                row = registry.save(session, spec, conf)
            except SecretsNotConfigured as exc:
                # A token was sent and there is nowhere to seal it. Refusing is
                # the point: saving the target and silently dropping its access
                # would look like success and fail hours later, in a run.
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)
                ) from exc
            item = registry.view(row, has_token=registry.has_token(session, key))
            item.last_job = _last_job(session, key)
            return item

    @app.delete("/targets/{key}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_target(key: str, conf: Guard) -> None:
        """Remove a target.

        Its measurements stay: they are about the endpoint, not the row.
        """
        with session_scope(conf) as session:
            if not registry.drop(session, key, conf):
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"there is no target {key}"
                )

    @app.post("/targets/{key}/check")
    def check_target(key: str, conf: Guard) -> dict[str, Any]:
        """Walk both roads to the target: to the index and to the node itself."""
        with session_scope(conf) as session:
            row = _target_or_404(session, key)
            node_conf, space = settings_for(row, conf)
        result: Check = check(space, node_conf)
        return {
            "target": result.target,
            "ok": result.ok,
            "corpus": result.corpus,
            "transport": result.transport,
            "collection": result.collection,
            "available": result.available,
            "chunks": result.chunks,
            "usable": result.usable,
            "documents": result.documents,
            "endpoint": result.endpoint,
            "response_type": result.response_type,
            "blocked_arms": result.blocked_arms,
            "problems": result.problems,
        }

    # --- launching ----------------------------------------------------------

    @app.post("/targets/{key}/runs", response_model=JobView, status_code=202)
    def start_run(key: str, request: RunRequest, conf: Guard) -> JobView:
        """Put a measurement in the queue.

        202 rather than 200: the work is accepted but not done — it runs for
        hours. The answer carries the job the work is watched through.
        """
        with session_scope(conf) as session:
            row = _target_or_404(session, key)
            if not row.enabled:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"target {key} is disabled — enable it before measuring",
                )
            job = job_queue.enqueue(session, row, request)
            return JobView.model_validate(job)

    @app.get("/targets/{key}/jobs", response_model=list[JobView])
    def target_jobs(key: str, conf: Guard) -> list[JobView]:
        with session_scope(conf) as session:
            rows = session.scalars(
                select(Job)
                .where(Job.target == key)
                .order_by(Job.created_at.desc())
                .limit(JOBS_PER_TARGET)
            )
            return [JobView.model_validate(row) for row in rows]

    @app.get("/jobs/{job_id}", response_model=JobView)
    def get_job(job_id: str, conf: Guard) -> JobView:
        with session_scope(conf) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"there is no job {job_id}"
                )
            return JobView.model_validate(job)

    @app.post("/jobs/{job_id}/cancel", response_model=JobView)
    def cancel_job(job_id: str, conf: Guard) -> JobView:
        """Ask a job to stop.

        A running one finishes the current question and exits by itself — which
        is why in the response it is still "running". What is done stays in the
        database: half a measurement is data too.
        """
        with session_scope(conf) as session:
            if not job_queue.cancel(session, job_id):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"job {job_id} has already finished, or there is no such job",
                )
            session.flush()
            job = session.get(Job, job_id)
            return JobView.model_validate(job)

    @app.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_job(job_id: str, conf: Guard) -> None:
        """Discard a finished job: its runs and their verdicts, card included.

        Not the question set — `qa_pairs` belongs to the target and is shared
        by every job that ever measured it. A live job is not touched by this
        route at all: stop it first, on its own terms.
        """
        with session_scope(conf) as session:
            outcome = job_queue.delete(session, job_id)
        if outcome == "not_found":
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"there is no job {job_id}")
        if outcome == "not_final":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"job {job_id} is still queued or running — cancel it first",
            )

    return app


def _local_models(conf: Settings, *, query: str, vendor: str) -> list[ModelEntry]:
    """The models this installation has pulled, as catalogue entries.

    A vendor filter excludes them all: a local model has no vendor. An
    unreachable Ollama is a warning and an empty list — the form is for
    configuring things, including while the model host is down.
    """
    if vendor:
        return []
    if kind_for_url(conf.ollama_url) is not ProviderKind.OLLAMA:
        # A gateway has no such route, and asking it costs a doomed request on
        # every draw of the form.
        return []
    try:
        names = installed_models(conf.ollama_url)
    except Exception as error:  # noqa: BLE001 — see the docstring
        logger.warning(f"the local model list could not be read: {error}")
        return []

    needle = query.strip().lower()
    return [
        ModelEntry(id=name, name=name, source="ollama", local=True)
        for name in sorted(names)
        if not needle or needle in name.lower()
    ]


def _provider(conf: Settings) -> ProviderInfo:
    """The model provider, as it can be described without naming the key.

    The key does not leave here, neither by value nor into any storage: the
    benchmark does the computing, the bill goes to the key's owner, and there is
    no reason for a second copy of the secret to live in a service that never
    talks to the provider. What travels outwards is exactly what tells the owner
    what they are being measured with and at whose expense.
    """
    roles = [
        ("generator", conf.generator_url, conf.generator_key),
        ("subject", conf.subject_url, conf.subject_key),
        ("judge", conf.judge_url, conf.judge_key),
    ]
    return ProviderInfo(
        url=conf.ollama_url,
        app_name=conf.llm_app_name,
        key_set=bool(conf.llm_api_key),
        external_hosts=list(conf.external_hosts),
        roles=[
            RoleProvider(
                role=role,
                url=url or conf.ollama_url,
                key_set=bool(key or conf.llm_api_key),
                own=bool(url or key),
            )
            for role, url, key in roles
        ],
    )


def _target_or_404(session: Any, key: str) -> Target:
    row: Target | None = session.get(Target, key)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"there is no target {key}")
    return row


def _last_job(session: Any, key: str) -> JobView | None:
    """The target's latest job — what shows in the list without opening the target."""
    row = session.scalars(
        select(Job).where(Job.target == key).order_by(Job.created_at.desc()).limit(1)
    ).first()
    return JobView.model_validate(row) if row is not None else None


def _last_jobs(session: Any, keys: list[str]) -> dict[str, JobView]:
    """The latest job per target, in one query — for the list view.

    Mirrors ``registry.tokens_for``: a query per row in a list endpoint scales
    with the number of targets, and this page is exactly where that grows.
    """
    if not keys:
        return {}
    rows = session.scalars(
        select(Job)
        .distinct(Job.target)
        .where(Job.target.in_(keys))
        .order_by(Job.target, Job.created_at.desc())
    )
    return {row.target: JobView.model_validate(row) for row in rows}
