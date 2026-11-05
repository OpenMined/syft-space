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

# Model refresh calls the provider.
REFRESH_TIMEOUT = httpx.Timeout(120.0, connect=5.0)

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
    def unconfigured(self) -> bool:
        """The benchmark is up but has no control key set (503)."""
        return self.status == 503


@dataclass
class Snapshot:
    """The benchmark's self-description: reachability, capabilities, defaults."""

    reachable: bool = False
    detail: str = ""
    capabilities: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)


class BenchmarkClient:
    """One benchmark, addressed by URL and key."""

    def __init__(self, url: str, token: str | None = None) -> None:
        self.url = url.rstrip("/")
        self.token = token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def _send(
        self,
        http: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        body: Any = None,
        stream: bool = False,
    ) -> httpx.Response | Reply:
        """Send one request: the response when the benchmark answered and did
        not refuse, otherwise the failed ``Reply``. With ``stream`` the
        response body is left unread for the caller."""
        url = f"{self.url}{path}"
        try:
            resp = await http.send(
                http.build_request(method, url, json=body, headers=self._headers),
                stream=stream,
            )
            if resp.status_code >= 400:
                await resp.aread()
                return Reply(ok=False, status=resp.status_code, detail=_detail(resp))
        except httpx.HTTPError as exc:
            logger.warning(f"benchmark {url}: {exc}")
            return Reply(ok=False, detail=str(exc))
        return resp

    async def _call(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        timeout: httpx.Timeout = TIMEOUT,
    ) -> Reply:
        """A JSON call; a 204 answers ``data=None``."""
        async with httpx.AsyncClient(timeout=timeout) as http:
            resp = await self._send(http, method, path, body=body)
            if isinstance(resp, Reply):
                return resp
            try:
                payload = None if resp.status_code == 204 else resp.json()
            except ValueError as exc:
                logger.warning(
                    f"benchmark {self.url}{path}: unreadable response: {exc}"
                )
                return Reply(ok=False, status=resp.status_code, detail=str(exc))
            return Reply(ok=True, data=payload, status=resp.status_code)

    # --- what this benchmark is ------------------------------------------

    async def snapshot(self) -> Snapshot:
        """Fetch health, capabilities and defaults; partial results are kept."""
        health = await self._call("GET", "/health")
        if not health.ok:
            return Snapshot(detail=health.detail or "benchmark is not answering")

        out = Snapshot(reachable=True)
        caps = await self.capabilities()
        if not caps.ok:
            out.reachable = False
            out.detail = (
                "the benchmark has no control key set"
                if caps.unconfigured
                else caps.detail or "the benchmark refused the key"
            )
            return out
        out.capabilities = caps.data or {}

        defaults = await self._call("GET", "/defaults")
        out.defaults = defaults.data or {}
        return out

    # --- the model catalogue -----------------------------------------------

    async def models(self, query: dict[str, Any]) -> Reply:
        """The benchmark's model catalogue, filtered by the benchmark."""
        return await self._call("GET", f"/models{_query(query)}")

    async def refresh_models(self) -> Reply:
        """Have the benchmark refetch its provider's model list."""
        return await self._call("POST", "/models/refresh", timeout=REFRESH_TIMEOUT)

    # --- targets -----------------------------------------------------------

    async def put_target(self, key: str, spec: dict[str, Any]) -> Reply:
        return await self._call("PUT", f"/targets/{key}", body=spec)

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

    async def capabilities(self) -> Reply:
        """What the benchmark can do, and where each provider role points."""
        return await self._call("GET", "/capabilities")

    async def get_settings(self) -> Reply:
        """The benchmark's setting overrides, not the effective values."""
        return await self._call("GET", "/settings")

    async def patch_settings(self, changes: dict[str, Any]) -> Reply:
        """Merge ``changes`` into the overrides; a ``None`` value removes one.

        Fields not named keep their overrides. Answers the whole stored document.
        """
        return await self._call("PATCH", "/settings", body={"values": changes})

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
        return await self._call(method, f"{path}{_query(params)}", body=body)

    async def download(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> Reply:
        """A file from the console: bytes in `data`, type and name in `headers`."""
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as http:
            resp = await self._send(http, "GET", f"{path}{_query(params)}")
            if isinstance(resp, Reply):
                return resp
            return Reply(
                ok=True,
                data=resp.content,
                status=resp.status_code,
                headers=_file_headers(resp),
            )

    async def stream(self, path: str, *, params: dict[str, Any] | None = None) -> Reply:
        """A streamed file: its chunks as an ``AsyncIterator[bytes]`` in `data`,
        type and name in `headers`. The connection stays open until the chunks
        are consumed."""
        http = httpx.AsyncClient(timeout=EXPORT_TIMEOUT)
        resp = await self._send(http, "GET", f"{path}{_query(params)}", stream=True)
        if isinstance(resp, Reply):
            await http.aclose()
            return resp

        async def body() -> AsyncIterator[bytes]:
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()
                await http.aclose()

        return Reply(
            ok=True,
            data=body(),
            status=resp.status_code,
            headers=_file_headers(resp),
        )


def _query(params: dict[str, Any] | None) -> str:
    """A query string of the non-empty ``params``, or empty."""
    clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    return f"?{urlencode(clean)}" if clean else ""


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
