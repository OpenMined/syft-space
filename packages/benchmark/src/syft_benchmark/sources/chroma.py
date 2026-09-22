"""Reading the indexed chunks from one Space ChromaDB.

A port of `OMSyft/scripts/qa_chroma.py`.

**This is the only module that sees source text** (invariant 1). Everything
further down the pipeline receives questions and gold answers already. The
boundary runs here not for elegance: it can be checked by imports, whereas
"access by agreement" cannot be checked at all.

ChromaDB is raised as a subprocess inside the Space container and listens on its
own port on 0.0.0.0. Hence two transports:

  * **http** — if the port is published to the host. The main path: fast and
    without docker in the chain;
  * **docker exec** — the fallback: the same HTTP request executed by python
    inside the container. Needed when the port is not published — the pipeline
    works straight away, without recreating containers.

The transport is chosen once, on the first call.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

import httpx

from syft_benchmark.config import Settings, SpaceConfig, get_settings

# There is no curl inside the container, but there is python — that is what we
# call ChromaDB with.
_STUB = """
import json, sys, urllib.error, urllib.request
req = json.loads(sys.stdin.read())
data = json.dumps(req["body"]).encode() if req["body"] is not None else None
url = "http://localhost:%d%s" % (req["port"], req["path"])
r = urllib.request.Request(url, data=data, method=req["method"],
                           headers={"Content-Type": "application/json"})
try:
    sys.stdout.write(urllib.request.urlopen(r, timeout=req["timeout"]).read().decode())
except urllib.error.HTTPError as e:
    sys.stderr.write("HTTP %s: %s" % (e.code, e.read().decode()[:500]))
    sys.exit(2)
except Exception as e:
    sys.stderr.write("%s: %s" % (type(e).__name__, e))
    sys.exit(3)
"""

_PAGE = 500  # how many chunks we pull in one request


class ChromaError(RuntimeError):
    """An error calling the Space ChromaDB."""


@dataclass(frozen=True, slots=True)
class Chunk:
    """One indexed chunk — the unit a question grows out of."""

    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    file_name: str
    headings: str


@dataclass(frozen=True, slots=True)
class Document:
    """A document assembled from its chunks."""

    doc_id: str
    title: str
    url: str
    source: str
    file_name: str
    chunks: list[Chunk]
    # The dates from the ETL header. Needed by the freshness window: the corpus
    # grows while the interest is usually in the latest, and without dates "take
    # the documents from the last week" is unexecutable.
    published_at: datetime | None = None
    ingested_at: datetime | None = None

    @property
    def dated_at(self) -> datetime | None:
        """The date by which the document counts as fresh.

        Publication matters more than ingestion: an interest in freshness is an
        interest in when the material came into the world, not in when our ETL
        picked it up. Reindexing the corpus shifts ingestion for everything at
        once and would thereby zero out any window.
        """
        return self.published_at or self.ingested_at


class ChromaClient:
    """A minimal ChromaDB v2 client for one Space."""

    def __init__(
        self,
        space: SpaceConfig,
        settings: Settings | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.space = space
        self.settings = settings or get_settings()
        self.timeout = timeout
        self.transport: str | None = None
        self._base = (
            f"/api/v2/tenants/{self.settings.chroma_tenant}"
            f"/databases/{self.settings.chroma_database}/collections"
        )

    # --- the transport ----------------------------------------------------
    def _http(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        url = f"http://{self.space.chroma_host}:{self.space.chroma_port}{path}"
        resp = httpx.request(method, url, json=body, timeout=self.timeout)
        if resp.status_code >= 400:
            raise ChromaError(
                f"{method} {path} -> {resp.status_code}: {resp.text[:400]}"
            )
        return resp.json()

    def _docker(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        if not self.space.container:
            raise ChromaError(
                f"Space {self.space.key!r} has no container set — "
                f"the fallback transport is unavailable"
            )
        payload = json.dumps(
            {
                "method": method,
                "path": path,
                "body": body,
                "port": self.settings.chroma_internal_port,
                "timeout": self.timeout,
            }
        )
        proc = subprocess.run(  # noqa: S603 - fixed command, name from the config
            ["docker", "exec", "-i", self.space.container, "python", "-c", _STUB],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout + 30,
            check=False,
        )
        if proc.returncode != 0:
            raise ChromaError(
                f"docker exec {self.space.container}: "
                f"{(proc.stderr or '').strip()[:400]}"
            )
        return json.loads(proc.stdout)

    def _pick_transport(self) -> str:
        """Try HTTP, and on failure fall back to docker exec."""
        if self.space.chroma_port:
            try:
                self._http("GET", "/api/v2/heartbeat", None)
                return "http"
            except Exception:  # noqa: BLE001 - any failure means "try the fallback"
                pass
        try:
            self._docker("GET", "/api/v2/heartbeat", None)
            return "docker"
        except Exception as exc:
            raise ChromaError(
                f"the ChromaDB of node {self.space.key!r} is unreachable both at "
                f"{self.space.chroma_host}:{self.space.chroma_port} and through "
                f"container {self.space.container or '—'}: {exc}"
            ) from exc

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> Any:
        if self.transport is None:
            self.transport = self._pick_transport()
        if self.transport == "http":
            return self._http(method, path, body)
        return self._docker(method, path, body)

    # --- collections ------------------------------------------------------
    def collections(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] | None = self.request("GET", self._base)
        return result or []

    def collection_id(self, collection_name: str) -> str | None:
        """The Space stores it under the name Collection_<collectionName>."""
        wanted = {collection_name, f"Collection_{collection_name}"}
        for coll in self.collections():
            if coll.get("name") in wanted:
                return str(coll["id"])
        return None

    def count(self, collection_id: str) -> int:
        return int(self.request("GET", f"{self._base}/{collection_id}/count"))

    def iter_chunks(self, collection_id: str) -> Iterator[Chunk]:
        """Return all the chunks of a collection, page by page."""
        offset = 0
        while True:
            page = self.request(
                "POST",
                f"{self._base}/{collection_id}/get",
                {
                    "limit": _PAGE,
                    "offset": offset,
                    "include": ["documents", "metadatas"],
                },
            )
            ids: list[str] = page.get("ids") or []
            if not ids:
                return
            documents: list[str] = page.get("documents") or []
            metadatas: list[dict[str, Any]] = page.get("metadatas") or []
            for i, chunk_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                yield Chunk(
                    chunk_id=chunk_id,
                    doc_id=str(meta.get("doc_id") or chunk_id.rsplit("_", 1)[0]),
                    chunk_index=int(meta.get("chunk_index") or 0),
                    text=(documents[i] if i < len(documents) else "") or "",
                    file_name=str(meta.get("file_name") or ""),
                    headings=str(meta.get("headings") or ""),
                )
            if len(ids) < _PAGE:
                return
            offset += len(ids)


# ---------------------------------------------------------------------------
# Parsing the chunks
# ---------------------------------------------------------------------------

# The YAML header the ETL puts on every file. In the index it usually ends up as
# the beginning of the first chunk: useless as a source of questions, and the
# opposite as a source of metadata.
_HEADER_KEYS = frozenset(
    {
        "title",
        "source",
        "author",
        "url",
        "published_date",
        "ingested_at",
        "method",
        "tags",
        "category",
        "updated_at",
    }
)

# The rubbish an article scraper drags along with the text: consent banners,
# footers, invitations to subscribe. Questions about them are meaningless — the
# model honestly asks "why does the site need functional cookies", and such a
# pair clutters the benchmark. Both languages are listed: the corpus can be in
# either.
_BOILERPLATE = (
    "cookie",
    "privacy policy",
    "consent",
    "newsletter",
    "subscribe",
    "sign in",
    "all rights reserved",
    "terms of service",
    "advertis",
    "tracking technolog",
    "user agreement",
    "opt out",
    "do not sell",
)

# The screening threshold: we count ALL occurrences of the markers, not how many
# distinct ones there are. A consent banner repeats "cookie" a dozen times,
# whereas an ordinary paragraph mentions a subscription once and stays in work.
_BOILERPLATE_LIMIT = 3


# The date formats found in ETL headers besides ISO. The list is deliberately
# short: an unparsed date is "there is no date", and such a document is not cut
# off by the window but let through with a note. Silently discarding material
# over a format would be worse than any imprecision of the window.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


def parse_date(raw: str) -> datetime | None:
    """The date from the document header, or None if it cannot be parsed.

    Always returned with a time zone: a naive time cannot be compared with the
    window boundary, and there is no reason to die over that mid-generation.
    """
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for form in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(text, form)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def strip_header(text: str) -> tuple[str, dict[str, str]]:
    """Cut off lines of the form `key: "value"` and return them separately."""
    header: dict[str, str] = {}
    body: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        key, sep, value = stripped.partition(":")
        if sep and not body and key.strip().lower() in _HEADER_KEYS:
            header[key.strip().lower()] = value.strip().strip('"').strip("'")
            continue
        if not body and stripped in ("---", ""):
            continue
        body.append(line)
    return "\n".join(body).strip(), header


def is_useful(text: str, min_chars: int) -> bool:
    """Whether the chunk will do as the basis for a question."""
    if len(text) < min_chars:
        return False
    lowered = text.lower()
    hits = sum(lowered.count(marker) for marker in _BOILERPLATE)
    return hits < _BOILERPLATE_LIMIT


def load_documents(
    client: ChromaClient,
    collection_id: str,
    min_chars: int | None = None,
) -> list[Document]:
    """Assemble a collection into documents.

    The metadata comes from the header, the body from the chunks.

    A rig corpus is dozens of documents and hundreds of chunks, so the collection
    fits into memory whole; for a corpus orders of magnitude larger, page-by-page
    processing belongs here.
    """
    threshold = client.settings.min_chunk_chars if min_chars is None else min_chars

    by_doc: dict[str, list[Chunk]] = {}
    for chunk in client.iter_chunks(collection_id):
        by_doc.setdefault(chunk.doc_id, []).append(chunk)

    documents: list[Document] = []
    for doc_id, chunks in by_doc.items():
        chunks.sort(key=lambda c: c.chunk_index)
        first_body, header = strip_header(chunks[0].text)

        useful: list[Chunk] = []
        for position, chunk in enumerate(chunks):
            text = first_body if position == 0 else chunk.text
            if is_useful(text, threshold):
                useful.append(replace(chunk, text=text))

        file_name = chunks[0].file_name
        documents.append(
            Document(
                doc_id=doc_id,
                title=header.get("title") or file_name,
                url=header.get("url", ""),
                source=header.get("source", ""),
                file_name=file_name,
                chunks=useful,
                published_at=parse_date(header.get("published_date", "")),
                ingested_at=parse_date(header.get("ingested_at", "")),
            )
        )

    documents.sort(key=lambda d: d.file_name)
    return documents
