"""WordPress REST API source.

Pulls posts/pages (or any public post type) from a self-hosted WordPress
site via ``/wp-json/wp/v2/``, authenticating with Basic Auth (username +
Application Password, generated under wp-admin → Users → Profile).

Ingestion is driven by an explicit selection made at picker time. Each
poll re-fetches the selected items via the REST ``include`` filter and
emits their current ``modified_gmt`` as a fingerprint; the ingestion
repository dedups on that fingerprint, so only edited items re-ingest.
There is no full-site crawl.

``fetch`` writes a post's body HTML to a tempfile for downstream parsing.

Not handled in v1: deletes (the REST API emits no tombstones) and a
"subscribe to a whole post type" mode (which would only grow the
selection, leaving modification detection unchanged).
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
# Many WP sites sit behind WAFs/Cloudflare that reject the default httpx
# User-Agent. Default to a mainstream UA; override via config when a site
# expects a specific allowlisted value.
DEFAULT_USER_AGENT = "curl/8.7.1"
PAGE_SIZE = 100


class WordPressBrowseConfig(BaseModel):
    """Connection config for browsing the WordPress REST API.

    The fields needed to authenticate and to enumerate post types as
    picker containers. ``WordPressDatasetConfig`` adds the ingest-time
    fields.
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
    """Full dataset config — the shape stored on the dataset row.

    Adds the poll cadence and the item selection to the browse config.
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
            "The external_ids (``{post_type}:{id}``) to ingest and watch "
            "for changes. The source polls exactly these items; an empty "
            "or unset selection ingests nothing."
        ),
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
        timeout=30.0,
        headers={
            "Accept": "application/json",
            "User-Agent": cfg.user_agent,
        },
    )


async def _probe(cfg: WordPressBrowseConfig) -> None:
    """Verify each post type is reachable with the given credentials.

    Hits the listing endpoint (``/{type}s?per_page=1``) rather than
    ``/users/me``, which hardened sites commonly lock down.

    Raises:
        ValueError: bad auth, a post type not exposed over REST, or the
            site's WAF blocking the request.
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
    """Map a REST listing row to a leaf ``SourceItem`` for the picker."""
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
    """Picker-time browsing of the WordPress REST API.

    Built by ``WordPressProvider.for_browse``. ``list_items(None)`` returns
    one container per post type; ``list_items("type:<name>")`` returns a
    page of that type's most recently modified items.
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

    Built by ``WordPressProvider.for_ingest``. Each poll re-fetches the
    selected items via the REST ``include`` filter and emits their current
    ``modified_gmt``. ``_fingerprints`` caches those values (also filled by
    ``fetch``) so the synchronous ``fingerprint()`` drift-check has
    something to read without a network call.
    """

    def __init__(self, config: WordPressDatasetConfig) -> None:
        self.config = config
        self._fingerprints: dict[str, str] = {}
        self._selected_items: set[str] = set(config.selected_items or ())

    async def list_items(self, parent_id: str | None = None) -> list[SourceItem]:
        """Delegate to a transient ``WordPressBrowser`` using the browse subset."""
        browser = WordPressBrowser(
            WordPressBrowseConfig.model_validate(self.config.model_dump())
        )
        return await browser.list_items(parent_id)

    @asynccontextmanager
    async def fetch(self, external_id: str) -> AsyncIterator[IngestFile]:
        """Download a post's rendered HTML to a tempfile and yield it.

        Caches the post's ``modified_gmt`` as a fingerprint on the way.
        """
        post_type, post_id = _parse_external_id(external_id)
        # Scope the client to the request — closed before the (slow) ingest.
        async with _make_client(self.config) as client:
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

    def change_stream(self) -> AsyncIterator[SourceChangeEvent]:
        """Re-poll the selected items every ``poll_interval_seconds``."""
        return self._change_stream_impl()

    async def _change_stream_impl(self) -> AsyncIterator[SourceChangeEvent]:
        # One client for the life of the stream; closed when the consuming
        # task is cancelled and the generator unwinds.
        async with _make_client(self.config) as client:
            while True:
                for post_type, post_ids in self._selected_by_type().items():
                    try:
                        async for event in self._poll_post_type(
                            client, post_type, post_ids
                        ):
                            yield event
                    except httpx.HTTPError as e:
                        logger.warning(
                            "WordPress poll failed for type %s: %s", post_type, e
                        )
                await asyncio.sleep(self.config.poll_interval_seconds)

    def _selected_by_type(self) -> dict[str, list[int]]:
        """Group the selected external_ids by post type: ``{type: [id, ...]}``.

        Malformed ids are skipped (and logged) so one bad entry can't
        abort the whole poll.
        """
        grouped: dict[str, list[int]] = {}
        for external_id in self._selected_items:
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
        for start in range(0, len(post_ids), PAGE_SIZE):
            batch = post_ids[start : start + PAGE_SIZE]
            r = await client.get(
                f"/{post_type}s",
                params={
                    "include": ",".join(str(i) for i in batch),
                    "per_page": len(batch),
                    "status": "publish",
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
    config dict. Both validators probe the live REST API so bad
    credentials fail fast instead of at first ingest.
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
