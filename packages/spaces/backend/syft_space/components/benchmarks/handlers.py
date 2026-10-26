"""Benchmark connections, per-endpoint targets, runs and the console proxy.

The Space stores the owner's settings and pushes them to the benchmark, which
keeps its own copy so scheduled runs work while the Space is down. The push is
best effort: a benchmark that is down does not block saving. Measurement
settings (judges, arms, thresholds) are passed through unparsed.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar
from urllib.parse import quote
from uuid import UUID

from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError

from syft_space.components.benchmarks.client import BenchmarkClient, Reply, Snapshot
from syft_space.components.benchmarks.entities import (
    BenchmarkConnection,
    BenchmarkTarget,
)
from syft_space.components.benchmarks.repository import (
    BenchmarkConnectionRepository,
    BenchmarkTargetRepository,
)
from syft_space.components.benchmarks.schemas import (
    CheckResponse,
    ConnectionRequest,
    ConnectionResponse,
    ConnectionSettings,
    JobResponse,
    ProviderResponse,
    ProviderRole,
    ProviderUrls,
    RunRequest,
    TargetRequest,
    TargetResponse,
    WindowResponse,
)
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.tenants.entities import Tenant

# How long a cached benchmark self-description (settings schema) is used.
SNAPSHOT_MAX_AGE = timedelta(hours=1)

# Provider key names the benchmark accepts (its `config.py`); checked here so a
# wrong name is a clear 404 rather than the benchmark's 422.
PROVIDER_KEY_NAMES = frozenset(
    {"llm_api_key", "generator_key", "subject_key", "judge_key", "filter_key"}
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _parsed(model: type[ModelT], data: Any) -> ModelT:
    """Validate the benchmark's reply; a shape mismatch is a 502."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"benchmark sent an unreadable {model.__name__}: {exc}",
        ) from exc


def _console_dict(reply: Reply) -> dict[str, Any]:
    """A console call's JSON body, or the refusal that stands in for it."""
    if not reply.ok:
        raise HTTPException(
            status_code=reply.status if reply.status >= 400 else 502,
            detail=reply.detail or "the benchmark's console did not answer",
        )
    return reply.data if isinstance(reply.data, dict) else {}


def _console_empty(reply: Reply) -> None:
    """A console call with nothing to return — a delete."""
    if not reply.ok:
        raise HTTPException(
            status_code=reply.status if reply.status >= 400 else 502,
            detail=reply.detail or "the benchmark's console did not answer",
        )


def _seg(value: str) -> str:
    """One path segment, escaped."""
    return quote(value, safe="")


class BenchmarkHandler:
    """Everything the benchmark pages do."""

    def __init__(
        self,
        connection_repository: BenchmarkConnectionRepository,
        target_repository: BenchmarkTargetRepository,
        endpoint_repository: EndpointRepository,
        dataset_repository: DatasetRepository,
        dataset_registry: Any,
        settings_repository: SettingsRepository | None = None,
    ) -> None:
        self.connections = connection_repository
        self.targets = target_repository
        self.endpoints = endpoint_repository
        self.datasets = dataset_repository
        self.dataset_registry = dataset_registry
        self.settings = settings_repository

    # --- connections -------------------------------------------------------

    async def list_connections(self, tenant: Tenant) -> list[ConnectionResponse]:
        """Connected benchmarks; stale self-descriptions are refreshed."""
        rows = await self.connections.list_for_tenant(tenant.id)
        rows = list(await asyncio.gather(*(self._if_stale(row) for row in rows)))
        out = []
        for row in rows:
            used = await self.targets.count_for_connection(row.id)
            out.append(self._connection_view(row, endpoints=used))
        return out

    async def connect(
        self, tenant: Tenant, request: ConnectionRequest
    ) -> ConnectionResponse:
        """Connect a benchmark and fetch its self-description.

        The first connection becomes the default.
        """
        existing = await self.connections.list_for_tenant(tenant.id)
        row = BenchmarkConnection(
            tenant_id=tenant.id,
            name=request.name,
            url=request.url,
            token=request.token or "",
            space_url=request.space_url or await self._own_url(),
            chroma_host=request.chroma_host,
            chroma_port=request.chroma_port,
            container=request.container,
            is_default=request.is_default or not existing,
            is_active=request.is_active,
        )
        row = await self.connections.create(row)
        if row.is_default:
            await self.connections.clear_default(tenant.id, keep=row.id)
        row = await self._refresh(row)
        return self._connection_view(row)

    async def update_connection(
        self, tenant: Tenant, connection_id: UUID, request: ConnectionRequest
    ) -> ConnectionResponse:
        row = await self._connection_or_404(tenant, connection_id)
        row.name = request.name
        row.url = request.url
        # The form never receives the token; an omitted token keeps the stored one.
        if request.token is not None:
            row.token = request.token
        row.space_url = request.space_url
        row.chroma_host = request.chroma_host
        row.chroma_port = request.chroma_port
        row.container = request.container
        row.is_default = request.is_default
        row.is_active = request.is_active
        row.updated_at = datetime.now(timezone.utc)
        row = await self.connections.update(row)
        if row.is_default:
            await self.connections.clear_default(tenant.id, keep=row.id)
        row = await self._refresh(row)
        # Targets carry connection details, so re-push them all.
        await self._resync(tenant, row)
        return self._connection_view(row)

    async def save_settings(
        self, tenant: Tenant, connection_id: UUID, settings: ConnectionSettings
    ) -> ConnectionResponse:
        """Store connection-wide settings and re-push every target that carries them."""
        row = await self._connection_or_404(tenant, connection_id)
        row.instrument = settings.instrument or None
        row.probe = settings.probe or None
        row.updated_at = datetime.now(timezone.utc)
        row = await self.connections.update(row)
        await self._resync(tenant, row)
        return self._connection_view(row)

    async def check_connection(
        self, tenant: Tenant, connection_id: UUID
    ) -> ConnectionResponse:
        row = await self._connection_or_404(tenant, connection_id)
        row = await self._refresh(row)
        return self._connection_view(row)

    async def disconnect(self, tenant: Tenant, connection_id: UUID) -> None:
        """Remove a connection; its targets keep their settings."""
        row = await self._connection_or_404(tenant, connection_id)
        await self.connections.delete(row.id)

    # --- the model catalogue -----------------------------------------------

    async def models(
        self, tenant: Tenant, connection_id: UUID, query: dict[str, Any]
    ) -> dict[str, Any]:
        """The benchmark's model catalogue, passed through unchanged."""
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).models(query)
        if not reply.ok:
            raise HTTPException(
                status_code=502,
                detail=reply.detail or "the benchmark did not hand over its models",
            )
        return reply.data or {}

    async def refresh_models(
        self, tenant: Tenant, connection_id: UUID
    ) -> dict[str, Any]:
        """Have the benchmark refetch its provider's model list.

        A refusal keeps its status (e.g. 403 naming the host to allow).
        """
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).refresh_models()
        if not reply.ok:
            raise HTTPException(
                status_code=reply.status if reply.status >= 400 else 502,
                detail=reply.detail or "the benchmark could not refresh its models",
            )
        return reply.data or {}

    # --- the model providers -------------------------------------------------
    #
    # Provider URLs and keys are benchmark-wide, shared by every Space using it.

    async def get_provider(
        self, tenant: Tenant, connection_id: UUID
    ) -> ProviderResponse:
        row = await self._connection_or_404(tenant, connection_id)
        client = self._client(row)
        settings_reply = await client.get_settings()
        if not settings_reply.ok:
            raise HTTPException(
                status_code=502,
                detail=settings_reply.detail or "the benchmark would not say",
            )
        values = (settings_reply.data or {}).get("values", {})
        defaults = row.defaults or {}
        secrets_reply = await client.list_credentials()
        updated: dict[str, datetime] = {}
        if secrets_reply.ok:
            for item in secrets_reply.data or []:
                updated[item["name"]] = item["updated_at"]

        def role(url_field: str, key_field: str) -> ProviderRole:
            return ProviderRole(
                url=values.get(url_field, "") or "",
                url_default=defaults.get(url_field, "") or "",
                key_set=key_field in updated,
                key_updated_at=updated.get(key_field),
            )

        return ProviderResponse(
            shared=role("ollama_url", "llm_api_key"),
            generator=role("generator_url", "generator_key"),
            subject=role("subject_url", "subject_key"),
            judge=role("judge_url", "judge_key"),
            filter=role("filter_url", "filter_key"),
        )

    async def save_provider(
        self, tenant: Tenant, connection_id: UUID, urls: ProviderUrls
    ) -> ProviderResponse:
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).put_settings(urls.model_dump())
        if not reply.ok:
            raise HTTPException(
                status_code=reply.status if reply.status >= 400 else 502,
                detail=reply.detail or "the benchmark refused those addresses",
            )
        return await self.get_provider(tenant, connection_id)

    async def save_provider_credential(
        self, tenant: Tenant, connection_id: UUID, name: str, value: str
    ) -> ProviderResponse:
        if name not in PROVIDER_KEY_NAMES:
            raise HTTPException(
                status_code=404, detail=f"{name!r} is not a provider key"
            )
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).put_credential(name, value)
        if not reply.ok:
            raise HTTPException(
                status_code=reply.status if reply.status >= 400 else 502,
                detail=reply.detail or "the benchmark refused that key",
            )
        return await self.get_provider(tenant, connection_id)

    async def delete_provider_credential(
        self, tenant: Tenant, connection_id: UUID, name: str
    ) -> ProviderResponse:
        if name not in PROVIDER_KEY_NAMES:
            raise HTTPException(
                status_code=404, detail=f"{name!r} is not a provider key"
            )
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).delete_credential(name)
        if not reply.ok:
            raise HTTPException(
                status_code=reply.status if reply.status >= 400 else 502,
                detail=reply.detail or "the benchmark could not clear that key",
            )
        return await self.get_provider(tenant, connection_id)

    # --- targets -----------------------------------------------------------

    async def get_target(self, tenant: Tenant, slug: str) -> TargetResponse:
        endpoint = await self._endpoint_or_404(tenant, slug)
        target = await self.targets.for_endpoint(endpoint.id)
        connection = await self._connection_for(tenant, target)
        if connection is not None:
            connection = await self._if_stale(connection)

        out = TargetResponse(
            endpoint_slug=slug,
            measured=target is not None,
            resolved_collection=await self._collection_for(tenant, endpoint),
        )
        if connection is not None:
            out.connection_id = connection.id
            out.connection_name = connection.name
            out.fields = connection.fields or {}
            out.defaults = connection.defaults or {}
            out.connection_probe = connection.probe or {}
            out.connection_instrument = connection.instrument or {}
            out.capabilities = connection.capabilities or {}
            out.reachable = connection.reachable
            out.detail = connection.detail
        if target is None:
            return out

        out.enabled = target.enabled
        out.collection = target.collection
        out.probe = target.probe or {}
        out.instrument = target.instrument or {}
        out.schedule = target.schedule
        out.schedule_at = target.schedule_at
        out.synced_at = target.synced_at
        out.last_job, out.next_run_at = await asyncio.gather(
            self._latest_job(target, connection, slug),
            self._next_run_at(connection, slug),
        )
        return out

    async def save_target(
        self, tenant: Tenant, slug: str, request: TargetRequest
    ) -> TargetResponse:
        """Start measuring this endpoint, or change how."""
        endpoint = await self._endpoint_or_404(tenant, slug)
        connection = await self._pick_connection(tenant, request.connection_id)

        # Pushed before storing, so a configuration the benchmark refuses is not kept.
        spec = await self._spec(
            tenant,
            connection,
            endpoint,
            collection=request.collection,
            instrument=request.instrument,
            probe=request.probe,
            enabled=request.enabled,
            schedule=request.schedule,
            schedule_at=request.schedule_at,
        )
        reply = await self._client(connection).put_target(endpoint.slug, spec)
        _raise_if_refused(reply)

        def apply(target: BenchmarkTarget) -> BenchmarkTarget:
            target.connection_id = connection.id
            target.enabled = request.enabled
            target.collection = request.collection
            target.probe = request.probe or None
            target.instrument = request.instrument or None
            target.schedule = request.schedule
            target.schedule_at = request.schedule_at
            target.updated_at = datetime.now(timezone.utc)
            return target

        existing = await self.targets.for_endpoint(endpoint.id)
        if existing is not None:
            target = await self.targets.update(apply(existing))
        else:
            new_target = apply(
                BenchmarkTarget(tenant_id=tenant.id, endpoint_id=endpoint.id)
            )
            try:
                target = await self.targets.create(new_target)
            except IntegrityError:
                # A concurrent save created the row first; update it.
                existing = await self.targets.for_endpoint(endpoint.id)
                assert existing is not None
                target = await self.targets.update(apply(existing))

        await self._synced(target, endpoint, reply)
        return await self.get_target(tenant, slug)

    async def check_target(self, tenant: Tenant, slug: str) -> CheckResponse:
        """Ask the benchmark whether it can actually reach this endpoint."""
        endpoint = await self._endpoint_or_404(tenant, slug)
        target, connection = await self._pair_or_404(tenant, endpoint, slug)
        # Push first so the check uses the current settings.
        await self._push(tenant, connection, target, endpoint)
        reply = await self._client(connection).check_target(slug)
        if not reply.ok:
            return CheckResponse(
                problems=[reply.detail or "benchmark is not answering"]
            )
        return _parsed(CheckResponse, reply.data)

    async def window(
        self, tenant: Tenant, slug: str, days: int | None = None
    ) -> WindowResponse:
        """How many articles the endpoint's time window holds."""
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        reply = await self._client(connection).window(slug, days)
        if not reply.ok:
            raise HTTPException(
                status_code=502,
                detail=reply.detail or "the benchmark could not count the articles",
            )
        return _parsed(WindowResponse, reply.data)

    # --- runs --------------------------------------------------------------

    async def start_run(
        self, tenant: Tenant, slug: str, request: RunRequest
    ) -> JobResponse:
        endpoint = await self._endpoint_or_404(tenant, slug)
        target, connection = await self._pair_or_404(tenant, endpoint, slug)
        if not target.enabled:
            raise HTTPException(
                status_code=409,
                detail="Measuring is paused for this endpoint",
            )
        _raise_if_refused(await self._push(tenant, connection, target, endpoint))
        reply = await self._client(connection).start_run(
            slug, request.model_dump(exclude_none=True)
        )
        _raise_if_refused(reply)
        if not reply.ok:
            raise HTTPException(
                status_code=502,
                detail=reply.detail or "the benchmark did not take the run",
            )
        job = _parsed(JobResponse, reply.data)
        await self.targets.remember_job(target.id, job.model_dump(mode="json"))
        return job

    async def _console(
        self, connection: BenchmarkConnection, target_key: str
    ) -> BenchmarkClient:
        """A client with a fresh session token scoped to one target."""
        reply = await self._client(connection).mint_session(target_key)
        token = reply.data.get("token") if isinstance(reply.data, dict) else None
        if not reply.ok or not token:
            raise HTTPException(
                status_code=502,
                detail=reply.detail or "the benchmark would not open a console session",
            )
        return self._console_client(connection, token)

    # --- the console: pairs, results, filtering, judging, the report -------
    #
    # Proxied to the benchmark's console API with a session token; replies are
    # passed through unchanged.

    async def list_pairs(
        self, tenant: Tenant, slug: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        console = await self._console(connection, slug)
        return _console_dict(await console.raw("GET", "/console/pairs", params=query))

    async def update_pair(
        self, tenant: Tenant, slug: str, pair_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        console = await self._console(connection, slug)
        reply = await console.raw("PATCH", f"/console/pairs/{pair_id}", body=body)
        return _console_dict(reply)

    async def delete_pair(self, tenant: Tenant, slug: str, pair_id: str) -> None:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        console = await self._console(connection, slug)
        _console_empty(await console.raw("DELETE", f"/console/pairs/{pair_id}"))

    async def list_results(
        self, tenant: Tenant, slug: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        console = await self._console(connection, slug)
        return _console_dict(await console.raw("GET", "/console/results", params=query))

    async def override_verdict(
        self, tenant: Tenant, slug: str, result_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        console = await self._console(connection, slug)
        reply = await console.raw(
            "POST", f"/console/results/{result_id}/verdict", body=body
        )
        return _console_dict(reply)

    async def withdraw_verdict(self, tenant: Tenant, slug: str, result_id: str) -> None:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        console = await self._console(connection, slug)
        await console.raw("DELETE", f"/console/results/{result_id}/verdict")

    async def build_report(self, tenant: Tenant, slug: str) -> dict[str, Any]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        console = await self._console(connection, slug)
        return _console_dict(await console.raw("POST", "/console/report"))

    # --- benchmark results: runs and their reports ---------------------------

    async def list_report_runs(
        self, tenant: Tenant, slug: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        _, console = await self._report_console(tenant, slug)
        return _console_dict(
            await console.raw("GET", "/console/report/runs", params=dict(query))
        )

    async def get_report_run(
        self, tenant: Tenant, slug: str, job_id: str
    ) -> dict[str, Any]:
        _, console = await self._report_console(tenant, slug)
        return _console_dict(
            await console.raw("GET", f"/console/report/runs/{_seg(job_id)}")
        )

    async def list_run_questions(
        self, tenant: Tenant, slug: str, job_id: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        _, console = await self._report_console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/questions"
        return _console_dict(await console.raw("GET", path, params=query))

    async def list_run_part(
        self, tenant: Tenant, slug: str, job_id: str, part: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        """A run's ``generated`` or ``filter`` list, passed through."""
        _, console = await self._report_console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/{part}"
        return _console_dict(await console.raw("GET", path, params=query))

    async def get_run_question(
        self, tenant: Tenant, slug: str, job_id: str, qa_id: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        _, console = await self._report_console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/questions/{_seg(qa_id)}"
        return _console_dict(await console.raw("GET", path, params=query))

    async def get_run_question_fragments(
        self, tenant: Tenant, slug: str, job_id: str, qa_id: str, query: dict[str, Any]
    ) -> list[Any]:
        _, console = await self._report_console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/questions/{_seg(qa_id)}/fragments"
        reply = await console.raw("GET", path, params=query)
        _console_empty(reply)
        return reply.data if isinstance(reply.data, list) else []

    async def delete_report_run(self, tenant: Tenant, slug: str, job_id: str) -> None:
        """Delete a finished run; the benchmark keeps its questions."""
        _, console = await self._report_console(tenant, slug)
        _console_empty(
            await console.raw("DELETE", f"/console/report/runs/{_seg(job_id)}")
        )

    async def download_run_summary(
        self, tenant: Tenant, slug: str, job_id: str
    ) -> tuple[bytes, dict[str, str]]:
        """The run's summary document and the headers it came with."""
        _, console = await self._report_console(tenant, slug)
        reply = await console.download(
            f"/console/report/runs/{_seg(job_id)}/summary.docx"
        )
        _console_empty(reply)
        return reply.data or b"", reply.headers

    async def stream_run_export(
        self, tenant: Tenant, slug: str, job_id: str
    ) -> tuple[AsyncIterator[bytes], dict[str, str]]:
        """The run's Excel export as it arrives, and the headers it came with."""
        _, console = await self._report_console(tenant, slug)
        reply, body = await console.stream(
            f"/console/report/runs/{_seg(job_id)}/export.xlsx"
        )
        _console_empty(reply)
        if body is None:
            raise HTTPException(status_code=502, detail="the export came back empty")
        return body, reply.headers

    async def _report_console(
        self, tenant: Tenant, slug: str
    ) -> tuple[Endpoint, BenchmarkClient]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        return endpoint, await self._console(connection, slug)

    async def list_jobs(self, tenant: Tenant, slug: str) -> list[JobResponse]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        target = await self.targets.for_endpoint(endpoint.id)
        connection = await self._connection_for(tenant, target)
        if target is None or connection is None:
            return []
        reply = await self._client(connection).jobs(slug)
        if not reply.ok:
            # Benchmark unreachable: show the last remembered job.
            return [_parsed(JobResponse, target.last_job)] if target.last_job else []
        jobs = [_parsed(JobResponse, item) for item in reply.data or []]
        # An empty list clears the remembered job too.
        await self.targets.remember_job(
            target.id, jobs[0].model_dump(mode="json") if jobs else None
        )
        return jobs

    async def cancel_run(self, tenant: Tenant, slug: str, job_id: str) -> JobResponse:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        reply = await self._client(connection).cancel(job_id)
        if not reply.ok:
            raise HTTPException(
                status_code=502, detail=reply.detail or "the run could not be stopped"
            )
        return _parsed(JobResponse, reply.data)

    # --- inside ------------------------------------------------------------

    def _client(self, connection: BenchmarkConnection) -> BenchmarkClient:
        return BenchmarkClient(connection.url, connection.token)

    def _console_client(
        self, connection: BenchmarkConnection, token: str
    ) -> BenchmarkClient:
        """A client carrying a console session token."""
        return BenchmarkClient(connection.url, token)

    async def _if_stale(self, row: BenchmarkConnection) -> BenchmarkConnection:
        """Refresh an expired self-description; on failure return the row unchanged."""
        if row.checked_at is not None:
            # SQLite returns naive datetimes; they are stored in UTC.
            seen = row.checked_at
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - seen < SNAPSHOT_MAX_AGE:
                return row
        try:
            return await self._refresh(row)
        except Exception as error:  # noqa: BLE001 — see the docstring
            logger.warning(
                f"benchmark {row.url}: could not be asked about itself: {error}"
            )
            return row

    async def _refresh(self, row: BenchmarkConnection) -> BenchmarkConnection:
        """Ask the benchmark about itself and remember the answer."""
        snapshot: Snapshot = await self._client(row).snapshot()
        row.reachable = snapshot.reachable
        row.detail = snapshot.detail
        row.checked_at = datetime.now(timezone.utc)
        if snapshot.capabilities:
            row.capabilities = snapshot.capabilities
        if snapshot.fields:
            row.fields = snapshot.fields
        if snapshot.defaults:
            row.defaults = snapshot.defaults
        return await self.connections.update(row)

    def _connection_view(
        self, row: BenchmarkConnection, endpoints: int = 0
    ) -> ConnectionResponse:
        return ConnectionResponse(
            id=row.id,
            name=row.name,
            url=row.url,
            has_token=bool(row.token),
            space_url=row.space_url,
            chroma_host=row.chroma_host,
            chroma_port=row.chroma_port,
            container=row.container,
            instrument=row.instrument or {},
            probe=row.probe or {},
            reachable=row.reachable,
            detail=row.detail,
            checked_at=row.checked_at,
            capabilities=row.capabilities or {},
            fields=row.fields or {},
            defaults=row.defaults or {},
            is_default=row.is_default,
            is_active=row.is_active,
            endpoints=endpoints,
        )

    async def _own_url(self) -> str:
        """This Space's public URL, or empty."""
        if self.settings is None:
            return ""
        try:
            return await self.settings.get_public_url() or ""
        except Exception:  # noqa: BLE001 - an address we do not know is simply blank
            return ""

    async def _collection_for(self, tenant: Tenant, endpoint: Endpoint) -> str:
        """The endpoint's index collection name, resolved from its dataset."""
        if not endpoint.dataset_id:
            return ""
        try:
            dataset = await self.datasets.get_by_id(endpoint.dataset_id, tenant.id)
            if dataset is None:
                return ""
            dataset_type = self.dataset_registry.get_dataset_type(dataset.dtype)
            instance = dataset_type(dataset.configuration)
            return str(getattr(instance, "collection_name", "") or "")
        except Exception as exc:  # noqa: BLE001 - a name we cannot resolve is blank
            logger.debug(f"collection for {endpoint.slug} not resolved: {exc}")
            return ""

    async def _push(
        self,
        tenant: Tenant,
        connection: BenchmarkConnection,
        target: BenchmarkTarget,
        endpoint: Endpoint,
    ) -> Reply:
        """Push this target's settings to the benchmark, best effort.

        ``synced_at`` records success; a refusal is returned for the caller.
        """
        spec = await self._spec(
            tenant,
            connection,
            endpoint,
            collection=target.collection,
            instrument=target.instrument or {},
            probe=target.probe or {},
            enabled=target.enabled,
            schedule=target.schedule,
            schedule_at=target.schedule_at,
        )
        reply = await self._client(connection).put_target(endpoint.slug, spec)
        await self._synced(target, endpoint, reply)
        return reply

    async def _synced(
        self, target: BenchmarkTarget, endpoint: Endpoint, reply: Reply
    ) -> None:
        """Record whether the benchmark took the settings."""
        if reply.ok:
            await self.targets.mark_synced(target.id)
        else:
            logger.warning(
                f"benchmark did not take target {endpoint.slug}: {reply.detail}"
            )

    async def _spec(
        self,
        tenant: Tenant,
        connection: BenchmarkConnection,
        endpoint: Endpoint,
        *,
        collection: str,
        instrument: dict[str, Any],
        probe: dict[str, Any],
        enabled: bool,
        schedule: str,
        schedule_at: str,
    ) -> dict[str, Any]:
        """The target as the benchmark takes it."""
        return {
            "key": endpoint.slug,
            "title": endpoint.name or endpoint.slug,
            "url": connection.space_url,
            "endpoint": endpoint.slug,
            "container": connection.container,
            "chroma_host": connection.chroma_host or "localhost",
            "chroma_port": connection.chroma_port,
            "collection": collection or await self._collection_for(tenant, endpoint),
            # Per-endpoint values override connection-wide ones.
            "instrument": {**(connection.instrument or {}), **instrument},
            "probe": {**(connection.probe or {}), **probe},
            "enabled": enabled,
            "schedule": schedule,
            "schedule_at": schedule_at,
        }

    async def _resync(self, tenant: Tenant, connection: BenchmarkConnection) -> None:
        """Re-push every target this connection measures."""
        for target in await self.targets.list_for_tenant(tenant.id):
            if target.connection_id != connection.id:
                continue
            endpoint = await self.endpoints.get_by_id(target.endpoint_id, tenant.id)
            if endpoint is not None:
                await self._push(tenant, connection, target, endpoint)

    async def _next_run_at(
        self, connection: BenchmarkConnection | None, slug: str
    ) -> datetime | None:
        """The benchmark's next scheduled run for this endpoint, or None."""
        if connection is None:
            return None
        reply = await self._client(connection).target(slug)
        if not reply.ok or not isinstance(reply.data, dict):
            return None
        raw = reply.data.get("next_run_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"benchmark returned an unreadable next_run_at: {raw!r}")
            return None

    async def _latest_job(
        self,
        target: BenchmarkTarget,
        connection: BenchmarkConnection | None,
        slug: str,
    ) -> JobResponse | None:
        if connection is None:
            return _parsed(JobResponse, target.last_job) if target.last_job else None
        reply = await self._client(connection).jobs(slug)
        if reply.ok:
            job = _parsed(JobResponse, reply.data[0]) if reply.data else None
            await self.targets.remember_job(
                target.id, job.model_dump(mode="json") if job else None
            )
            return job
        # Unreachable: fall back to the remembered job.
        return _parsed(JobResponse, target.last_job) if target.last_job else None

    async def _connection_for(
        self, tenant: Tenant, target: BenchmarkTarget | None
    ) -> BenchmarkConnection | None:
        if target is not None and target.connection_id:
            return await self.connections.get(tenant.id, target.connection_id)
        return await self.connections.default_for(tenant.id)

    async def _pick_connection(
        self, tenant: Tenant, connection_id: UUID | None
    ) -> BenchmarkConnection:
        connection = (
            await self.connections.get(tenant.id, connection_id)
            if connection_id
            else await self.connections.default_for(tenant.id)
        )
        if connection is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "No benchmark is connected to this Space. Connect one in "
                    "Settings before measuring an endpoint."
                ),
            )
        return connection

    async def _connection_or_404(
        self, tenant: Tenant, connection_id: UUID
    ) -> BenchmarkConnection:
        row = await self.connections.get(tenant.id, connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Benchmark not found")
        return row

    async def _endpoint_or_404(self, tenant: Tenant, slug: str) -> Endpoint:
        endpoint = await self.endpoints.get_by_slug(slug, tenant.id)
        if endpoint is None:
            raise HTTPException(status_code=404, detail="Endpoint not found")
        return endpoint

    async def _pair_or_404(
        self, tenant: Tenant, endpoint: Endpoint, slug: str
    ) -> tuple[BenchmarkTarget, BenchmarkConnection]:
        target = await self.targets.for_endpoint(endpoint.id)
        if target is None:
            raise HTTPException(
                status_code=409,
                detail="This endpoint is not measured by any benchmark yet",
            )
        connection = await self._connection_for(tenant, target)
        if connection is None:
            raise HTTPException(
                status_code=409,
                detail="The benchmark this endpoint was measured by is gone",
            )
        return target, connection


def _raise_if_refused(reply: Reply) -> None:
    """Raise the benchmark's 422 (invalid configuration); other failures pass."""
    if reply.status == 422:
        raise HTTPException(status_code=422, detail=reply.detail)
