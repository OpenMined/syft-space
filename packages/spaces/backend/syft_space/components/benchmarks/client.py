"""HTTP client for a benchmark's control API.

Settings pass through unparsed. Calls have short timeouts and return failures
as a ``Reply`` value instead of raising.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
from loguru import logger

# Default; starting a run returns once it is queued.
TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Target checks walk the whole collection; model refresh calls the provider.
CHECK_TIMEOUT = httpx.Timeout(120.0, connect=5.0)

# Summary document download.
DOWNLOAD_TIMEOUT = httpx.Timeout(60.0, connect=5.0)

# Excel export, built on request.
EXPORT_TIMEOUT = httpx.Timeout(300.0, connect=5.0)


@dataclass
class Reply:
    """A call's result; ``ok`` is False on any failure, including no answer."""

    ok: bool
    data: Any = None
    status: int = 0
    detail: str = ""
    # File headers, set by `download` and `stream`.
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def missing(self) -> bool:
        """The benchmark answered 404."""
        return self.status == 404

    @property
    def unconfigured(self) -> bool:
        """The benchmark is up but has no control key set (503)."""
        return self.status == 503


@dataclass
class Snapshot:
    """The benchmark's self-description: reachability, capabilities, schema, defaults."""

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
        """Fetch health, capabilities, schema and defaults; partial results are kept."""
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
        """The benchmark's model catalogue, filtered by the benchmark."""
        clean = {key: value for key, value in query.items() if value not in (None, "")}
        suffix = f"?{urlencode(clean)}" if clean else ""
        return await self._call("GET", f"/models{suffix}")

    async def refresh_models(self) -> Reply:
        """Have the benchmark refetch its provider's model list."""
        return await self._call("POST", "/models/refresh", timeout=CHECK_TIMEOUT)

    # --- targets -----------------------------------------------------------

    async def put_target(self, key: str, spec: dict[str, Any]) -> Reply:
        return await self._call("PUT", f"/targets/{key}", body=spec)

    async def check_target(self, key: str) -> Reply:
        return await self._call("POST", f"/targets/{key}/check", timeout=CHECK_TIMEOUT)

    # --- runs --------------------------------------------------------------

    async def start_run(self, key: str, request: dict[str, Any]) -> Reply:
        return await self._call("POST", f"/targets/{key}/runs", body=request)

    async def target(self, key: str) -> Reply:
        """One target as the benchmark holds it, including ``next_run_at``."""
        return await self._call("GET", f"/targets/{key}")

    async def window(self, key: str, days: int | None = None) -> Reply:
        """How many articles the target's time window holds."""
        query = f"?days={days}" if days is not None else ""
        return await self._call("GET", f"/targets/{key}/window{query}")

    async def jobs(self, key: str) -> Reply:
        return await self._call("GET", f"/targets/{key}/jobs")

    async def cancel(self, job_id: str) -> Reply:
        return await self._call("POST", f"/jobs/{job_id}/cancel")

    async def mint_session(self, key: str) -> Reply:
        """A short-lived, single-target token for the benchmark's own console."""
        return await self._call("POST", f"/targets/{key}/session")

    # --- installation settings ----------------------------------------------

    async def get_settings(self) -> Reply:
        """The benchmark's setting overrides, not the effective values."""
        return await self._call("GET", "/settings")

    async def put_settings(self, values: dict[str, Any]) -> Reply:
        return await self._call("PUT", "/settings", body={"values": values})

    # --- secrets ---------------------------------------------------------------
    #
    # Write-only: `list_credentials` returns names and update times, not values.

    async def list_credentials(self) -> Reply:
        return await self._call("GET", "/credentials")

    async def put_credential(self, name: str, value: str) -> Reply:
        return await self._call("PUT", f"/credentials/{name}", body={"value": value})

    async def delete_credential(self, name: str) -> Reply:
        return await self._call("DELETE", f"/credentials/{name}")

    # --- the console: pairs, results, filtering, judging, the report -------
    #
    # Used with a per-target session token (see `BenchmarkHandler._console`),
    # not the control key. Paths are given by the caller.

    async def raw(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Reply:
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        suffix = f"?{urlencode(clean)}" if clean else ""
        return await self._call(method, f"{path}{suffix}", body=body)

    async def download(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> Reply:
        """A file from the console: bytes in `data`, type and name in `headers`."""
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        suffix = f"?{urlencode(clean)}" if clean else ""
        url = f"{self.url}{path}{suffix}"
        try:
            async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as http:
                resp = await http.get(url, headers=self._headers)
        except httpx.HTTPError as exc:
            logger.warning(f"benchmark {url}: {exc}")
            return Reply(ok=False, detail=str(exc))
        if resp.status_code >= 400:
            return Reply(ok=False, status=resp.status_code, detail=_detail(resp))
        return Reply(
            ok=True,
            data=resp.content,
            status=resp.status_code,
            headers=_file_headers(resp),
        )

    async def stream(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> tuple[Reply, AsyncIterator[bytes] | None]:
        """A streamed file: the reply (with `headers`) and its body, or a refusal and None."""
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        suffix = f"?{urlencode(clean)}" if clean else ""
        url = f"{self.url}{path}{suffix}"
        http = httpx.AsyncClient(timeout=EXPORT_TIMEOUT)
        try:
            resp = await http.send(
                http.build_request("GET", url, headers=self._headers), stream=True
            )
        except httpx.HTTPError as exc:
            await http.aclose()
            logger.warning(f"benchmark {url}: {exc}")
            return Reply(ok=False, detail=str(exc)), None
        if resp.status_code >= 400:
            await resp.aread()
            await resp.aclose()
            await http.aclose()
            return Reply(ok=False, status=resp.status_code, detail=_detail(resp)), None

        async def body() -> AsyncIterator[bytes]:
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()
                await http.aclose()

        reply = Reply(ok=True, status=resp.status_code, headers=_file_headers(resp))
        return reply, body()


def _file_headers(resp: httpx.Response) -> dict[str, str]:
    """Content type and disposition, to pass a file on."""
    kept = ("content-type", "content-disposition")
    return {k.lower(): v for k, v in resp.headers.items() if k.lower() in kept}


def _detail(resp: httpx.Response) -> str:
    """The error detail from a failed response."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and all(isinstance(item, dict) for item in detail):
        # A validation refusal: one "field: reason" per problem.
        return "; ".join(
            f"{'.'.join(str(part) for part in item.get('loc', [])[1:])}: "
            f"{item.get('msg', '')}"
            for item in detail
        )[:500]
    return str(detail or body)[:500]
