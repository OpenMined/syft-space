"""Benchmark API routes.

Connections (Settings) say which benchmark and how it reaches this Space;
targets are per endpoint. The rest proxies the benchmark's console and reports.
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
        """Connected benchmarks."""
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
        """Connect a benchmark; the reply includes its self-description."""
        return await handler.connect(tenant, request)

    @router.put("/connections/{connection_id}", response_model=ConnectionResponse)
    async def update_connection(
        connection_id: UUID,
        request: ConnectionRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ConnectionResponse:
        """Update a connection."""
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
        """Replace the connection-wide measurement settings (not a patch)."""
        return await handler.save_settings(tenant, connection_id, settings)

    @router.post(
        "/connections/{connection_id}/check", response_model=ConnectionResponse
    )
    async def check_connection(
        connection_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> ConnectionResponse:
        """Re-check the benchmark's reachability and self-description."""
        return await handler.check_connection(tenant, connection_id)

    @router.delete(
        "/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    async def disconnect(
        connection_id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Remove a connection; endpoints keep their settings."""
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
        """The benchmark's model catalogue, passed through unchanged.

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
        """Have the benchmark refetch its provider's model list."""
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
        """The shared default provider, and the per-role overrides."""
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
        """Set provider URLs per role; keys use ``/provider/credentials/{name}``."""
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
        """Set one provider key; it is never returned, only whether it is set."""
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
        """Clear one provider key; the role falls back to the shared default."""
        return await handler.delete_provider_credential(tenant, connection_id, name)

    # --- per endpoint ------------------------------------------------------

    @router.get("/endpoints/{slug}", response_model=TargetResponse)
    async def get_target(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> TargetResponse:
        """This endpoint's benchmark settings and last job.

        ``measured: false`` means the endpoint is not opted in.
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

    @router.post("/endpoints/{slug}/check", response_model=CheckResponse)
    async def check_target(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> CheckResponse:
        """Check that the benchmark can reach this endpoint and its index."""
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
        """Start a run; 202, the job runs in the background."""
        return await handler.start_run(tenant, slug, request)

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

        ``job`` limits them to one job, rejected ones included.
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

    @router.patch("/endpoints/{slug}/console/pairs/{pair_id}")
    async def update_pair(
        slug: str,
        pair_id: str,
        body: dict,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Set a pair's status by hand: ``{"status": ..., "note": ...}``."""
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
        """Delete a pair; refused once it has been measured."""
        await handler.delete_pair(tenant, slug, pair_id)

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

        ``job`` limits them to one job. ``prompts`` adds the prompts sent to the
        model and judges plus the retrieved chunks; use it with ``qa_id``.
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
                # Empty is dropped by the client; `False` would be sent as "False".
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
        """Add a manual verdict; earlier verdicts are kept."""
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
        """Remove the manual verdict; the judges' verdict applies again."""
        await handler.withdraw_verdict(tenant, slug, result_id)

    @router.post("/endpoints/{slug}/console/report")
    async def build_report(
        slug: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Build the card from the currently graded answers."""
        return await handler.build_report(tenant, slug)

    # --- benchmark results ---------------------------------------------------

    @router.get("/endpoints/{slug}/report/runs")
    async def list_report_runs(
        slug: str,
        date_from: str = Query(default="", alias="from"),
        date_to: str = Query(default="", alias="to"),
        limit: int | None = None,
        offset: int | None = None,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> dict:
        """Runs in progress, and finished runs paged."""
        return await handler.list_report_runs(
            tenant,
            slug,
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

    @router.delete(
        "/endpoints/{slug}/report/runs/{job_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_report_run(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> None:
        """Delete a finished run and its answers; questions stay. 409 while running."""
        await handler.delete_report_run(tenant, slug, job_id)

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

    @router.get("/endpoints/{slug}/report/runs/{job_id}/summary.docx")
    async def download_run_summary(
        slug: str,
        job_id: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: BenchmarkHandler = Depends(get_handler),
    ) -> Response:
        """The run's summary document (.docx)."""
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
        """The run's Excel export, streamed."""
        body, headers = await handler.stream_run_export(tenant, slug, job_id)
        media_type = headers.get("content-type") or (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        passed = {}
        if headers.get("content-disposition"):
            passed["Content-Disposition"] = headers["content-disposition"]
        return StreamingResponse(body, media_type=media_type, headers=passed)

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
        """Cancel a run after its current question; results so far are kept."""
        return await handler.cancel_run(tenant, slug, job_id)

    return router
