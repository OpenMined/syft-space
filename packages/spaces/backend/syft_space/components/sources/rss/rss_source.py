"""RSS / Atom source for public feeds.

Ingests items from one or more feeds named by URL. No credentials: a
private feed carries its token in the URL already.

``RssProvider`` builds the two runtime objects: ``RssBrowser`` for
picker-time discovery, ``RssSource`` for ingestion. A feed is
``feed:{feedHash}`` and an item is ``{feedHash}:{itemHash}``; only feeds
are selectable, but items carry an id because that is what
``change_stream`` emits and ``fetch`` receives.

Three properties of real feeds shape this source:

* **A feed is a mutable window, not an archive.** The publisher rewrites
  one document in place, and there is no pagination back to what has
  fallen off (windows sampled ranged from ~12 hours on BBC News to
  unbounded on podcast archives). That makes the poll interval a
  correctness setting, not a tuning knob.
* **Append-only.** RSS 2.0 carries only ``pubDate`` and cannot express an
  edit, so every poll re-emits the whole window and the ingestion
  repository's upsert collapses the repeats. No watermark and no
  suppression, so a transiently-failed ingest retries next poll.
* **The interesting fields are extensions.** The body lives in
  ``content:encoded`` and the author in ``dc:creator``; the spec's own
  ``<author>`` appeared in no feed sampled. ``feedparser`` normalises
  those, which is why it is a dependency rather than a hand-rolled parse.

Fetching stays here rather than in ``feedparser``, which can fetch for
itself, because conditional GET and the per-hop scheme check both need
the request.

Not handled: deletes — a removed item just stops appearing, the same gap
as the Blogspot and WordPress sources.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, NamedTuple

import feedparser
import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.shared.timestamps import parse_datetime
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.errors import SourceError
from syft_space.components.sources.interfaces import (
    SourceChangeEvent,
    SourceItem,
    SourcePage,
)

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 20.0

# Hourly is safe for every feed sampled; the choices span busy news to
# archives. Anything slower than daily loses items on a news-rate feed.
DEFAULT_POLL_INTERVAL_SECONDS = 3600
POLL_INTERVAL_CHOICES = [900, 3600, 21600, 86400]

# One github.blog item measured 486 KB of HTML; ten of those per poll is
# 5 MB held in memory before it reaches a tempfile.
MAX_BODY_BYTES = 1_000_000

# Podcast feeds ship their whole archive (560 items measured) where blogs
# ship ~10; bound the per-poll work rather than assume ingest absorbs it.
MAX_ITEMS_PER_POLL = 200

MAX_REDIRECTS = 5
MAX_SLUG_LENGTH = 60
_HASH_LENGTH = 16

_REDIRECT_CODES = {301, 302, 303, 307, 308}
_TAG_RE = re.compile(r"<[^>]+>")
_ANCHOR_RE = re.compile(r"<a\b[^>]*>.*?</a>", re.IGNORECASE | re.DOTALL)


def _user_agent() -> str:
    """Identify ourselves so a publisher can recognise or block this source."""
    return "SyftSpace-RSS/1.0 (+https://github.com/OpenMined/syft-space)"


@asynccontextmanager
async def _make_client() -> AsyncIterator[httpx.AsyncClient]:
    """Client with redirects OFF — each hop is scheme-checked by hand.

    Reading ``response.history`` after the fact is too late: the request to
    the redirected-to host has already been made.
    """
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"User-Agent": _user_agent()},
    ) as client:
        yield client


# ── configuration ───────────────────────────────────────────────────────


class RssBrowseConfig(BaseModel):
    """Connection config for browsing public feeds.

    ``feed_urls`` is a comma- or newline-separated list so the picker's plain
    text input can name several feeds. ``RssDatasetConfig`` adds the
    ingest-time fields.
    """

    feed_urls: str = Field(
        ...,
        alias="feedUrls",
        title="Feed URLs",
        description=(
            "Public RSS or Atom feed URLs, comma-separated "
            "(e.g. https://example.com/feed/). HTTPS only"
        ),
    )

    model_config = {"populate_by_name": True}

    @field_validator("feed_urls")
    @classmethod
    def normalize_feed_urls(cls, v: str) -> str:
        """Split, validate, and re-join so the stored value is canonical.

        The scheme check re-raises as ``ValueError`` so pydantic reports it
        as a field error, rather than letting a fetch-path ``SourceError``
        escape ``model_validate``.
        """
        urls = _split_feed_urls(v)
        if not urls:
            raise ValueError("At least one feed URL is required")
        for url in urls:
            try:
                _require_https(url)
            except SourceError as e:
                raise ValueError(e.message) from e
        return ",".join(urls)

    @property
    def feed_url_list(self) -> list[str]:
        """The configured URLs, parsed."""
        return _split_feed_urls(self.feed_urls)


class RssDatasetConfig(RssBrowseConfig):
    """Full dataset config — the shape stored on the dataset row.

    Adds the poll cadence to the browse config. The items to poll are NOT
    part of the configuration — they live in the ``dataset_selection``
    table and arrive via ``change_stream``.
    """

    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        alias="pollIntervalSeconds",
        title="Check for new items",
        description=(
            "How often to poll. Match the feed's publishing rate: a feed "
            "only shows its most recent items, so polling slower than it "
            "publishes loses the ones that fall off"
        ),
        json_schema_extra={"enum": POLL_INTERVAL_CHOICES},
    )

    @field_validator("poll_interval_seconds")
    @classmethod
    def known_interval(cls, v: int) -> int:
        """Off-menu intervals are usually a typo, and the wrong one
        silently drops items."""
        if v not in POLL_INTERVAL_CHOICES:
            raise ValueError(
                f"poll_interval_seconds must be one of {POLL_INTERVAL_CHOICES}"
            )
        return v


def _split_feed_urls(raw: str) -> list[str]:
    """Split a comma/newline-separated list, trimmed and de-duplicated."""
    parts = re.split(r"[,\n]", raw or "")
    seen: list[str] = []
    for part in parts:
        url = part.strip().rstrip("/")
        if url and url not in seen:
            seen.append(url)
    return seen


def _require_https(url: str) -> None:
    """Reject anything but https. Called once per redirect hop.

    This doubles as the SSRF guard, and certificate verification is what
    makes it one: internal services speak plain http or hold no
    publicly-valid cert, so even a DNS rebind dies at the TLS handshake.
    Never run with verification disabled.
    """
    parsed = httpx.URL(url)
    if parsed.scheme != "https":
        raise SourceError(
            f"Feed URLs must be https (got {parsed.scheme or 'no scheme'}): {url}"
        )
    if not parsed.host:
        raise SourceError(f"Feed URL has no host: {url}")


# ── id scheme ───────────────────────────────────────────────────────────


def _hash(value: str) -> str:
    """Short stable digest, used for both halves of an id.

    Ids are ``{container}:{leaf}`` and a guid is often a URL, which itself
    contains ``:``, so neither half can be embedded raw.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:_HASH_LENGTH]


def _feed_container_id(feed_url: str) -> str:
    """Compose a whole-feed subscription id (e.g. ``feed:1a2b…``)."""
    return f"feed:{_hash(feed_url)}"


def _parse_feed_container_id(item_id: str) -> str | None:
    """Return the feed hash from a ``feed:{hash}`` id, else None."""
    prefix, _, digest = item_id.partition(":")
    return digest if prefix == "feed" and digest else None


def _item_id(feed_url: str, guid: str) -> str:
    """Compose an item leaf id (e.g. ``1a2b…:3c4d…``)."""
    return f"{_hash(feed_url)}:{_hash(guid)}"


def _parse_item_id(external_id: str) -> tuple[str, str]:
    """Inverse of ``_item_id``: ``feedHash:itemHash``."""
    feed_hash, _, item_hash = external_id.partition(":")
    if not feed_hash or not item_hash or feed_hash == "feed":
        raise ValueError(f"malformed external_id: {external_id!r}")
    return feed_hash, item_hash


def _slugify(title: str) -> str:
    """Reduce a title to a filename stem."""
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug[:MAX_SLUG_LENGTH].strip("-") or "untitled"


# ── fetch + parse ───────────────────────────────────────────────────────


class _Feed(BaseModel):
    """A fetched-and-parsed feed, or the fact that it has not changed."""

    url: str
    title: str = ""
    entries: list[dict[str, Any]] = Field(default_factory=list)
    etag: str | None = None
    modified: str | None = None
    unchanged: bool = False


async def _fetch_feed(
    client: httpx.AsyncClient,
    url: str,
    etag: str | None = None,
    modified: str | None = None,
) -> _Feed:
    """Fetch and parse one feed, honouring conditional GET.

    A 304 returns ``unchanged`` and no body. Redirects are followed by hand
    so every hop is scheme-checked before it is requested.
    """
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified

    current = url
    for _ in range(MAX_REDIRECTS + 1):
        _require_https(current)
        try:
            response = await client.get(current, headers=headers)
        except httpx.HTTPError as e:
            raise SourceError(f"Could not fetch {current}: {e}") from e

        if response.status_code in _REDIRECT_CODES:
            location = response.headers.get("location")
            if not location:
                raise SourceError(f"Redirect without a location from {current}")
            current = str(httpx.URL(current).join(location))
            continue

        if response.status_code == 304:
            return _Feed(url=url, etag=etag, modified=modified, unchanged=True)
        if response.status_code >= 400:
            raise SourceError(
                f"Feed {current} returned HTTP {response.status_code}",
                status_code=response.status_code if response.status_code < 500 else 502,
            )
        return _parse_feed(url, response)

    raise SourceError(f"Too many redirects fetching {url}")


def _parse_feed(url: str, response: httpx.Response) -> _Feed:
    """Parse response bytes into entries.

    ``bozo`` is not fatal: a truncated or unclosed feed still yields usable
    entries, so the gate is how many entries parsed, not whether the parser
    was happy.
    """
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise SourceError(
            f"Could not parse {url}: {parsed.get('bozo_exception') or 'malformed feed'}"
        )
    # Entry count alone cannot tell a mistyped URL from a quiet feed — a web
    # page parses cleanly into zero entries. ``version`` names the dialect and
    # is empty for anything that is not a feed.
    if not parsed.get("version") and not parsed.entries:
        raise SourceError(f"{url} is not an RSS or Atom feed")
    if parsed.bozo:
        logger.warning(
            "Feed %s parsed with warnings (%s); using %d entries",
            url,
            parsed.get("bozo_exception"),
            len(parsed.entries),
        )
    return _Feed(
        url=url,
        title=(parsed.feed.get("title") or "") if parsed.get("feed") else "",
        entries=list(parsed.entries),
        etag=response.headers.get("etag"),
        modified=response.headers.get("last-modified"),
    )


def _entry_guid(entry: dict[str, Any]) -> str:
    """The item's stable identity.

    ``id`` is absent on real feeds (Hacker News), so fall back to the link
    and finally to the title plus date — enough to keep two items in the
    same window apart.
    """
    for key in ("id", "link"):
        value = (entry.get(key) or "").strip()
        if value:
            return value
    return f"{entry.get('title') or ''}|{entry.get('published') or ''}"


def _entry_body(entry: dict[str, Any]) -> str:
    """The item's HTML body: full content if present, else the summary.

    Never both: where a feed carries both, the summary is a prefix of the
    content, so concatenating would double the opening paragraph and skew
    retrieval towards it.
    """
    contents = entry.get("content") or []
    for content in contents:
        value = (content.get("value") or "").strip()
        if value:
            return value
    return (entry.get("summary") or entry.get("description") or "").strip()


def _has_prose(html: str) -> bool:
    """Whether a body says anything beyond its link labels.

    Anchors are dropped before the tag strip, not with it: a Hacker News
    item's whole body is ``<a ...>Comments</a>``, and that label survives a
    plain strip — the same constant string on every item in the feed. A
    length threshold would instead discard genuinely short posts.
    """
    return bool(_TAG_RE.sub(" ", _ANCHOR_RE.sub(" ", html)).strip())


def _entry_metadata(feed: _Feed, entry: dict[str, Any]) -> dict[str, Any]:
    """Searchable facts about the item, and where it came from.

    Dates are ``datetime`` objects: the vector store stores each as an ISO
    string plus a filterable epoch int.
    """
    tags = [t.get("term") for t in (entry.get("tags") or []) if t.get("term")]
    return {
        "source": RssProvider.NAME,
        "feed_url": feed.url,
        "feed_title": feed.title or None,
        "title": entry.get("title") or None,
        "url": entry.get("link") or None,
        "comments_url": entry.get("comments") or None,
        "author": (entry.get("author") or "").strip() or None,
        "tags": tags or None,
        "published": parse_datetime(entry.get("published") or entry.get("updated")),
    }


# ── browse ──────────────────────────────────────────────────────────────


def _to_feed_item(feed: _Feed) -> SourceItem:
    """A feed, pickable whole or expandable to its current items."""
    return SourceItem(
        external_id=_feed_container_id(feed.url),
        display_name=feed.title or feed.url,
        is_container=True,
        is_leaf=True,
        metadata={"feed_url": feed.url, "item_count": len(feed.entries)},
    )


def _to_entry_item(feed: _Feed, entry: dict[str, Any]) -> SourceItem:
    """One item within a feed."""
    guid = _entry_guid(entry)
    published = parse_datetime(entry.get("published") or entry.get("updated"))
    return SourceItem(
        external_id=_item_id(feed.url, guid),
        display_name=entry.get("title") or guid,
        parent_id=_feed_container_id(feed.url),
        is_container=False,
        is_leaf=True,
        metadata={
            "url": entry.get("link"),
            "published": published.isoformat() if published else None,
        },
    )


class RssBrowser:
    """Picker-time browsing of public feeds.

    Built by ``RssProvider.for_browse``. ``list_items(None)`` returns one
    container per configured feed; ``list_items("feed:{hash}")`` returns that
    feed's current items. There is no cursor: feeds do not paginate, so a
    level is always exhausted in one page.
    """

    def __init__(self, config: RssBrowseConfig) -> None:
        self.config = config

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        async with _make_client() as client:
            if parent_id is None:
                feeds = []
                for url in self.config.feed_url_list:
                    feeds.append(await _fetch_feed(client, url))
                return SourcePage(items=[_to_feed_item(f) for f in feeds])

            feed_hash = _parse_feed_container_id(parent_id)
            if feed_hash is None:
                return SourcePage(items=[])

            url = self._url_for_hash(feed_hash)
            if url is None:
                return SourcePage(items=[])

            feed = await _fetch_feed(client, url)
            return SourcePage(items=[_to_entry_item(feed, e) for e in feed.entries])

    def _url_for_hash(self, feed_hash: str) -> str | None:
        """Resolve a feed hash back to its configured URL."""
        for url in self.config.feed_url_list:
            if _hash(url) == feed_hash:
                return url
        return None


# ── ingest ──────────────────────────────────────────────────────────────


class _Slot(NamedTuple):
    """The one feed held in memory, indexed by item id.

    ``feed`` is a header: only the url and title ``_entry_metadata`` stamps
    onto each item, never the parsed entries again.
    """

    feed_hash: str
    feed: _Feed
    entries: dict[str, dict[str, Any]]


class RssSource:
    """Ingest-time access to public feeds.

    Built by ``RssProvider.for_ingest``. Each poll emits an event per item in
    the feed's window and caches nothing: the window is re-emitted whole every
    poll, so all but the few items new since the last one are dropped by the
    scanner and would be cached unread.

    ``fetch`` loads what it needs instead, into ``_slot`` — one feed at a
    time, since parsing a feed for one article materialises all of them.
    ``_conditional`` carries each feed's validators between polls; it holds
    two short strings per feed, so it is not worth bounding.
    """

    def __init__(self, config: RssDatasetConfig) -> None:
        self.config = config
        self._slot: _Slot | None = None
        self._conditional: dict[str, tuple[str | None, str | None]] = {}

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        """Delegate to a transient ``RssBrowser`` using the browse subset."""
        browser = RssBrowser(
            RssBrowseConfig.model_validate(self.config.model_dump(by_alias=True))
        )
        return await browser.list_items(parent_id, cursor)

    @asynccontextmanager
    async def fetch(self, external_id: str) -> AsyncIterator[IngestFile]:
        """Write the item's HTML body to a tempfile and yield it.

        The title becomes an ``<h1>`` so the chunker, which splits on
        headings, names every chunk of a long article. The body is the
        publisher's HTML passed through, and is dropped when it holds
        nothing but link labels.
        """
        feed_hash, item_hash = _parse_item_id(external_id)
        entry, feed = await self._take(external_id, feed_hash)

        body = _entry_body(entry)
        title = entry.get("title") or "(untitled)"
        document = f"<h1>{title}</h1>"
        if _has_prose(body):
            document = f"{document}\n{body}"

        fd, tmp_str = tempfile.mkstemp(prefix=f"rss_{item_hash}_", suffix=".html")
        os.close(fd)
        tmp_path = Path(tmp_str)
        tmp_path.write_text(document, encoding="utf-8")
        try:
            yield IngestFile(
                external_id=external_id,
                path=tmp_path,
                filename=f"{_slugify(title)}_{item_hash}.html",
                file_size=tmp_path.stat().st_size,
                metadata=_entry_metadata(feed, entry),
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    async def _take(
        self, external_id: str, feed_hash: str
    ) -> tuple[dict[str, Any], _Feed]:
        """Claim an item's parsed entry, loading its feed when the slot
        cannot serve it.

        A held slot misses two ways: it holds a different feed, or it has
        already handed this item out — a retry after a failed ingest. Both
        reload, so the entry always comes from a parse that still has it.
        """
        slot = self._slot
        if (
            slot is None
            or slot.feed_hash != feed_hash
            or external_id not in slot.entries
        ):
            self._slot = None  # release the held feed before parsing the next
            slot = await self._load(feed_hash)
            self._slot = slot

        entry = slot.entries.pop(external_id, None)
        if entry is None:
            raise SourceError(
                f"Item {external_id} is no longer in {slot.feed.url}"
                " — feeds keep no archive"
            )
        return entry, slot.feed

    async def _load(self, feed_hash: str) -> _Slot:
        """Download one feed and index its items by id.

        Truncated like a poll: an item the poll would not have emitted has no
        job, so nothing will ask for it.
        """
        url = next(
            (u for u in self.config.feed_url_list if _hash(u) == feed_hash), None
        )
        if url is None:
            raise SourceError(f"No configured feed matches feed {feed_hash}")

        async with _make_client() as client:
            feed = await _fetch_feed(client, url)
        return _Slot(
            feed_hash=feed_hash,
            feed=_Feed(url=feed.url, title=feed.title),
            entries={
                _item_id(url, _entry_guid(e)): e
                for e in feed.entries[:MAX_ITEMS_PER_POLL]
            },
        )

    def fingerprint(self, external_id: str) -> str:
        """The item hash, which is also its fingerprint.

        Append-only, so it never changes and a re-emitted item is correctly
        seen as unchanged.
        """
        _, item_hash = _parse_item_id(external_id)
        return item_hash

    def change_stream(
        self, selected_ids: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        """Poll the selected feeds every ``poll_interval_seconds``.

        Ids are self-describing: ``feed:{hash}`` subscribes to a whole feed
        and keeps picking up items published later, while
        ``{feedHash}:{itemHash}`` is one item. Both resolve against the same
        per-feed fetch, so a whole-feed pick costs no more requests.
        """
        return self._change_stream_impl(selected_ids)

    async def _change_stream_impl(
        self, selected_ids: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        whole_feeds, items_by_feed = self._group_picks(selected_ids)
        feed_urls = [
            url
            for url in self.config.feed_url_list
            if _hash(url) in whole_feeds or _hash(url) in items_by_feed
        ]

        async with _make_client() as client:
            while True:
                for url in feed_urls:
                    feed_hash = _hash(url)
                    try:
                        async for event in self._poll_feed(
                            client,
                            url,
                            whole_feed=feed_hash in whole_feeds,
                            picked_items=items_by_feed.get(feed_hash, set()),
                        ):
                            yield event
                    except (httpx.HTTPError, SourceError, ValueError) as e:
                        logger.warning("RSS poll failed for %s: %s", url, e)
                await asyncio.sleep(self.config.poll_interval_seconds)

    async def _poll_feed(
        self,
        client: httpx.AsyncClient,
        url: str,
        whole_feed: bool,
        picked_items: set[str],
    ) -> AsyncIterator[SourceChangeEvent]:
        """Emit one event per in-scope item in the feed's current window."""
        etag, modified = self._conditional.get(url, (None, None))
        feed = await _fetch_feed(client, url, etag=etag, modified=modified)
        self._conditional[url] = (feed.etag, feed.modified)
        if feed.unchanged:
            return

        # Anything the slot holds for this feed is a parse of the window that
        # just moved, so drop it rather than hold it until the next fetch.
        if self._slot is not None and self._slot.feed_hash == _hash(url):
            self._slot = None

        entries = feed.entries
        if len(entries) > MAX_ITEMS_PER_POLL:
            logger.info(
                "Feed %s has %d items; emitting the newest %d",
                url,
                len(entries),
                MAX_ITEMS_PER_POLL,
            )
            entries = entries[:MAX_ITEMS_PER_POLL]

        for entry in entries:
            external_id = _item_id(url, _entry_guid(entry))
            if not whole_feed and external_id not in picked_items:
                continue

            body = _entry_body(entry)
            if len(body.encode("utf-8")) > MAX_BODY_BYTES:
                logger.warning(
                    "Skipping %s from %s: body is %d bytes (limit %d)",
                    external_id,
                    url,
                    len(body.encode("utf-8")),
                    MAX_BODY_BYTES,
                )
                continue
            if not _has_prose(body) and not (entry.get("title") or "").strip():
                logger.debug(
                    "Skipping %s from %s: no title and no prose", external_id, url
                )
                continue

            yield SourceChangeEvent(
                event_type="created",
                external_id=external_id,
                fingerprint=self.fingerprint(external_id),
                metadata=_entry_metadata(feed, entry),
            )

    @staticmethod
    def _group_picks(
        selected_ids: list[str],
    ) -> tuple[set[str], dict[str, set[str]]]:
        """Split picks into whole-feed subscriptions and per-feed item ids.

        A whole-feed pick absorbs that feed's individual item picks, which
        would otherwise make the scope test ambiguous. Malformed ids are
        skipped so one bad entry cannot abort the poll.
        """
        whole_feeds: set[str] = set()
        items_by_feed: dict[str, set[str]] = {}
        for item_id in selected_ids:
            feed_hash = _parse_feed_container_id(item_id)
            if feed_hash is not None:
                whole_feeds.add(feed_hash)
                continue
            try:
                feed_hash, _ = _parse_item_id(item_id)
            except ValueError:
                logger.warning("Skipping malformed RSS pick: %r", item_id)
                continue
            items_by_feed.setdefault(feed_hash, set()).add(item_id)
        for feed_hash in whole_feeds:
            items_by_feed.pop(feed_hash, None)
        return whole_feeds, items_by_feed


# ── provider ────────────────────────────────────────────────────────────


async def _validate_connection(config: RssBrowseConfig) -> None:
    """Fetch every configured feed so a bad URL fails at setup, not ingest."""
    async with _make_client() as client:
        for url in config.feed_url_list:
            feed = await _fetch_feed(client, url)
            if not feed.entries:
                logger.info("Feed %s currently has no items", url)


class RssProvider:
    """Registry description and factories for the RSS source.

    Both validators fetch the live feeds so an unreachable URL, a non-HTTPS
    one, or a document that is not a feed fails fast.
    """

    NAME = "rss"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "RSS / Atom source (public feeds, no credentials)"

    @classmethod
    def icon(cls) -> str:
        return "📡"

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    def browse_schema(cls) -> dict[str, Any]:
        return RssBrowseConfig.model_json_schema(schema_generator=ConfigSchemaGenerator)

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return RssDatasetConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def selection_covers(cls, item_id: str, external_id: str) -> bool:
        """A feed pick covers every item in it; an item pick covers itself."""
        feed_hash = _parse_feed_container_id(item_id)
        if feed_hash is not None:
            return external_id.startswith(f"{feed_hash}:")
        return external_id == item_id

    @classmethod
    async def validate_selection(cls, item_ids: list[str]) -> None:
        """Only whole feeds are selectable.

        An article pick would ingest once and then poll forever without
        emitting again, so the picker offers feeds only and this refuses the
        rest. Whether a feed still resolves is not checked — its window moves
        on its own, so a pick cannot be confirmed (as in the Blogspot source).

        Raises:
            ValueError: If any pick is an article rather than a whole feed.
                Not ``SourceError``: the create / add-selection handlers
                translate only ``ValueError`` into a 400.
        """
        articles = [i for i in item_ids if _parse_feed_container_id(i) is None]
        if articles:
            raise ValueError(
                "Select whole feeds, not individual articles: "
                + ", ".join(sorted(articles)[:3])
            )

    @classmethod
    async def validate_browse_config(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = RssBrowseConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid browse configuration: {e}") from e
        await _validate_connection(cfg)

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = RssDatasetConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e
        await _validate_connection(cfg)

    @classmethod
    def for_browse(cls, configuration: dict[str, Any]) -> RssBrowser:
        return RssBrowser(RssBrowseConfig.model_validate(configuration))

    @classmethod
    def for_ingest(cls, configuration: dict[str, Any]) -> RssSource:
        return RssSource(RssDatasetConfig.model_validate(configuration))
