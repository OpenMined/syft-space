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

from fastapi import APIRouter, Depends, status

from syft_space.components.benchmarks.handlers import BenchmarkHandler
from syft_space.components.benchmarks.schemas import (
    CheckResponse,
    ConnectionRequest,
    ConnectionResponse,
    ConnectionSettings,
    JobResponse,
    RunRequest,
    TargetRequest,
    TargetResponse,
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
