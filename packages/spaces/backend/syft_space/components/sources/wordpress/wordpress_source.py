"""WordPress REST API source.

Ingests posts, pages, or any public post type from a self-hosted WordPress
site via ``/wp-json/wp/v2/``, using Basic Auth (username + Application
Password, from wp-admin → Users → Profile).

``WordPressProvider`` builds the two runtime objects: ``WordPressBrowser``
for picker-time discovery, ``WordPressSource`` for ingestion. Ingestion is
driven by the dataset's selection-table picks passed to ``change_stream``:
each poll re-fetches those items via the REST ``include`` filter and emits
their ``modified_gmt`` as a fingerprint, which the ingestion repository
dedups on so only edited items re-ingest. ``fetch`` writes a post's rendered
HTML to a tempfile. There is no full-site crawl.

Not handled in v1: deletes (no REST tombstones — a removed item just stops
appearing in polls) and a "subscribe to a whole post type" mode.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import tempfile
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.shared.timestamps import parse_datetime
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.errors import (
    SourceAuthError,
    SourceError,
    SourceForbiddenError,
)
from syft_space.components.sources.interfaces import (
    SourceChangeEvent,
    SourceItem,
    SourcePage,
)

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 300
# WAFs (Cloudflare, Wordfence, ...) 403 tool-like User-Agents before the
# request reaches WordPress, so default to a browser UA. Override with the
# `userAgent` config field if a site allowlists a specific value.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
PAGE_SIZE = 100
# Statuses surfaced to the picker and watched by the poll. The authenticated
# account is expected to hold read_private_posts; drafts and trash are left out.
BROWSE_STATUSES = "publish,private"
# WordPress caps per_page at 100, so a post type with more items spans
# several REST pages. The browser hands back one page plus a cursor (the
# next WP page number) and the picker fetches more on demand — no upper
# bound, no silent cap.
# Registered but non-content types — media has no body to ingest; the
# block-editor internals (wp_block, wp_template, ...) are already
# viewable=false and filtered out by that check.
_EXCLUDED_TYPES = {"attachment"}


class WordPressBrowseConfig(BaseModel):
    """Connection config for browsing the WordPress REST API.

    Just the fields needed to authenticate. The post types to browse are
    discovered from the site itself (see ``_fetch_post_types``);
    ``WordPressDatasetConfig`` adds the ingest-time fields.
    """

    site_url: str = Field(
        ...,
        alias="siteUrl",
        title="Site URL",
        description="Base URL of the WordPress site (e.g. https://example.com)",
    )
    username: str = Field(
        ...,
        title="Username",
        description="WordPress user_login or display name — used for Basic Auth",
    )
    application_password: str = Field(
        ...,
        alias="applicationPassword",
        title="Application password",
        description=(
            "WordPress Application Password (24 chars; generate under "
            "Users → Profile → Application Passwords in wp-admin)"
        ),
        json_schema_extra={"format": "password"},
    )
    user_agent: str = Field(
        default=DEFAULT_USER_AGENT,
        alias="userAgent",
        title="User agent",
        description=(
            "HTTP User-Agent header — override when a site WAF expects a "
            "specific allowlisted value"
        ),
    )

    model_config = {"populate_by_name": True}

    @field_validator("site_url")
    @classmethod
    def normalize_site_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v.endswith("/wp-json"):
            v = v[: -len("/wp-json")]
        if not v.startswith(("http://", "https://")):
            raise ValueError("site_url must include scheme (http:// or https://)")
        return v


class WordPressDatasetConfig(WordPressBrowseConfig):
    """Full dataset config — the shape stored on the dataset row.

    Adds the poll cadence to the browse config. The items to poll are NOT
    part of the configuration — they live in the ``dataset_selection``
    table and arrive via ``change_stream``.
    """

    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        alias="pollIntervalSeconds",
        description="Seconds between change-stream polls",
        gt=0,
    )


def _external_id(post_type: str, post_id: int) -> str:
    """Compose a typed external id (e.g. ``post:1234``)."""
    return f"{post_type}:{post_id}"


def _parse_external_id(external_id: str) -> tuple[str, int]:
    """Inverse of ``_external_id``: ``post:1234`` -> ``("post", 1234)``."""
    post_type, _, post_id_str = external_id.partition(":")
    if not post_type or not post_id_str:
        raise ValueError(f"malformed external_id: {external_id!r}")
    return post_type, int(post_id_str)


def _make_client(cfg: WordPressBrowseConfig) -> httpx.AsyncClient:
    """Build an httpx client bound to the site's REST API root.

    Takes a browse config since the ingest config inherits it and only
    the connection fields are needed to authenticate.
    """
    return httpx.AsyncClient(
        base_url=f"{cfg.site_url}/wp-json/wp/v2",
        auth=(cfg.username, cfg.application_password),
        follow_redirects=True,
        timeout=30.0,
        headers={
            "Accept": "application/json",
            "User-Agent": cfg.user_agent,
        },
    )


async def _fetch_post_types(client: httpx.AsyncClient) -> dict[str, dict[str, str]]:
    """Discover the site's ingestable post types from ``/types``.

    Requested in ``edit`` context so the call doubles as the credential
    check — ``/types`` is public in the default ``view`` context and would
    not surface bad auth. Edit context also carries ``viewable``, which we
    use to keep public content types and drop the block-editor internals.
    Each kept type is mapped to its REST URL segment (``rest_base``), which
    is not always ``slug + "s"`` for custom types.

    ``_fields`` is deliberately not sent: on this object-style endpoint
    WordPress collapses a ``_fields`` request to an empty response.

    Returns:
        ``{slug: {"name": <label>, "rest_base": <url segment>}}``.

    Raises:
        SourceAuthError: credentials rejected (401).
        SourceForbiddenError: permission or WAF/User-Agent block (403).
        ValueError: no REST API at this URL (404) — usually not a WordPress
            site at all, or the REST API is disabled.
    """
    r = await client.get("/types", params={"context": "edit"})
    if r.status_code == 401:
        raise SourceAuthError(
            "Authentication failed (401) — check username and Application Password"
        )
    if r.status_code == 403:
        raise SourceForbiddenError(
            "Listing post types returned 403 — the user may lack edit rights, "
            "or the site blocks this User-Agent (override userAgent)"
        )
    if r.status_code == 404:
        # A 404 here means /wp-json/wp/v2 isn't serving the REST API. Reporting
        # the raw status would leave someone checking their password when the
        # real answer is that the URL isn't a WordPress site.
        logger.error("No WordPress REST API found at %s", client.base_url)
        site = str(client.base_url).removesuffix("/wp-json/wp/v2")
        raise ValueError(
            f"No WordPress REST API found at {site} — check the site URL, and "
            "that the REST API has not been disabled."
        )
    r.raise_for_status()
    types: dict[str, dict[str, str]] = {}
    for info in r.json().values():
        slug = info.get("slug")
        if not slug or slug in _EXCLUDED_TYPES or not info.get("viewable"):
            continue
        rest_base = info.get("rest_base")
        if rest_base:
            types[slug] = {"name": info.get("name") or slug, "rest_base": rest_base}
    return types


async def _validate_connection(cfg: WordPressBrowseConfig) -> None:
    """Verify the credentials and that the site exposes ingestable content.

    Delegates to ``_fetch_post_types`` (whose ``edit``-context request is
    the actual auth check) and fails if no content types come back.

    Raises:
        SourceAuthError: credentials rejected (401).
        SourceForbiddenError: permission or WAF/User-Agent block (403).
        ValueError: connected, but no ingestable post types are exposed
            over REST.
    """
    async with _make_client(cfg) as client:
        if not await _fetch_post_types(client):
            raise ValueError(
                f"No ingestable post types are exposed over the REST API at "
                f"{cfg.site_url}"
            )


def _to_source_item(post_type: str, parent_id: str, item: dict[str, Any]) -> SourceItem:
    """Map a REST listing row to a leaf ``SourceItem`` for the picker."""
    rendered = (item.get("title") or {}).get("rendered")
    # WordPress returns titles HTML-encoded (e.g. ``&#8217;``); decode so the
    # picker shows real text instead of entities.
    title = (
        html.unescape(rendered) if rendered else (item.get("slug") or str(item["id"]))
    )
    return SourceItem(
        external_id=_external_id(post_type, item["id"]),
        display_name=title,
        parent_id=parent_id,
        is_container=False,
        is_leaf=True,
        metadata={
            "post_type": post_type,
            "modified_gmt": item.get("modified_gmt"),
            "link": item.get("link"),
            "status": item.get("status"),
        },
    )


class WordPressBrowser:
    """Picker-time browsing of the WordPress REST API.

    Built by ``WordPressProvider.for_browse``. ``list_items(None)`` returns
    one container per post type the site exposes; ``list_items("type:<slug>")``
    returns one page of that type's items, most recently modified first, plus
    a cursor (the next WP page number) for fetching more on demand.
    """

    def __init__(self, config: WordPressBrowseConfig) -> None:
        self.config = config

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        async with _make_client(self.config) as client:
            types = await _fetch_post_types(client)
            if parent_id is None:
                return SourcePage(
                    items=[
                        SourceItem(
                            external_id=f"type:{slug}",
                            display_name=info["name"],
                            parent_id=None,
                            is_container=True,
                            is_leaf=False,
                            metadata={
                                "post_type": slug,
                                "rest_base": info["rest_base"],
                            },
                        )
                        for slug, info in types.items()
                    ],
                    next_cursor=None,
                )

            if not parent_id.startswith("type:"):
                return SourcePage(items=[], next_cursor=None)
            post_type = parent_id[len("type:") :]
            info = types.get(post_type)
            if info is None:
                return SourcePage(items=[], next_cursor=None)

            page = int(cursor) if cursor else 1
            return await self._list_type_page(
                client, post_type, parent_id, info["rest_base"], page
            )

    async def _list_type_page(
        self,
        client: httpx.AsyncClient,
        post_type: str,
        parent_id: str,
        rest_base: str,
        page: int,
    ) -> SourcePage:
        """Fetch one page of a post type's items, most recently modified first.

        Returns the page's items plus a cursor for the next page (the next WP
        page number as a string) while one remains, else ``None``. WordPress
        caps ``per_page`` at 100, so larger types span multiple pages; the
        picker fetches them on demand. Requesting a page past the last returns
        400 (``rest_post_invalid_page_number``), which we treat as exhausted.
        """
        r = await client.get(
            f"/{rest_base}",
            params={
                "per_page": PAGE_SIZE,
                "page": page,
                "orderby": "modified",
                "order": "desc",
                "status": BROWSE_STATUSES,
                "_fields": "id,slug,title,modified_gmt,link,status",
            },
        )
        if r.status_code == 400:
            return SourcePage(items=[], next_cursor=None)
        r.raise_for_status()
        rows = r.json()
        items = [_to_source_item(post_type, parent_id, row) for row in rows]
        total_pages = int(r.headers.get("X-WP-TotalPages", page))
        next_cursor = str(page + 1) if rows and page < total_pages else None
        return SourcePage(items=items, next_cursor=next_cursor)


class WordPressSource:
    """Ingest-time access to the WordPress REST API.

    Built by ``WordPressProvider.for_ingest``. Each poll re-fetches the
    selected items via the REST ``include`` filter and emits their current
    ``modified_gmt``. ``_fingerprints`` caches those values (also filled by
    ``fetch``) so the synchronous ``fingerprint()`` drift-check has
    something to read without a network call.
    """

    def __init__(self, config: WordPressDatasetConfig) -> None:
        self.config = config
        self._fingerprints: dict[str, str] = {}
        self._post_types: dict[str, dict[str, str]] = {}

    async def _rest_base(self, client: httpx.AsyncClient, post_type: str) -> str:
        """Resolve a post type's REST URL segment, caching the lookup."""
        if not self._post_types:
            self._post_types = await _fetch_post_types(client)
        info = self._post_types.get(post_type)
        if info is None:
            raise ValueError(
                f"Post type {post_type!r} is not exposed over the REST API"
            )
        return info["rest_base"]

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        """Delegate to a transient ``WordPressBrowser`` using the browse subset."""
        browser = WordPressBrowser(
            WordPressBrowseConfig.model_validate(self.config.model_dump())
        )
        return await browser.list_items(parent_id, cursor)

    @asynccontextmanager
    async def fetch(self, external_id: str) -> AsyncIterator[IngestFile]:
        """Download a post's rendered HTML to a tempfile and yield it.

        Caches the post's ``modified_gmt`` as a fingerprint on the way.
        """
        post_type, post_id = _parse_external_id(external_id)
        # Scope the client to the request — closed before the (slow) ingest.
        async with _make_client(self.config) as client:
            rest_base = await self._rest_base(client, post_type)
            r = await client.get(
                f"/{rest_base}/{post_id}",
                params={
                    "_fields": (
                        "id,slug,link,modified_gmt,title,content,excerpt,"
                        "categories,tags,author,status"
                    ),
                },
            )
            r.raise_for_status()
            post = r.json()
        html: str = (post.get("content") or {}).get("rendered", "")
        title: str = (post.get("title") or {}).get("rendered", "")
        slug: str = post.get("slug") or str(post_id)

        modified_gmt = post.get("modified_gmt")
        if modified_gmt:
            self._fingerprints[external_id] = modified_gmt

        fd, tmp_str = tempfile.mkstemp(
            prefix=f"wp_{post_type}_{post_id}_", suffix=".html"
        )
        os.close(fd)
        tmp_path = Path(tmp_str)
        tmp_path.write_text(html, encoding="utf-8")
        try:
            yield IngestFile(
                path=tmp_path,
                filename=f"{slug}.html",
                file_size=tmp_path.stat().st_size,
                metadata={
                    "source": WordPressProvider.NAME,
                    "post_type": post_type,
                    "post_id": post_id,
                    "slug": slug,
                    "title": title,
                    "link": post.get("link"),
                    # A datetime, not the raw string: the vector store turns
                    # it into an ISO value plus a filterable epoch int.
                    "modified_gmt": parse_datetime(modified_gmt),
                    "status": post.get("status"),
                    "categories": post.get("categories"),
                    "tags": post.get("tags"),
                    "author": post.get("author"),
                },
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    def fingerprint(self, external_id: str) -> str:
        """Return the cached ``modified_gmt`` for an item.

        The cache is filled by ``change_stream`` polls and ``fetch``. A
        miss (e.g. right after restart, before the first poll) raises
        ``OSError``, which the ingestion manager treats as a best-effort
        skip — it proceeds with the job's recorded fingerprint.
        """
        try:
            return self._fingerprints[external_id]
        except KeyError as e:
            raise OSError(
                f"no cached fingerprint for {external_id} — repopulated "
                "on next change_stream poll"
            ) from e

    def change_stream(
        self, selected_ids: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        """Re-poll the selected posts every ``poll_interval_seconds``.

        The manager supplies the dataset's pick ids from the selection table
        — ``{post_type}:{id}`` posts, polled directly. Ids are self-
        describing, so a future container pick (``category:{id}``) would be
        classified here and expanded to its posts; for now every pick is an
        individual post.
        """
        return self._change_stream_impl(selected_ids)

    async def _change_stream_impl(
        self, selected_ids: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        # One client for the life of the stream; closed when the consuming
        # task is cancelled and the generator unwinds.
        async with _make_client(self.config) as client:
            while True:
                for post_type, post_ids in self._group_by_type(selected_ids).items():
                    try:
                        async for event in self._poll_post_type(
                            client, post_type, post_ids
                        ):
                            yield event
                    except (httpx.HTTPError, SourceError, ValueError) as e:
                        logger.warning(
                            "WordPress poll failed for type %s: %s", post_type, e
                        )
                await asyncio.sleep(self.config.poll_interval_seconds)

    def _group_by_type(self, ids: Iterable[str]) -> dict[str, list[int]]:
        """Group external_ids by post type: ``{type: [id, ...]}``.

        Malformed ids are skipped (and logged) so one bad entry can't
        abort the whole poll.
        """
        grouped: dict[str, list[int]] = {}
        for external_id in ids:
            try:
                post_type, post_id = _parse_external_id(external_id)
            except ValueError:
                logger.warning("Skipping malformed selected id: %r", external_id)
                continue
            grouped.setdefault(post_type, []).append(post_id)
        return grouped

    async def _poll_post_type(
        self, client: httpx.AsyncClient, post_type: str, post_ids: list[int]
    ) -> AsyncIterator[SourceChangeEvent]:
        """Re-fetch one post type's selected items in ``include`` batches.

        Emits an event per returned item with its current ``modified_gmt``;
        the repository dedups, so unchanged items are a no-op. Items the
        API omits (unpublished/deleted) are silently skipped — see the
        module note on deletes.
        """
        rest_base = await self._rest_base(client, post_type)
        for start in range(0, len(post_ids), PAGE_SIZE):
            batch = post_ids[start : start + PAGE_SIZE]
            r = await client.get(
                f"/{rest_base}",
                params={
                    "include": ",".join(str(i) for i in batch),
                    "per_page": len(batch),
                    "status": BROWSE_STATUSES,
                    "_fields": "id,modified_gmt",
                },
            )
            r.raise_for_status()
            for item in r.json():
                modified = item.get("modified_gmt")
                if not modified:
                    continue
                external_id = _external_id(post_type, item["id"])
                self._fingerprints[external_id] = modified
                yield SourceChangeEvent(
                    event_type="updated",
                    external_id=external_id,
                    fingerprint=modified,
                )


class WordPressProvider:
    """Registry description and factories for the WordPress source.

    Exposes metadata, the browse/dataset config schemas, and factories
    that build a ``WordPressBrowser`` or ``WordPressSource`` from a raw
    config dict. Both validators hit the live REST API so bad credentials
    fail fast instead of at first ingest.
    """

    NAME = "wordpress"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "WordPress REST API source (self-hosted)"

    @classmethod
    def icon(cls) -> str:
        return "📰"

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    def browse_schema(cls) -> dict[str, Any]:
        return WordPressBrowseConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return WordPressDatasetConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def selection_covers(cls, item_id: str, external_id: str) -> bool:
        """A post pick covers exactly itself (``{post_type}:{id}`` equality)."""
        return external_id == item_id

    @classmethod
    async def validate_selection(cls, item_ids: list[str]) -> None:
        """No-op for now — post existence is not probed at selection time.

        The picker only surfaces existing posts; confirming per-post existence
        would mean a REST round-trip per pick in the request path. Revisit if
        stale post picks become a problem.
        """
        return None

    @classmethod
    async def validate_browse_config(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = WordPressBrowseConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid browse configuration: {e}") from e
        await _validate_connection(cfg)

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = WordPressDatasetConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e
        await _validate_connection(cfg)

    @classmethod
    def for_browse(cls, configuration: dict[str, Any]) -> WordPressBrowser:
        return WordPressBrowser(WordPressBrowseConfig.model_validate(configuration))

    @classmethod
    def for_ingest(cls, configuration: dict[str, Any]) -> WordPressSource:
        return WordPressSource(WordPressDatasetConfig.model_validate(configuration))
