"""Benchmark API routes.

Two groups, because the owner does two different things. Connections are set up
once, in Settings — which benchmark, how it reaches this Space, how it measures.
Targets are per endpoint, on the endpoint's own page — measure this one or not,
what differs about it, and go.

None of these are gated on the benchmarks ``mode`` setting. That switch governs whether a
benchmark may *report* about this Space — speak in the owner's name to a
marketplace. Deciding what to measure is the owner speaking to his own service,
and locking it behind the reporting switch would mean he cannot configure
anything until he has already agreed to publish it.

Connecting the first benchmark is the one exception with a side effect on that
switch rather than a gate: it turns reporting on, since only the owner can
reach this route at all. See ``SettingsRepository.enable_benchmarks_if_untouched``.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from syft_space.components.benchmarks.handlers import BenchmarkHandler
from syft_space.components.benchmarks.schemas import (
    CheckResponse,
    ConnectionRequest,
    ConnectionResponse,
    ConnectionSettings,
    JobResponse,
    ProviderCredential,
    ProviderResponse,
    ProviderUrls,
    RunRequest,
    SessionResponse,
    TargetRequest,
    TargetResponse,
    WindowResponse,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_benchmark_routes(handler: BenchmarkHandler) -> APIRouter:
    """Build the benchmark routes."""
    router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

    def get_handler() -> BenchmarkHandler:
        return handler

    # --- connections -------------------------------------------------------

    @router.get("/connections", response_model=list[ConnectionResponse])
    async def list_connections(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> list[ConnectionResponse]:
        """Benchmarks this Space is wired to. Empty is the shipped state."""
        return await handler.list_connections(tenant)

    @router.post(
        "/connections",
        response_model=ConnectionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def connect(
        request: ConnectionRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ConnectionResponse:
        """Wire a benchmark up and ask it what it can do.

        The answer comes back with the connection, so the settings form can be
        drawn immediately — including the case where the benchmark is up but
        has no control key set, which is a different problem from being down.
        """
        return await handler.connect(tenant, request)

    @router.put("/connections/{connection_id}", response_model=ConnectionResponse)
    async def update_connection(
        connection_id: UUID,
        request: ConnectionRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ConnectionResponse:
        """Change where the benchmark is, or how it reaches this Space."""
        return await handler.update_connection(tenant, connection_id, request)

    @router.put(
        "/connections/{connection_id}/settings", response_model=ConnectionResponse
    )
    async def save_settings(
        connection_id: UUID,
        settings: ConnectionSettings,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ConnectionResponse:
        """Store how this benchmark should measure, and tell it.

        Whole, not patched: the form shows the settings as one document, and
        with a patch a cleared field would be indistinguishable from a field
        the form did not send.
        """
        return await handler.save_settings(tenant, connection_id, settings)

    @router.post(
        "/connections/{connection_id}/check", response_model=ConnectionResponse
    )
    async def check_connection(
        connection_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ConnectionResponse:
        """Ask the benchmark again whether it is there and what it offers."""
        return await handler.check_connection(tenant, connection_id)

    @router.delete(
        "/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    async def disconnect(
        connection_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Forget this benchmark. Published cards are untouched — that is a
        separate decision, made per endpoint."""
        await handler.disconnect(tenant, connection_id)

    # --- the model catalogue -----------------------------------------------

    @router.get("/connections/{connection_id}/models")
    async def list_models(
        connection_id: UUID,
        q: str = "",
        vendor: str = "",
        supports: str = "",
        lacks: str = "",
        web_search: str = "",
        include_retired: bool = False,
        limit: int = 0,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """The models this benchmark can be pointed at.

        A route of its own: three hundred models are too many to carry on every
        page load. The answer passes through as the benchmark shaped it — naming
        its fields here is the coupling that leaves a form unable to configure
        something that already works.

        Args:
            q: Free text over the identifier and the shown name
            vendor: One vendor only
            supports: Comma-separated request parameters the model must honour
            lacks: Comma-separated request parameters the model must not take
            web_search: native, plugin, none, or any (native or plugin)
            include_retired: Keep models the provider has dated for withdrawal
            limit: Cap on the answer; zero — everything
        """
        return await handler.models(
            tenant,
            connection_id,
            {
                "q": q,
                "vendor": vendor,
                "supports": supports,
                "lacks": lacks,
                "web_search": web_search,
                "include_retired": include_retired,
                "limit": limit,
            },
        )

    @router.post("/connections/{connection_id}/models/refresh")
    async def refresh_models(
        connection_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Have the benchmark fetch its provider's model list afresh.

        An explicit action of the owner's: on the benchmark's side it is a call
        outside its perimeter, and a refusal reaches the form intact.
        """
        return await handler.refresh_models(tenant, connection_id)

    # --- the model providers -------------------------------------------------

    @router.get(
        "/connections/{connection_id}/provider", response_model=ProviderResponse
    )
    async def get_provider(
        connection_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ProviderResponse:
        """The shared default provider, and the three role overrides."""
        return await handler.get_provider(tenant, connection_id)

    @router.put(
        "/connections/{connection_id}/provider", response_model=ProviderResponse
    )
    async def save_provider(
        connection_id: UUID,
        urls: ProviderUrls,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ProviderResponse:
        """Change where each role's provider is reached. Keys are separate —
        see the ``/provider/credentials/{name}`` routes."""
        return await handler.save_provider(tenant, connection_id, urls)

    @router.put(
        "/connections/{connection_id}/provider/credentials/{name}",
        response_model=ProviderResponse,
    )
    async def save_provider_credential(
        connection_id: UUID,
        name: str,
        credential: ProviderCredential,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ProviderResponse:
        """Set one provider key, sealed on the benchmark's side. It never
        travels back — only whether it is set."""
        return await handler.save_provider_credential(
            tenant, connection_id, name, credential.value
        )

    @router.delete(
        "/connections/{connection_id}/provider/credentials/{name}",
        response_model=ProviderResponse,
    )
    async def delete_provider_credential(
        connection_id: UUID,
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ProviderResponse:
        """Clear one provider key — that role falls back to the shared default."""
        return await handler.delete_provider_credential(tenant, connection_id, name)

    # --- per endpoint ------------------------------------------------------

    @router.get("/endpoints/{slug}", response_model=TargetResponse)
    async def get_target(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> TargetResponse:
        """How this endpoint is measured, and where its last run got to.

        ``measured: false`` means nobody has opted this endpoint in. That is
        not a score of zero and must never be rendered as one.
        """
        return await handler.get_target(tenant, slug)

    @router.put("/endpoints/{slug}", response_model=TargetResponse)
    async def save_target(
        slug: str,
        request: TargetRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> TargetResponse:
        """Start measuring this endpoint, or change how."""
        return await handler.save_target(tenant, slug, request)

    @router.delete("/endpoints/{slug}", status_code=status.HTTP_204_NO_CONTENT)
    async def stop_measuring(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Take this endpoint out of the benchmark, there as well as here."""
        await handler.stop_measuring(tenant, slug)

    @router.post("/endpoints/{slug}/check", response_model=CheckResponse)
    async def check_target(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> CheckResponse:
        """Can the benchmark reach this endpoint's index, and the endpoint itself."""
        return await handler.check_target(tenant, slug)

    @router.get("/endpoints/{slug}/window", response_model=WindowResponse)
    async def get_window(
        slug: str,
        days: int | None = Query(default=None, ge=0),
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> WindowResponse:
        """Articles in the time window; ``days`` overrides the saved window."""
        return await handler.window(tenant, slug, days)

    @router.post(
        "/endpoints/{slug}/runs",
        response_model=JobResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_run(
        slug: str,
        request: RunRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> JobResponse:
        """Measure now. 202: the work is accepted, not done — it takes hours."""
        return await handler.start_run(tenant, slug, request)

    @router.post("/endpoints/{slug}/session", response_model=SessionResponse)
    async def start_console_session(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> SessionResponse:
        """Open the benchmark's own standalone console for this endpoint.

        The routes below reach the same console API and return its data
        directly, for this Space's own embedded view; this one instead
        hands back a link, scoped to this one endpoint and good for an
        hour, for opening the benchmark's console on its own.
        """
        return await handler.start_console_session(tenant, slug)

    # --- the console, embedded: pairs, results, filtering, judging, report --

    @router.get("/endpoints/{slug}/console/pairs")
    async def list_pairs(
        slug: str,
        pair_status: str = Query(default="", alias="status"),
        cohort: str = "",
        generator: str = "",
        job: str = "",
        limit: int = 0,
        offset: int = 0,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """This endpoint's question/answer pairs, filterable and paged.

        ``job`` narrows them to one launch — what that run generated, rejected
        ones included. It is how a run's own page is drawn.
        """
        return await handler.list_pairs(
            tenant,
            slug,
            {
                "status": pair_status,
                "cohort": cohort,
                "generator": generator,
                "job": job,
                "limit": limit,
                "offset": offset,
            },
        )

    @router.get("/endpoints/{slug}/console/pairs/{pair_id}")
    async def get_pair(
        slug: str,
        pair_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """One pair in full — question, answer, context, status."""
        return await handler.get_pair(tenant, slug, pair_id)

    @router.patch("/endpoints/{slug}/console/pairs/{pair_id}")
    async def update_pair(
        slug: str,
        pair_id: str,
        body: dict,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Override a pair's status by hand — ``{"status": ..., "note": ...}``."""
        return await handler.update_pair(tenant, slug, pair_id, body)

    @router.delete(
        "/endpoints/{slug}/console/pairs/{pair_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_pair(
        slug: str,
        pair_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Remove a pair outright — refused if anything has measured it yet."""
        await handler.delete_pair(tenant, slug, pair_id)

    @router.post(
        "/endpoints/{slug}/console/filter", status_code=status.HTTP_202_ACCEPTED
    )
    async def run_filter(
        slug: str,
        body: dict,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Screen this endpoint's pending pairs, on their own, in one job."""
        return await handler.run_filter(tenant, slug, body)

    @router.get("/endpoints/{slug}/console/results")
    async def list_results(
        slug: str,
        verdict: str = "",
        qa_id: str = "",
        job: str = "",
        limit: int = 0,
        offset: int = 0,
        prompts: bool = False,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """This endpoint's graded answers, filterable and paged.

        ``job`` narrows them to one launch — what that run asked and what came
        back. ``prompts`` adds what was actually sent to the answering model
        and to each judge, together with the chunks retrieval found; it is
        heavy enough that the benchmark keeps it off by default, so it is
        asked for one question at a time, with ``qa_id``.
        """
        return await handler.list_results(
            tenant,
            slug,
            {
                "verdict": verdict,
                "qa_id": qa_id,
                "job": job,
                "limit": limit,
                "offset": offset,
                # Sent only when it is wanted: the console client drops empty
                # values, and a literal `False` would travel as "False".
                "prompts": "true" if prompts else "",
            },
        )

    @router.post("/endpoints/{slug}/console/results/{result_id}/verdict")
    async def override_verdict(
        slug: str,
        result_id: str,
        body: dict,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Record a verdict by hand — inserted, never a rewrite of the last one."""
        return await handler.override_verdict(tenant, slug, result_id, body)

    @router.delete(
        "/endpoints/{slug}/console/results/{result_id}/verdict",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def withdraw_verdict(
        slug: str,
        result_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Take back a verdict recorded by hand — the panel's stands again."""
        await handler.withdraw_verdict(tenant, slug, result_id)

    @router.post(
        "/endpoints/{slug}/console/judge", status_code=status.HTTP_202_ACCEPTED
    )
    async def run_judge(
        slug: str,
        body: dict,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Grade this endpoint's pending verdicts, on their own, in one job."""
        return await handler.run_judge(tenant, slug, body)

    @router.post("/endpoints/{slug}/console/report")
    async def build_report(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Rebuild the card from what is active and graded right now."""
        return await handler.build_report(tenant, slug)

    @router.post("/endpoints/{slug}/console/publish")
    async def publish_report(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Hand the current card to the Space, from the endpoint's own review."""
        return await handler.publish_report(tenant, slug)

    @router.post(
        "/endpoints/{slug}/console/retract", status_code=status.HTTP_204_NO_CONTENT
    )
    async def retract_report(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Take the published card back."""
        await handler.retract_report(tenant, slug)

    # --- benchmark results ---------------------------------------------------

    @router.get("/endpoints/{slug}/report/runs")
    async def list_report_runs(
        slug: str,
        run_status: str = Query(default="all", alias="status"),
        date_from: str = Query(default="", alias="from"),
        date_to: str = Query(default="", alias="to"),
        limit: int | None = None,
        offset: int | None = None,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Runs in progress, and finished runs paged, each marked ``published``
        with its ``card_id``. ``status``: ``all``, ``published`` or ``private``."""
        return await handler.list_report_runs(
            tenant,
            slug,
            run_status,
            {"from": date_from, "to": date_to, "limit": limit, "offset": offset},
        )

    @router.get("/endpoints/{slug}/report/runs/{job_id}")
    async def get_report_run(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """One run's report, without per-question rows."""
        return await handler.get_report_run(tenant, slug, job_id)

    @router.get("/endpoints/{slug}/report/runs/{job_id}/questions")
    async def list_run_questions(
        slug: str,
        job_id: str,
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """One run's questions for one model, paged. Query passed through."""
        return await handler.list_run_questions(
            tenant, slug, job_id, dict(request.query_params)
        )

    @router.get("/endpoints/{slug}/report/runs/{job_id}/generated")
    async def list_run_generated(
        slug: str,
        job_id: str,
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """The questions the run wrote, paged, and its build per kind. Query
        passed through (``generator``, ``status``, ``limit``, ``offset``)."""
        return await handler.list_run_part(
            tenant, slug, job_id, "generated", dict(request.query_params)
        )

    @router.get("/endpoints/{slug}/report/runs/{job_id}/filter")
    async def list_run_filter(
        slug: str,
        job_id: str,
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """The run's filter decisions, paged. Query passed through
        (``stage``, ``outcome``, ``limit``, ``offset``)."""
        return await handler.list_run_part(
            tenant, slug, job_id, "filter", dict(request.query_params)
        )

    @router.get("/endpoints/{slug}/report/runs/{job_id}/questions/{qa_id}")
    async def get_run_question(
        slug: str,
        job_id: str,
        qa_id: str,
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """One question of a run in full. Query passed through (``model``)."""
        return await handler.get_run_question(
            tenant, slug, job_id, qa_id, dict(request.query_params)
        )

    @router.get("/endpoints/{slug}/report/runs/{job_id}/questions/{qa_id}/fragments")
    async def get_run_question_fragments(
        slug: str,
        job_id: str,
        qa_id: str,
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> list:
        """The passages sent with the with-data answer."""
        return await handler.get_run_question_fragments(
            tenant, slug, job_id, qa_id, dict(request.query_params)
        )

    @router.put("/endpoints/{slug}/report/runs/{job_id}/questions/{qa_id}/exclusion")
    async def exclude_run_question(
        slug: str,
        job_id: str,
        qa_id: str,
        body: dict,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Leave a question out of this run's figures —
        ``{"reason": ..., "retire": bool}``."""
        return await handler.exclude_run_question(tenant, slug, job_id, qa_id, body)

    @router.delete(
        "/endpoints/{slug}/report/runs/{job_id}/questions/{qa_id}/exclusion",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def restore_run_question(
        slug: str,
        job_id: str,
        qa_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Count an excluded question again."""
        await handler.restore_run_question(tenant, slug, job_id, qa_id)

    @router.get("/endpoints/{slug}/report/runs/{job_id}/summary.docx")
    async def download_run_summary(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> Response:
        """The run's summary document, as the benchmark names and types it."""
        content, headers = await handler.download_run_summary(tenant, slug, job_id)
        media_type = headers.get("content-type") or (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        passed = {}
        if headers.get("content-disposition"):
            passed["Content-Disposition"] = headers["content-disposition"]
        return Response(content=content, media_type=media_type, headers=passed)

    @router.get("/endpoints/{slug}/report/runs/{job_id}/export.xlsx")
    async def stream_run_export(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> StreamingResponse:
        """Everything that took part in the run as one workbook, streamed as
        the benchmark sends it."""
        body, headers = await handler.stream_run_export(tenant, slug, job_id)
        media_type = headers.get("content-type") or (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        passed = {}
        if headers.get("content-disposition"):
            passed["Content-Disposition"] = headers["content-disposition"]
        return StreamingResponse(body, media_type=media_type, headers=passed)

    @router.post("/endpoints/{slug}/report/runs/{job_id}/publish")
    async def publish_run(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Publish this run's card, whatever the run's age. Newer cards are
        withdrawn. ``refused`` lists marketplaces that did not take it."""
        return await handler.publish_run(tenant, slug, job_id)

    @router.post("/endpoints/{slug}/report/runs/{job_id}/unpublish")
    async def unpublish_run(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Withdraw the published card. 409 unless it is this run's."""
        return await handler.unpublish_run(tenant, slug, job_id)

    @router.get("/endpoints/{slug}/jobs", response_model=list[JobResponse])
    async def list_jobs(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> list[JobResponse]:
        """Runs of this endpoint, newest first."""
        return await handler.list_jobs(tenant, slug)

    @router.post("/endpoints/{slug}/jobs/{job_id}/cancel", response_model=JobResponse)
    async def cancel_run(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> JobResponse:
        """Ask a run to stop. It finishes the question in hand and comes out —
        what it measured so far stays measured."""
        return await handler.cancel_run(tenant, slug, job_id)

    @router.delete(
        "/endpoints/{slug}/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    async def delete_job(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Discard a finished run — its passes, its verdicts, its card."""
        await handler.delete_job(tenant, slug, job_id)

    return router
