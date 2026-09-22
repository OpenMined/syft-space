"""Wiring a benchmark up, configuring it, and setting it going.

The Space is the place the owner decides things: which benchmark, which
endpoints, how often, and with what. It stores those decisions and hands them
over. It does not decide how a measurement works — judges, arms and thresholds
are the benchmark's subject, and the Space passes them through without opening
the envelope.

Two copies exist on purpose. The Space keeps what the owner set, because it is
the page he edits; the benchmark keeps the same thing, because it must keep
measuring on schedule while this Space is restarting. Saving here pushes there,
and the push is best-effort: a benchmark that is down must not make the
settings page refuse to save.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar
from uuid import UUID

from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError

from syft_space.components.benchmarks.client import BenchmarkClient, Snapshot
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
    RunRequest,
    TargetRequest,
    TargetResponse,
)
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.tenants.entities import Tenant

# How long a benchmark's description of itself is taken on trust.
#
# Asking the benchmark for the shape of its settings is what lets one that grows
# a field get a form for it without a release on this side; cached for ever,
# that only holds until the benchmark is upgraded. So the cache has an age.
#
# An hour: asking on every page load puts a round trip in front of a page that
# opens fine without one, and asking once a day leaves a rig upgraded this
# morning misconfigured until tomorrow.
SNAPSHOT_MAX_AGE = timedelta(hours=1)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _parsed(model: type[ModelT], data: Any) -> ModelT:
    """Validate the benchmark's reply, turning a shape mismatch into a 502.

    The benchmark is a separate service that can be upgraded independently;
    a field it dropped or renamed must not surface here as an unhandled 500.
    """
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"benchmark sent an unreadable {model.__name__}: {exc}",
        ) from exc


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
        """The benchmarks this Space is wired to, as the settings page shows them.

        A description that has gone stale is refreshed here: this is the page
        that draws a form out of it.
        """
        rows = await self.connections.list_for_tenant(tenant.id)
        # Together rather than in turn: a Space wired to three benchmarks
        # should not open its settings page three timeouts late.
        rows = list(await asyncio.gather(*(self._if_stale(row) for row in rows)))
        out = []
        for row in rows:
            used = await self.targets.count_for_connection(row.id)
            out.append(self._connection_view(row, endpoints=used))
        return out

    async def connect(
        self, tenant: Tenant, request: ConnectionRequest
    ) -> ConnectionResponse:
        """Wire this Space to a benchmark and ask it what it can do.

        The first connection becomes the default without being asked. A Space
        with exactly one benchmark should never have to be told which one to
        use, and a default nobody set is the commonest way to end up with
        endpoints that quietly measure nothing.

        The first connection is also read as the owner's consent to let a
        benchmark report in this Space's name: only he can reach this route,
        and making the connection already says so. ``benchmarks_mode`` is
        switched on with it — once, the first time, through
        ``enable_benchmarks_if_untouched`` — so that consent is not asked for
        twice, once here and once again on a settings page he may never open.
        He can still turn it back off, and it stays off from then on.
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
        if self.settings is not None:
            await self.settings.enable_benchmarks_if_untouched()
        row = await self._refresh(row)
        return self._connection_view(row)

    async def update_connection(
        self, tenant: Tenant, connection_id: UUID, request: ConnectionRequest
    ) -> ConnectionResponse:
        row = await self._connection_or_404(tenant, connection_id)
        row.name = request.name
        row.url = request.url
        # The form was never told the key, so it cannot send it back. Without
        # this rule, renaming a connection would silently revoke its access.
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
        # The benchmark is reached differently now, so every target it holds
        # describes a road that may no longer exist.
        await self._resync(tenant, row)
        return self._connection_view(row)

    async def save_settings(
        self, tenant: Tenant, connection_id: UUID, settings: ConnectionSettings
    ) -> ConnectionResponse:
        """Store how this benchmark should measure, and tell it.

        Settings reach the benchmark only through the targets, and every target
        carries them. That is why saving re-pushes all of them: a setting
        stored here and not there would take effect on the next manual run and
        never on the nightly one.
        """
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
        """Forget a benchmark.

        Its targets lose their connection and stop being measured, but keep
        their settings: the owner is switching benchmarks, not starting over.
        Cards already published are untouched — taking those down is a separate
        decision, made per endpoint, and never a side effect of rewiring.
        """
        row = await self._connection_or_404(tenant, connection_id)
        await self.connections.delete(row.id)

    # --- the model catalogue -----------------------------------------------

    async def models(
        self, tenant: Tenant, connection_id: UUID, query: dict[str, Any]
    ) -> dict[str, Any]:
        """The models this benchmark can offer, as it describes them.

        Passed through unshaped, by the same rule as ``/schema``: a field named
        on this side needs a release here before the benchmark may grow it.
        """
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
        """Have the benchmark fetch its provider's list afresh.

        The refusal keeps its own status: a benchmark whose perimeter forbids
        the call answers 403 naming the host to open, and a blanket 502 would
        replace that instruction with "something went wrong".
        """
        row = await self._connection_or_404(tenant, connection_id)
        reply = await self._client(row).refresh_models()
        if not reply.ok:
            raise HTTPException(
                status_code=reply.status if reply.status >= 400 else 502,
                detail=reply.detail or "the benchmark could not refresh its models",
            )
        return reply.data or {}

    # --- targets -----------------------------------------------------------

    async def get_target(self, tenant: Tenant, slug: str) -> TargetResponse:
        endpoint = await self._endpoint_or_404(tenant, slug)
        target = await self.targets.for_endpoint(endpoint.id)
        connection = await self._connection_for(tenant, target)
        # This page draws a form out of that description too.
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
            out.reachable = connection.reachable
            out.detail = connection.detail
        if target is None:
            return out

        out.enabled = target.enabled
        out.collection = target.collection
        out.probe = target.probe or {}
        out.schedule = target.schedule
        out.schedule_at = target.schedule_at
        out.synced_at = target.synced_at
        # Both in one go: they are two calls to the same service, neither
        # depends on the other, and a page that waited for them in turn would
        # wait twice for no reason.
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

        def apply(target: BenchmarkTarget) -> BenchmarkTarget:
            target.connection_id = connection.id
            target.enabled = request.enabled
            target.collection = request.collection
            target.probe = request.probe or None
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
                # A concurrent save for the same endpoint (a double press of
                # "Save") won the race and created the row first; update it
                # instead of failing this call.
                existing = await self.targets.for_endpoint(endpoint.id)
                assert existing is not None
                target = await self.targets.update(apply(existing))

        await self._push(tenant, connection, target, endpoint)
        return await self.get_target(tenant, slug)

    async def stop_measuring(self, tenant: Tenant, slug: str) -> None:
        """Take this endpoint out of the benchmark entirely.

        The target goes from the benchmark too — otherwise it would keep
        measuring on schedule an endpoint the owner has taken off the list, and
        nothing here would show it. Questions and verdicts stay there: they are
        the history of what was measured, and history is not a setting.
        """
        endpoint = await self._endpoint_or_404(tenant, slug)
        target = await self.targets.for_endpoint(endpoint.id)
        if target is None:
            return
        connection = await self._connection_for(tenant, target)
        if connection is not None:
            reply = await self._client(connection).delete_target(slug)
            if not reply.ok and not reply.missing:
                logger.warning(f"benchmark kept target {slug}: {reply.detail}")
        await self.targets.delete(target.id)

    async def check_target(self, tenant: Tenant, slug: str) -> CheckResponse:
        """Ask the benchmark whether it can actually reach this endpoint."""
        endpoint = await self._endpoint_or_404(tenant, slug)
        target, connection = await self._pair_or_404(tenant, endpoint, slug)
        # Push first: checking settings the benchmark has not been told about
        # would answer a question about the previous ones.
        await self._push(tenant, connection, target, endpoint)
        reply = await self._client(connection).check_target(slug)
        if not reply.ok:
            return CheckResponse(
                problems=[reply.detail or "benchmark is not answering"]
            )
        return _parsed(CheckResponse, reply.data)

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
        await self._push(tenant, connection, target, endpoint)
        reply = await self._client(connection).start_run(
            slug, request.model_dump(exclude_none=True)
        )
        if not reply.ok:
            raise HTTPException(
                status_code=502,
                detail=reply.detail or "the benchmark did not take the run",
            )
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
            # The remembered one rather than nothing: a page that empties out
            # while the benchmark is down reads as "no run ever happened".
            return [_parsed(JobResponse, target.last_job)] if target.last_job else []
        jobs = [_parsed(JobResponse, item) for item in reply.data or []]
        # "There are none" is an answer, not silence. The cache exists for a
        # benchmark that cannot reply; outliving its own reply, it would leave a
        # run on this page with nothing behind it, and leave it there for good.
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

    async def delete_job(self, tenant: Tenant, slug: str, job_id: str) -> None:
        """Discard a finished run: its own row, its passes and their verdicts.

        Not the question set — that belongs to the target and is shared by
        every run that ever measured it. A run still queued or running is
        refused by the benchmark itself (409): stop it first, on its own terms.
        """
        endpoint = await self._endpoint_or_404(tenant, slug)
        _, connection = await self._pair_or_404(tenant, endpoint, slug)
        reply = await self._client(connection).delete_job(job_id)
        if not reply.ok:
            raise HTTPException(
                status_code=reply.status or 502,
                detail=reply.detail or "the run could not be discarded",
            )

    # --- inside ------------------------------------------------------------

    def _client(self, connection: BenchmarkConnection) -> BenchmarkClient:
        return BenchmarkClient(connection.url, connection.token)

    async def _if_stale(self, row: BenchmarkConnection) -> BenchmarkConnection:
        """Refresh a description that has aged out, and never fail over it.

        On failure the row comes back as it stands: a benchmark that is down
        must not make the settings page unopenable, which is why the description
        is cached at all.
        """
        if row.checked_at is not None:
            # SQLite hands the moment back without a zone; it was written in
            # UTC, and comparing it to an aware "now" would raise.
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
        """This Space's address, as far as it knows it."""
        if self.settings is None:
            return ""
        try:
            return await self.settings.get_public_url() or ""
        except Exception:  # noqa: BLE001 - an address we do not know is simply blank
            return ""

    async def _collection_for(self, tenant: Tenant, endpoint: Endpoint) -> str:
        """What the endpoint's index collection is called.

        Resolved rather than typed: the owner picked a dataset, not a
        collection, and making him find the name in ChromaDB would be asking
        him to know an implementation detail of his own Space.
        """
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
    ) -> None:
        """Hand this target's settings to the benchmark.

        Best effort by design. A benchmark that is down must not make the
        settings page refuse to save — the owner would then have nowhere to
        record the decision he has already made. ``synced_at`` says whether it
        got through, and the page says so plainly.
        """
        spec = {
            "key": endpoint.slug,
            "title": endpoint.name or endpoint.slug,
            "url": connection.space_url,
            "endpoint": endpoint.slug,
            "container": connection.container,
            "chroma_host": connection.chroma_host or "localhost",
            "chroma_port": connection.chroma_port,
            "collection": target.collection
            or await self._collection_for(tenant, endpoint),
            "instrument": connection.instrument or {},
            # Two layers flattened into one: the benchmark merges what it is
            # given over its own defaults, and the order between Space-wide and
            # per-endpoint is settled here, where both are known.
            "probe": {**(connection.probe or {}), **(target.probe or {})},
            "enabled": target.enabled,
            "schedule": target.schedule,
            "schedule_at": target.schedule_at,
        }
        reply = await self._client(connection).put_target(endpoint.slug, spec)
        if reply.ok:
            await self.targets.mark_synced(target.id)
        else:
            logger.warning(
                f"benchmark did not take target {endpoint.slug}: {reply.detail}"
            )

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
        """When the benchmark says it will next measure this endpoint.

        Not computed here from the interval. The benchmark is what decides, and
        it also decides what a schedule saved a minute ago means and what a
        window slept through means; a second computation would part company
        with it on exactly the question the owner asks this to answer.

        A benchmark that cannot answer leaves this empty rather than guessing.
        """
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
            # The cache is for a benchmark that cannot answer, not for one that
            # answers "there are none": a run it has forgotten would otherwise
            # stay on this page forever with nothing behind it.
            job = _parsed(JobResponse, reply.data[0]) if reply.data else None
            await self.targets.remember_job(
                target.id, job.model_dump(mode="json") if job else None
            )
            return job
        # Unreachable, so the remembered one stands — dated by its own
        # timestamps rather than pretending to be current.
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
