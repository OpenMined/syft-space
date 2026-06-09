"""WordPress REST API source.

Pulls posts and pages (or other public post types) from a self-hosted
WordPress site via ``/wp-json/wp/v2/``. Auth is required — uses HTTP
Basic Auth with a username + Application Password (generate one under
``Users → Profile → Application Passwords`` in ``wp-admin``).

The change stream polls each configured post type on a fixed interval;
the first poll backfills all published items, subsequent polls use the
last-seen ``modified_gmt`` as an exclusive cursor. ``fetch`` writes the
post body HTML to a tempfile so docling can parse it downstream.

Deletes are not detected in v1 — WP's REST API does not emit tombstones.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.interfaces import (
    SourceChangeEvent,
    SourceItem,
)

logger = logging.getLogger(__name__)

DEFAULT_POST_TYPES = ["post", "page"]
DEFAULT_POLL_INTERVAL_SECONDS = 300
# Many WP sites sit behind Cloudflare bot management which rejects the
# default python-httpx UA. Send a mainstream UA by default; users on
# sites that prefer a custom allowlist can override via configuration.
DEFAULT_USER_AGENT = "curl/8.7.1"
PAGE_SIZE = 100


class WordPressBrowseConfig(BaseModel):
    """Picker-time configuration for the WordPress source.

    Holds the connection fields needed to authenticate against the WP
    REST API and the set of post types the picker enumerates as
    containers. Ingest-time fields are added by
    ``WordPressDatasetConfig`` below.
    """

    site_url: str = Field(
        ...,
        alias="siteUrl",
        description="Base URL of the WordPress site (e.g. https://example.com)",
    )
    username: str = Field(
        ...,
        description="WordPress user_login or display name — used for Basic Auth",
    )
    application_password: str = Field(
        ...,
        alias="applicationPassword",
        description=(
            "WordPress Application Password (24 chars; generate under "
            "Users → Profile → Application Passwords in wp-admin)"
        ),
        json_schema_extra={"format": "password"},
    )
    post_types: list[str] = Field(
        default_factory=lambda: list(DEFAULT_POST_TYPES),
        alias="postTypes",
        description="REST API post types to ingest (e.g. post, page)",
    )
    user_agent: str = Field(
        default=DEFAULT_USER_AGENT,
        alias="userAgent",
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
    """Full dataset configuration for the WordPress source.

    Extends the browse configuration with the change-stream polling
    cadence and an optional explicit selection of items to ingest.
    The dataset row stores this shape.
    """

    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        alias="pollIntervalSeconds",
        description="Seconds between change-stream polls",
        gt=0,
    )
    selected_items: list[str] | None = Field(
        default=None,
        alias="selectedItems",
        description=(
            "Restrict ingestion to these external_ids "
            "(``{post_type}:{id}``). ``None`` ingests everything the "
            "source emits; an empty list ingests nothing."
        ),
    )


def _external_id(post_type: str, post_id: int) -> str:
    """Compose a typed external id (e.g. ``post:1234``)."""
    return f"{post_type}:{post_id}"


def _parse_external_id(external_id: str) -> tuple[str, int]:
    post_type, _, post_id_str = external_id.partition(":")
    if not post_type or not post_id_str:
        raise ValueError(f"malformed external_id: {external_id!r}")
    return post_type, int(post_id_str)


def _make_client(cfg: WordPressBrowseConfig) -> httpx.AsyncClient:
    """Build an httpx client for the WordPress REST API.

    Accepts a browse config because the ingest config inherits from it
    and only browse-shaped fields are needed to authenticate.
    """
    return httpx.AsyncClient(
        base_url=f"{cfg.site_url}/wp-json/wp/v2",
        auth=(cfg.username, cfg.application_password),
        timeout=30.0,
        headers={
            "Accept": "application/json",
            "User-Agent": cfg.user_agent,
        },
    )


async def _probe(cfg: WordPressBrowseConfig) -> None:
    """Check that each configured post type is reachable with the given creds.

    Uses ``/{type}s?per_page=1`` (the listing endpoint) rather than
    ``/users/me`` because hardened sites commonly lock down user
    endpoints while leaving listings open.

    Raises:
        ValueError: auth fails, a listed post type isn't exposed at the
            target URL, or the site WAF blocks the request.
    """
    async with _make_client(cfg) as client:
        for post_type in cfg.post_types:
            r = await client.get(f"/{post_type}s", params={"per_page": 1})
            if r.status_code == 401:
                raise ValueError(
                    "Authentication failed (401) — check username and "
                    "Application Password"
                )
            if r.status_code == 403:
                raise ValueError(
                    f"Listing {post_type}s returned 403 — site may "
                    "block this User-Agent (override userAgent in the "
                    "configuration)"
                )
            if r.status_code == 404:
                raise ValueError(
                    f"Post type {post_type!r} not found at "
                    f"{cfg.site_url} — verify it's exposed via REST"
                )
            r.raise_for_status()


def _to_source_item(post_type: str, parent_id: str, item: dict[str, Any]) -> SourceItem:
    title = (
        (item.get("title") or {}).get("rendered") or item.get("slug") or str(item["id"])
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
        },
    )


class WordPressBrowser:
    """Picker-time access to the WordPress REST API.

    Built by ``WordPressProvider.for_browse``. ``list_items(None)``
    returns one container per configured post type;
    ``list_items("type:<name>")`` returns one page of recently-modified
    items in that type.
    """

    def __init__(self, config: WordPressBrowseConfig) -> None:
        self.config = config

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        if parent_id is None:
            return [
                SourceItem(
                    external_id=f"type:{t}",
                    display_name=f"{t.title()}s",
                    parent_id=None,
                    is_container=True,
                    is_leaf=False,
                    metadata={"post_type": t},
                )
                for t in self.config.post_types
            ]

        if not parent_id.startswith("type:"):
            return []
        post_type = parent_id[len("type:") :]
        if post_type not in self.config.post_types:
            return []

        async with _make_client(self.config) as client:
            r = await client.get(
                f"/{post_type}s",
                params={
                    "per_page": PAGE_SIZE,
                    "orderby": "modified",
                    "order": "desc",
                    "status": "publish",
                    "_fields": "id,slug,title,modified_gmt,link",
                },
            )
            r.raise_for_status()
            return [_to_source_item(post_type, parent_id, item) for item in r.json()]


class WordPressSource:
    """Ingest-time access to the WordPress REST API.

    Built by ``WordPressProvider.for_ingest``. Maintains per-type
    ``modified_gmt`` cursors that advance with each poll, and a
    fingerprint cache populated by ``change_stream()`` emissions and
    ``fetch()`` responses (``fingerprint()`` is synchronous and cannot
    reach the network).
    """

    def __init__(self, config: WordPressDatasetConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._cursors: dict[str, str | None] = dict.fromkeys(self.config.post_types)
        self._fingerprints: dict[str, str] = {}
        self._selected_items: set[str] | None = (
            None if config.selected_items is None else set(config.selected_items)
        )

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = _make_client(self.config)
        return self._client

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        """Delegate to a transient ``WordPressBrowser`` using the browse subset."""
        browser = WordPressBrowser(
            WordPressBrowseConfig.model_validate(self.config.model_dump())
        )
        return await browser.list_items(parent_id)

    @asynccontextmanager
    async def fetch(self, external_id: str) -> AsyncIterator[IngestFile]:
        """Materialize a post's body HTML to a tempfile and yield it."""
        post_type, post_id = _parse_external_id(external_id)
        client = self._get_client()
        r = await client.get(
            f"/{post_type}s/{post_id}",
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
                    "modified_gmt": modified_gmt,
                    "status": post.get("status"),
                    "categories": post.get("categories"),
                    "tags": post.get("tags"),
                    "author": post.get("author"),
                },
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    def fingerprint(self, external_id: str) -> str:
        """Return the cached ``modified_gmt`` for the given external_id.

        The cache is populated by ``change_stream()`` emissions and
        ``fetch()`` responses. A cache miss (e.g. immediately after
        restart, before the first poll completes) raises ``OSError`` —
        the ingestion manager treats that as a best-effort skip and
        proceeds with the job's previously-recorded fingerprint.
        """
        try:
            return self._fingerprints[external_id]
        except KeyError as e:
            raise OSError(
                f"no cached fingerprint for {external_id} — repopulated "
                "on next change_stream poll"
            ) from e

    def change_stream(self) -> AsyncIterator[SourceChangeEvent]:
        """Poll each configured post type on the configured interval."""
        return self._change_stream_impl()

    async def _change_stream_impl(self) -> AsyncIterator[SourceChangeEvent]:
        client = self._get_client()
        while True:
            for post_type in self.config.post_types:
                try:
                    async for event in self._poll_post_type(client, post_type):
                        yield event
                except httpx.HTTPError as e:
                    logger.warning(
                        "WordPress poll failed for type %s: %s", post_type, e
                    )
            await asyncio.sleep(self.config.poll_interval_seconds)

    async def _poll_post_type(
        self, client: httpx.AsyncClient, post_type: str
    ) -> AsyncIterator[SourceChangeEvent]:
        """One pass: paginate all items modified after the cursor.

        ``self._selected_items`` (when non-None) restricts emission to
        the listed ``external_id``s; the cursor still advances past
        every item the API returns, so we don't re-scan the skipped
        ones on the next poll.
        """
        params: dict[str, Any] = {
            "per_page": PAGE_SIZE,
            "orderby": "modified",
            "order": "asc",
            "status": "publish",
            "_fields": "id,modified_gmt",
        }
        cursor = self._cursors.get(post_type)
        if cursor is not None:
            # ``modified_after`` is exclusive — strictly newer items only.
            params["modified_after"] = cursor

        page = 1
        latest_seen: str | None = cursor
        while True:
            r = await client.get(f"/{post_type}s", params={**params, "page": page})
            # WP returns 400 with code ``rest_post_invalid_page_number``
            # when paginating past the end. Treat that as end-of-stream.
            if r.status_code == 400:
                break
            r.raise_for_status()
            items = r.json()
            if not items:
                break

            for item in items:
                modified = item.get("modified_gmt")
                if not modified:
                    continue
                external_id = _external_id(post_type, item["id"])
                if latest_seen is None or modified > latest_seen:
                    latest_seen = modified
                if (
                    self._selected_items is not None
                    and external_id not in self._selected_items
                ):
                    continue
                self._fingerprints[external_id] = modified
                yield SourceChangeEvent(
                    event_type="updated",
                    external_id=external_id,
                    fingerprint=modified,
                )

            try:
                total_pages = int(r.headers.get("X-WP-TotalPages", "1"))
            except ValueError:
                total_pages = 1
            if page >= total_pages:
                break
            page += 1

        if latest_seen is not None:
            self._cursors[post_type] = latest_seen


class WordPressProvider:
    """Description of the WordPress source for the registry.

    Holds metadata, the browse and dataset configuration schemas, and
    the factories that build a ``WordPressBrowser`` or
    ``WordPressSource`` from a raw configuration dict. Both validators
    probe the live WP REST API so bad credentials surface immediately
    rather than at first ingest.
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
    async def validate_browse_config(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = WordPressBrowseConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid browse configuration: {e}") from e
        await _probe(cfg)

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = WordPressDatasetConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e
        await _probe(cfg)

    @classmethod
    def for_browse(cls, configuration: dict[str, Any]) -> WordPressBrowser:
        return WordPressBrowser(WordPressBrowseConfig.model_validate(configuration))

    @classmethod
    def for_ingest(cls, configuration: dict[str, Any]) -> WordPressSource:
        return WordPressSource(WordPressDatasetConfig.model_validate(configuration))
