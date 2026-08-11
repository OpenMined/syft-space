"""Minimal HTTP client for docling-serve's async conversion API.

Transport only: submits a file, polls the task, and returns the
lossless DoclingDocument as a dict (``json_content``). Knows nothing
about chunking. Flow:

    POST /v1/convert/file/async  ->  task_id
    GET  /v1/status/poll/{task_id}  (until terminal)
    GET  /v1/result/{task_id}    ->  document.json_content
"""

import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Options pinned so the remote result matches in-process conversion:
# the lossless DoclingDocument with picture bytes embedded, at the same
# image resolution the local pipeline produces. docling-serve defaults
# to image_export_mode=placeholder, which would silently drop every
# picture, and images_scale=2.0, which doubles the local resolution.
_CONVERT_OPTIONS = {
    "to_formats": "json",
    "image_export_mode": "embedded",
    "images_scale": "1.0",
}

# task_status values after which polling stops.
_TERMINAL_STATUSES = {"success", "partial_success", "skipped"}

# Per-request timeout: generous read/write for uploads and large results,
# but fail fast when the server is down. The overall conversion deadline
# is the caller's ``timeout_seconds``.
_HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0, write=300.0)


class DoclingServeError(RuntimeError):
    """docling-serve is unreachable or reported a failed conversion."""


class DoclingServeClient:
    """Synchronous client for one docling-serve instance."""

    def __init__(self, base_url: str, poll_interval_seconds: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self._poll_interval = poll_interval_seconds

    def convert_to_docling_dict(
        self, path: Path, filename: str, timeout_seconds: float
    ) -> dict[str, Any]:
        """Convert one file and return the DoclingDocument as a dict.

        Args:
            path: Local readable path of the file to convert
            filename: Display filename sent to the server
            timeout_seconds: Overall conversion deadline

        Raises:
            DoclingServeError: Server unreachable or conversion failed
            TimeoutError: Conversion not finished within ``timeout_seconds``
        """
        deadline = time.monotonic() + timeout_seconds
        try:
            with self._build_http_client() as client:
                task_id = self._submit(client, path, filename)
                self._poll_until_terminal(client, task_id, deadline, filename)
                return self._fetch_result(client, task_id, filename)
        except httpx.HTTPError as e:
            raise DoclingServeError(
                f"docling-serve at {self.base_url} unavailable: {e}"
            ) from e

    def _build_http_client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=_HTTP_TIMEOUT)

    def _submit(self, client: httpx.Client, path: Path, filename: str) -> str:
        """Submit the file for async conversion, returning the task id."""
        with path.open("rb") as fh:
            response = client.post(
                "/v1/convert/file/async",
                files={"files": (filename, fh, "application/octet-stream")},
                data=_CONVERT_OPTIONS,
            )
        response.raise_for_status()
        return response.json()["task_id"]

    def _poll_until_terminal(
        self, client: httpx.Client, task_id: str, deadline: float, filename: str
    ) -> None:
        """Poll the task until it finishes, fails, or the deadline passes."""
        while True:
            response = client.get(f"/v1/status/poll/{task_id}")
            response.raise_for_status()
            info = response.json()
            status = info["task_status"]
            if status == "failure":
                raise DoclingServeError(
                    f"docling-serve failed to convert {filename}: "
                    f"{info.get('error_message') or 'unknown error'}"
                )
            if status in _TERMINAL_STATUSES:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"docling-serve conversion of {filename} timed out "
                    f"(task {task_id} still {status})"
                )
            time.sleep(self._poll_interval)

    def _fetch_result(
        self, client: httpx.Client, task_id: str, filename: str
    ) -> dict[str, Any]:
        """Fetch the finished task's result and return ``json_content``."""
        response = client.get(f"/v1/result/{task_id}")
        response.raise_for_status()
        data = response.json()

        status = data.get("status")
        if status == "partial_success":
            logger.warning(
                "docling-serve partially converted %s: %s",
                filename,
                data.get("errors"),
            )
        elif status != "success":
            raise DoclingServeError(
                f"docling-serve failed to convert {filename} "
                f"(status={status}): {data.get('errors')}"
            )

        json_content = (data.get("document") or {}).get("json_content")
        if not json_content:
            raise DoclingServeError(
                f"docling-serve returned no document for {filename}"
            )
        return json_content
