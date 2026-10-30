"""Benchmark connections, per-endpoint targets, runs and the console proxy.

The Space stores the owner's settings and pushes them to the benchmark, which
keeps its own copy so scheduled runs work while the Space is down. The push is
best effort: a benchmark that is down does not block saving. Measurement
settings (judges, arms, thresholds) are passed through unparsed.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, TypeVar, cast
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
    ConnectionRequest,
    ConnectionResponse,
    JobResponse,
    ProviderKeyState,
    ProviderResponse,
    ProviderRole,
    ProviderUrls,
    RunRequest,
    TargetRequest,
    TargetResponse,
    WindowResponse,
)
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.tenants.entities import Tenant

# How long a cached benchmark self-description (capabilities, defaults) is used.
SNAPSHOT_MAX_AGE = timedelta(hours=1)

# Provider roles (``ProviderResponse`` fields) and the benchmark's names for
# their URL setting and key (its `config.py`).
PROVIDER_ROLES: dict[str, tuple[str, str]] = {
    "shared": ("ollama_url", "llm_api_key"),
    "generator": ("generator_url", "generator_key"),
    "subject": ("subject_url", "subject_key"),
    "judge": ("judge_url", "judge_key"),
    "filter": ("filter_url", "filter_key"),
}
# Checked here so a wrong key name is a clear 404 rather than the benchmark's 422.
ROLE_OF_KEY = {key: role for role, (_, key) in PROVIDER_ROLES.items()}

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


def _require(reply: Reply, fallback: str, *, keep_status: bool = True) -> None:
    """Raise unless the benchmark answered; its error status is kept or made a 502."""
    if reply.ok:
        return
    passed_on = keep_status and reply.status >= 400
    raise HTTPException(
        status_code=reply.status if passed_on else 502,
        detail=reply.detail or fallback,
    )


def _raise_if_refused(reply: Reply) -> None:
    """Raise the benchmark's 422 (invalid configuration); other failures pass."""
    if reply.status == 422:
        raise HTTPException(status_code=422, detail=reply.detail)


def _provider_locality(reply: Reply) -> dict[str, bool]:
    """Per role (``shared`` for the default), whether the benchmark says its
    calls stay inside the perimeter; empty when it did not answer."""
    provider = (reply.data or {}).get("provider") if reply.ok else None
    if not isinstance(provider, dict):
        return {}
    out: dict[str, bool] = {}
    if isinstance(provider.get("local"), bool):
        out["shared"] = provider["local"]
    for role in provider.get("roles") or []:
        if isinstance(role, dict) and isinstance(role.get("local"), bool):
            out[str(role.get("role"))] = role["local"]
    return out


def _provider_view(
    defaults: dict[str, Any], settings: Reply, secrets: Reply, capabilities: Reply
) -> ProviderResponse:
    """Each role's URL, key state and locality from the benchmark's replies.

    Unanswered settings leave the URLs blank, an unanswered key list leaves
    ``key_set`` null (unknown), unanswered capabilities leave ``local`` null.
    """
    values = (settings.data or {}).get("values", {}) if settings.ok else {}
    updated: dict[str, datetime] | None = (
        {item["name"]: item["updated_at"] for item in secrets.data or []}
        if secrets.ok
        else None
    )
    local = _provider_locality(capabilities)
    return ProviderResponse(
        **{
            role: ProviderRole(
                url=values.get(url_field, "") or "",
                url_default=defaults.get(url_field, "") or "",
                key_set=None if updated is None else key in updated,
                key_updated_at=(updated or {}).get(key),
                local=local.get(role),
            )
            for role, (url_field, key) in PROVIDER_ROLES.items()
        }
    )


def _check_provider_key(name: str) -> None:
    if name not in ROLE_OF_KEY:
        raise HTTPException(status_code=404, detail=f"{name!r} is not a provider key")


_CONSOLE_SILENT = "the benchmark's console did not answer"


def _console_dict(reply: Reply) -> dict[str, Any]:
    """A console call's JSON body, or the refusal that stands in for it."""
    _require(reply, _CONSOLE_SILENT)
    return reply.data if isinstance(reply.data, dict) else {}


def _remembered(target: BenchmarkTarget) -> JobResponse | None:
    """The job cached on the target, shown while the benchmark is unreachable."""
    return _parsed(JobResponse, target.last_job) if target.last_job else None


def _warn_if_not_taken(endpoint: Endpoint, reply: Reply) -> None:
    """Log a target push the benchmark did not take."""
    if not reply.ok:
        logger.warning(f"benchmark did not take target {endpoint.slug}: {reply.detail}")


def _seg(value: str) -> str:
    """One path segment, escaped."""
    return quote(value, safe="")


class _TargetSettings(Protocol):
    """What the Space decides about a target: a stored row or a save request."""

    @property
    def collection(self) -> str: ...
    @property
    def instrument(self) -> dict[str, Any] | None: ...
    @property
    def probe(self) -> dict[str, Any] | None: ...
    @property
    def enabled(self) -> bool: ...
    @property
    def schedule(self) -> str: ...
    @property
    def schedule_at(self) -> str: ...


class BenchmarkHandler:
    """Everything the benchmark pages do."""

    def __init__(
        self,
        connection_repository: BenchmarkConnectionRepository,
        target_repository: BenchmarkTargetRepository,
        endpoint_repository: EndpointRepository,
        dataset_repository: DatasetRepository,
        dataset_registry: DatasetTypeRegistry,
        settings_repository: SettingsRepository,
        client_factory: Callable[[str, str | None], BenchmarkClient] = BenchmarkClient,
    ) -> None:
        self.connections = connection_repository
        self.targets = target_repository
        self.endpoints = endpoint_repository
        self.datasets = dataset_repository
        self.dataset_registry = dataset_registry
        self.settings = settings_repository
        self._new_client = client_factory

    # --- connections -------------------------------------------------------

    async def list_connections(self, tenant: Tenant) -> list[ConnectionResponse]:
        """Connected benchmarks; stale self-descriptions are refreshed."""
        rows = await self.connections.list_for_tenant(tenant.id)
        rows = list(await asyncio.gather(*(self._if_stale(row) for row in rows)))
        used = await self.targets.count_by_connection(tenant.id)
        return [
            self._connection_view(row, endpoints=used.get(row.id, 0)) for row in rows
        ]

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
        _require(reply, "the benchmark did not hand over its models", keep_status=False)
        return reply.data or {}

    async def refresh_models(
        self, tenant: Tenant, connection_id: UUID
    ) -> dict[str, Any]:
        """Have the benchmark refetch its provider's model list.

        A refusal keeps its status (e.g. 403 naming the host to allow).
        """
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).refresh_models()
        _require(reply, "the benchmark could not refresh its models")
        return reply.data or {}

    # --- the model providers -------------------------------------------------
    #
    # Provider URLs and keys are benchmark-wide, shared by every Space using it.

    async def get_provider(
        self, tenant: Tenant, connection_id: UUID
    ) -> ProviderResponse:
        row = await self._connection_or_404(tenant, connection_id)
        settings, secrets, capabilities = await self._provider_replies(row)
        _require(settings, "the benchmark would not say", keep_status=False)
        return _provider_view(row.defaults or {}, settings, secrets, capabilities)

    async def save_provider(
        self, tenant: Tenant, connection_id: UUID, urls: ProviderUrls
    ) -> ProviderResponse:
        """Store the provider URLs, leaving every other benchmark setting alone.

        A blank URL is sent as ``None``, which removes that override so the
        benchmark's default applies.
        """
        row = await self._connection_or_404(tenant, connection_id)
        changes = {
            field: url.strip() or None for field, url in urls.model_dump().items()
        }
        client = self._client(row)
        settings = await client.patch_settings(changes)
        _require(settings, "the benchmark refused those addresses")
        secrets, capabilities = await asyncio.gather(
            client.list_credentials(), client.capabilities()
        )
        return _provider_view(row.defaults or {}, settings, secrets, capabilities)

    async def save_provider_credential(
        self, tenant: Tenant, connection_id: UUID, name: str, value: str
    ) -> ProviderKeyState:
        _check_provider_key(name)
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).put_credential(name, value)
        _require(reply, "the benchmark refused that key")
        return await self._key_state(row, name, key_set=True)

    async def delete_provider_credential(
        self, tenant: Tenant, connection_id: UUID, name: str
    ) -> ProviderKeyState:
        _check_provider_key(name)
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).delete_credential(name)
        _require(reply, "the benchmark could not clear that key")
        return await self._key_state(row, name, key_set=False)

    async def _provider_replies(
        self, row: BenchmarkConnection
    ) -> tuple[Reply, Reply, Reply]:
        """The benchmark's settings, key list and capabilities, asked at once."""
        client = self._client(row)
        return await asyncio.gather(
            client.get_settings(), client.list_credentials(), client.capabilities()
        )

    async def _key_state(
        self, row: BenchmarkConnection, name: str, *, key_set: bool
    ) -> ProviderKeyState:
        """Key ``name`` from one key-list read; the operation's result if that read fails."""
        reply = await self._client(row).list_credentials()
        if not reply.ok:
            return ProviderKeyState(key_set=key_set)
        updated = {item["name"]: item["updated_at"] for item in reply.data or []}
        return ProviderKeyState(
            key_set=name in updated, key_updated_at=updated.get(name)
        )

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
            out.defaults = connection.defaults or {}
            out.capabilities = connection.capabilities or {}
        if target is None:
            return out

        out.enabled = target.enabled
        out.collection = target.collection
        out.probe = target.probe or {}
        out.instrument = target.instrument or {}
        out.schedule = target.schedule
        out.schedule_at = target.schedule_at
        out.next_run_at = await self._next_run_at(connection, slug)
        return out

    async def save_target(
        self, tenant: Tenant, slug: str, request: TargetRequest
    ) -> TargetResponse:
        """Start measuring this endpoint, or change how."""
        endpoint = await self._endpoint_or_404(tenant, slug)
        connection = await self._pick_connection(tenant, request.connection_id)

        # Pushed before storing, so a configuration the benchmark refuses is not kept.
        spec = await self._spec(tenant, connection, endpoint, request)
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
            await self.targets.update(apply(existing))
        else:
            new_target = apply(
                BenchmarkTarget(tenant_id=tenant.id, endpoint_id=endpoint.id)
            )
            try:
                await self.targets.create(new_target)
            except IntegrityError:
                # A concurrent save created the row first; update it.
                existing = await self.targets.for_endpoint(endpoint.id)
                assert existing is not None
                await self.targets.update(apply(existing))

        _warn_if_not_taken(endpoint, reply)
        return await self.get_target(tenant, slug)

    async def window(
        self, tenant: Tenant, slug: str, days: int | None = None
    ) -> WindowResponse:
        """How many articles the endpoint's time window holds."""
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._measured_pair_or_409(tenant, endpoint, slug)
        reply = await self._client(connection).window(slug, days)
        _require(reply, "the benchmark could not count the articles", keep_status=False)
        return _parsed(WindowResponse, reply.data)

    # --- runs --------------------------------------------------------------

    async def start_run(
        self, tenant: Tenant, slug: str, request: RunRequest
    ) -> JobResponse:
        endpoint = await self._endpoint_or_404(tenant, slug)
        target, connection = await self._measured_pair_or_409(tenant, endpoint, slug)
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
        _require(reply, "the benchmark did not take the run", keep_status=False)
        job = _parsed(JobResponse, reply.data)
        await self.targets.remember_job(target.id, job.model_dump(mode="json"))
        return job

    async def list_jobs(self, tenant: Tenant, slug: str) -> list[JobResponse]:
        endpoint = await self._endpoint_or_404(tenant, slug)
        target = await self.targets.for_endpoint(endpoint.id)
        connection = await self._connection_for(tenant, target)
        if target is None or connection is None:
            return []
        reply = await self._client(connection).jobs(slug)
        if not reply.ok:
            remembered = _remembered(target)
            return [remembered] if remembered else []
        jobs = [_parsed(JobResponse, item) for item in reply.data or []]
        # An empty list clears the remembered job too.
        await self.targets.remember_job(
            target.id, jobs[0].model_dump(mode="json") if jobs else None
        )
        return jobs

    async def cancel_run(self, tenant: Tenant, slug: str, job_id: str) -> JobResponse:
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._measured_pair_or_409(tenant, endpoint, slug)
        reply = await self._client(connection).cancel(job_id)
        _require(reply, "the run could not be stopped", keep_status=False)
        return _parsed(JobResponse, reply.data)

    # --- the console: pairs, results, judging, run reports ------------------
    #
    # Proxied to the benchmark's console API with a per-target session token;
    # replies are passed through unchanged.

    async def update_pair(
        self, tenant: Tenant, slug: str, pair_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        console = await self._console(tenant, slug)
        reply = await console.raw("PATCH", f"/console/pairs/{_seg(pair_id)}", body=body)
        return _console_dict(reply)

    async def list_results(
        self, tenant: Tenant, slug: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        console = await self._console(tenant, slug)
        return _console_dict(await console.raw("GET", "/console/results", params=query))

    async def override_verdict(
        self, tenant: Tenant, slug: str, result_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        console = await self._console(tenant, slug)
        reply = await console.raw(
            "POST", f"/console/results/{_seg(result_id)}/verdict", body=body
        )
        return _console_dict(reply)

    async def withdraw_verdict(self, tenant: Tenant, slug: str, result_id: str) -> None:
        console = await self._console(tenant, slug)
        reply = await console.raw(
            "DELETE", f"/console/results/{_seg(result_id)}/verdict"
        )
        _require(reply, _CONSOLE_SILENT)

    async def list_report_runs(
        self, tenant: Tenant, slug: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        console = await self._console(tenant, slug)
        return _console_dict(
            await console.raw("GET", "/console/report/runs", params=dict(query))
        )

    async def get_report_run(
        self, tenant: Tenant, slug: str, job_id: str
    ) -> dict[str, Any]:
        console = await self._console(tenant, slug)
        return _console_dict(
            await console.raw("GET", f"/console/report/runs/{_seg(job_id)}")
        )

    async def list_run_questions(
        self, tenant: Tenant, slug: str, job_id: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        console = await self._console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/questions"
        return _console_dict(await console.raw("GET", path, params=query))

    async def list_run_part(
        self, tenant: Tenant, slug: str, job_id: str, part: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        """A run's ``generated``, ``filter``, ``writing`` or ``pairs`` list,
        passed through."""
        console = await self._console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/{part}"
        return _console_dict(await console.raw("GET", path, params=query))

    async def get_run_question(
        self, tenant: Tenant, slug: str, job_id: str, qa_id: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        console = await self._console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/questions/{_seg(qa_id)}"
        return _console_dict(await console.raw("GET", path, params=query))

    async def get_run_pair(
        self, tenant: Tenant, slug: str, job_id: str, qa_id: str
    ) -> dict[str, Any]:
        """One question of the target with its meta and calls, read from a run."""
        console = await self._console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/pairs/{_seg(qa_id)}"
        return _console_dict(await console.raw("GET", path))

    async def get_run_question_fragments(
        self, tenant: Tenant, slug: str, job_id: str, qa_id: str, query: dict[str, Any]
    ) -> list[Any]:
        console = await self._console(tenant, slug)
        path = f"/console/report/runs/{_seg(job_id)}/questions/{_seg(qa_id)}/fragments"
        reply = await console.raw("GET", path, params=query)
        _require(reply, _CONSOLE_SILENT)
        return reply.data if isinstance(reply.data, list) else []

    async def delete_report_run(self, tenant: Tenant, slug: str, job_id: str) -> None:
        """Delete a finished run; the benchmark keeps its questions."""
        console = await self._console(tenant, slug)
        reply = await console.raw("DELETE", f"/console/report/runs/{_seg(job_id)}")
        _require(reply, _CONSOLE_SILENT)

    async def download_run_summary(
        self, tenant: Tenant, slug: str, job_id: str
    ) -> tuple[bytes, dict[str, str]]:
        """The run's summary document and the headers it came with."""
        console = await self._console(tenant, slug)
        reply = await console.download(
            f"/console/report/runs/{_seg(job_id)}/summary.docx"
        )
        _require(reply, _CONSOLE_SILENT)
        return reply.data or b"", reply.headers

    async def stream_run_export(
        self, tenant: Tenant, slug: str, job_id: str
    ) -> tuple[AsyncIterator[bytes], dict[str, str]]:
        """The run's Excel export as it arrives, and the headers it came with."""
        console = await self._console(tenant, slug)
        reply = await console.stream(f"/console/report/runs/{_seg(job_id)}/export.xlsx")
        _require(reply, _CONSOLE_SILENT)
        return cast(AsyncIterator[bytes], reply.data), reply.headers

    async def _console(self, tenant: Tenant, slug: str) -> BenchmarkClient:
        """A client carrying a fresh session token scoped to this endpoint's target."""
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._measured_pair_or_409(tenant, endpoint, slug)
        reply = await self._client(connection).mint_session(slug)
        token = reply.data.get("token") if isinstance(reply.data, dict) else None
        if not reply.ok or not token:
            raise HTTPException(
                status_code=502,
                detail=reply.detail or "the benchmark would not open a console session",
            )
        return self._new_client(connection.url, token)

    # --- helpers -------------------------------------------------------------

    def _client(self, connection: BenchmarkConnection) -> BenchmarkClient:
        """A client carrying the connection's control key."""
        return self._new_client(connection.url, connection.token)

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
            reachable=row.reachable,
            detail=row.detail,
            capabilities=row.capabilities or {},
            endpoints=endpoints,
        )

    async def _own_url(self) -> str:
        """This Space's public URL, or empty."""
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
        """Push this target's settings to the benchmark, best effort; a refusal
        is returned for the caller."""
        spec = await self._spec(tenant, connection, endpoint, target)
        reply = await self._client(connection).put_target(endpoint.slug, spec)
        _warn_if_not_taken(endpoint, reply)
        return reply

    async def _spec(
        self,
        tenant: Tenant,
        connection: BenchmarkConnection,
        endpoint: Endpoint,
        settings: _TargetSettings,
    ) -> dict[str, Any]:
        """The target as the benchmark takes it."""
        collection = settings.collection or await self._collection_for(tenant, endpoint)
        return {
            "key": endpoint.slug,
            "title": endpoint.name or endpoint.slug,
            "url": connection.space_url,
            "endpoint": endpoint.slug,
            "container": connection.container,
            "chroma_host": connection.chroma_host or "localhost",
            "chroma_port": connection.chroma_port,
            "collection": collection,
            "instrument": settings.instrument or {},
            "probe": settings.probe or {},
            "enabled": settings.enabled,
            "schedule": settings.schedule,
            "schedule_at": settings.schedule_at,
        }

    async def _resync(self, tenant: Tenant, connection: BenchmarkConnection) -> None:
        """Re-push every target this connection measures."""
        for target in await self.targets.list_for_connection(connection.id):
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

    async def _measured_pair_or_409(
        self, tenant: Tenant, endpoint: Endpoint, slug: str
    ) -> tuple[BenchmarkTarget, BenchmarkConnection]:
        """The endpoint's target and its connection; 409 when it is not
        measured or its benchmark is gone."""
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
