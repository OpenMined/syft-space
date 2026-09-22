"""Talking to a benchmark's control API.

Thin on purpose. The Space does not model what a benchmark setting *is* — it
stores what the owner set and hands it over. Every field this client knows by
name is a field that would need a migration here when the benchmark grows one,
and the point of the design is that it does not.

Every call has a short timeout and every failure comes back as a value rather
than an exception. A benchmark that is down must make its own page say so, not
make the Space's settings page unopenable.
"""

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
from loguru import logger

# Short: these calls are a form waiting to be drawn or a button waiting to be
# acknowledged. Starting a run returns as soon as it is queued — the run itself
# takes hours and is watched through the job, not held open on a socket.
TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# The one call that may legitimately take a while: reading the index to see how
# much material is there. It walks the whole collection.
CHECK_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


@dataclass
class Reply:
    """What came back, including the case where nothing did."""

    ok: bool
    data: Any = None
    status: int = 0
    detail: str = ""

    @property
    def missing(self) -> bool:
        """Asked about something the benchmark does not have."""
        return self.status == 404

    @property
    def unconfigured(self) -> bool:
        """The benchmark is up but has no control key set.

        Not the same as refusing us: it means nobody has switched control on
        over there, and the owner has to do it on the benchmark's side.
        """
        return self.status == 503


@dataclass
class Snapshot:
    """Everything the settings form needs, in one round trip."""

    reachable: bool = False
    detail: str = ""
    capabilities: dict[str, Any] = field(default_factory=dict)
    fields: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)


class BenchmarkClient:
    """One benchmark, addressed by URL and key."""

    def __init__(self, url: str, token: str | None = None) -> None:
        self.url = url.rstrip("/")
        self.token = token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def _call(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        timeout: httpx.Timeout = TIMEOUT,
    ) -> Reply:
        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.request(
                    method, f"{self.url}{path}", json=body, headers=self._headers
                )
        except httpx.HTTPError as exc:
            logger.warning(f"benchmark {self.url}{path}: {exc}")
            return Reply(ok=False, detail=str(exc))

        if resp.status_code >= 400:
            return Reply(
                ok=False,
                status=resp.status_code,
                detail=_detail(resp),
            )
        try:
            payload = None if resp.status_code == 204 else resp.json()
        except ValueError as exc:
            logger.warning(f"benchmark {self.url}{path}: unreadable response: {exc}")
            return Reply(ok=False, status=resp.status_code, detail=str(exc))
        return Reply(ok=True, data=payload, status=resp.status_code)

    # --- what this benchmark is ------------------------------------------

    async def snapshot(self) -> Snapshot:
        """Ask the benchmark what it can do and how it is configured.

        Three calls rather than one because they answer three questions and a
        benchmark may grow any of them separately. Partial failure is kept:
        capabilities without defaults still draws a usable form.
        """
        health = await self._call("GET", "/health")
        if not health.ok:
            return Snapshot(detail=health.detail or "benchmark is not answering")

        out = Snapshot(reachable=True)
        caps = await self._call("GET", "/capabilities")
        if not caps.ok:
            out.reachable = False
            out.detail = (
                "the benchmark has no control key set"
                if caps.unconfigured
                else caps.detail or "the benchmark refused the key"
            )
            return out
        out.capabilities = caps.data or {}

        shape = await self._call("GET", "/schema")
        out.fields = shape.data or {}
        defaults = await self._call("GET", "/defaults")
        out.defaults = defaults.data or {}
        return out

    # --- the model catalogue -----------------------------------------------

    async def models(self, query: dict[str, Any]) -> Reply:
        """The models this benchmark can offer, filtered as the picker asks.

        Proxied, not stored: a copy here would be a second answer to what may be
        measured, stale exactly when somebody has just added a model. The
        filtering is the benchmark's for the same reason.
        """
        clean = {key: value for key, value in query.items() if value not in (None, "")}
        suffix = f"?{urlencode(clean)}" if clean else ""
        return await self._call("GET", f"/models{suffix}")

    async def refresh_models(self) -> Reply:
        """Have the benchmark fetch its provider's model list afresh.

        The long timeout: a call to a third party, and a few hundred kilobytes
        back.
        """
        return await self._call("POST", "/models/refresh", timeout=CHECK_TIMEOUT)

    # --- targets -----------------------------------------------------------

    async def put_target(self, key: str, spec: dict[str, Any]) -> Reply:
        return await self._call("PUT", f"/targets/{key}", body=spec)

    async def delete_target(self, key: str) -> Reply:
        return await self._call("DELETE", f"/targets/{key}")

    async def check_target(self, key: str) -> Reply:
        return await self._call("POST", f"/targets/{key}/check", timeout=CHECK_TIMEOUT)

    # --- runs --------------------------------------------------------------

    async def start_run(self, key: str, request: dict[str, Any]) -> Reply:
        return await self._call("POST", f"/targets/{key}/runs", body=request)

    async def target(self, key: str) -> Reply:
        """One target as the benchmark holds it — including when it next fires."""
        return await self._call("GET", f"/targets/{key}")

    async def jobs(self, key: str) -> Reply:
        return await self._call("GET", f"/targets/{key}/jobs")

    async def cancel(self, job_id: str) -> Reply:
        return await self._call("POST", f"/jobs/{job_id}/cancel")

    async def delete_job(self, job_id: str) -> Reply:
        return await self._call("DELETE", f"/jobs/{job_id}")


def _detail(resp: httpx.Response) -> str:
    """The benchmark's own words about the refusal, if it gave any."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    return str(detail or body)[:500]
