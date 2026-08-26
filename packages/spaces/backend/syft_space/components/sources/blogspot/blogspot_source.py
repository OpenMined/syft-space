"""Blogspot (Blogger v3) source for public blogs.

Ingests posts from one or more public Blogger blogs, named by URL, via
``https://www.googleapis.com/blogger/v3`` with a Google API key. The key
identifies the caller for quota purposes only — it grants no access to
anyone's account, so this source reads exactly what an anonymous visitor
could read, and one key serves any number of blogs.

The v3 API refuses unauthenticated callers outright ("Method doesn't allow
unregistered callers"), so a key is required even for public data. Getting
one is a single console step: create a project, enable the Blogger API,
create an API key. No OAuth client, no consent screen, no token to refresh.

``BlogspotProvider`` builds the two runtime objects: ``BlogspotBrowser`` for
picker-time discovery, ``BlogspotSource`` for ingestion. Each configured URL
is resolved to a blog via ``blogs/byurl`` and shown as a container; both a
whole blog (``blog:{blogId}``) and an individual post (``{blogId}:{postId}``)
can be picked. Ingestion is driven by those picks passed to ``change_stream``:
each poll walks the blog's post list and emits a post's ``updated`` timestamp
as a fingerprint, which the ingestion repository dedups on so only edited
posts re-ingest. ``fetch`` writes a post's HTML body to a tempfile.

Two behaviours differ from the WordPress source, both because a whole-blog
pick expands to arbitrarily many leaves:

* The poll walks the blog's listing rather than re-fetching exact ids —
  Blogger has no ``include``-style id filter. A watermark stops the walk
  early once it reaches posts older than the newest one seen last time.
* Unchanged posts are not re-emitted between sweeps — re-emitting a large
  blog every poll would cost a DB read per post. Every
  ``FULL_SWEEP_EVERY_POLLS`` polls the suppression is dropped for one walk, so
  a transiently-failed ingest can still use its retry budget.

Not handled: deletes (Blogger has no REST tombstone — a removed post just
stops appearing in polls, same gap as the WordPress source), drafts and
private blogs (both need an account-delegated OAuth token, which this source
deliberately does not use).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from collections.abc import AsyncIterator
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

BLOGGER_API_ROOT = "https://www.googleapis.com/blogger/v3"

DEFAULT_POLL_INTERVAL_SECONDS = 300
# Blogger caps maxResults per page; the browser hands back one page plus the
# API's own nextPageToken, which is what drives the picker's "Load more".
PAGE_SIZE = 100
# Longest filename stem taken from a post title before the post id suffix.
MAX_SLUG_LENGTH = 60
# Polls between full re-walks. A FAILED job only re-queues when the source
# re-emits it, so suppression can't be permanent. ~hourly at the default poll.
FULL_SWEEP_EVERY_POLLS = 12

# 403s that are about quota rather than access. Reporting these as an API-key
# problem would send people hunting through the console for the wrong thing.
_QUOTA_REASONS = {
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "dailyLimitExceeded",
    "quotaExceeded",
}


# ── Configuration ────────────────────────────────────────────────────────


class BlogspotBrowseConfig(BaseModel):
    """Connection config for browsing public Blogger blogs.

    ``blog_urls`` is a comma- or newline-separated list so the picker's plain
    text input can name several blogs; ``blog_url_list`` is the parsed form.
    One API key covers all of them — it authenticates the caller, not the
    blog. ``BlogspotDatasetConfig`` adds the ingest-time fields.
    """

    blog_urls: str = Field(
        ...,
        alias="blogUrls",
        title="Blog URLs",
        description=(
            "Public Blogger blog URLs, comma-separated "
            "(e.g. https://example.blogspot.com)"
        ),
    )
    api_key: str = Field(
        ...,
        alias="apiKey",
        title="API key",
        description=(
            "Google API key with the Blogger API enabled (APIs & Services → "
            "Credentials → Create credentials → API key)"
        ),
        json_schema_extra={"format": "password"},
    )

    model_config = {"populate_by_name": True}

    @field_validator("blog_urls")
    @classmethod
    def normalize_blog_urls(cls, v: str) -> str:
        """Split, normalize, and re-join so the stored value is canonical."""
        urls = _split_blog_urls(v)
        if not urls:
            raise ValueError("At least one blog URL is required")
        return ",".join(urls)

    @property
    def blog_url_list(self) -> list[str]:
        """The configured URLs, parsed."""
        return _split_blog_urls(self.blog_urls)


class BlogspotDatasetConfig(BlogspotBrowseConfig):
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


def _split_blog_urls(raw: str) -> list[str]:
    """Parse a comma/newline-separated URL list, normalizing each entry.

    Duplicates are dropped while preserving the order the user typed, so the
    picker shows each blog once.

    Raises:
        ValueError: If an entry is not an http(s) URL.
    """
    urls: list[str] = []
    for part in re.split(r"[,\n]", raw or ""):
        url = part.strip().rstrip("/")
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            raise ValueError(
                f"Blog URL must include scheme (http:// or https://): {url!r}"
            )
        if url not in urls:
            urls.append(url)
    return urls


# ── Id space ─────────────────────────────────────────────────────────────
# Containers are ``blog:{blogId}``; leaves are ``{blogId}:{postId}``. Blog
# ids are numeric, so the ``blog:`` prefix never collides with a leaf id.


def _blog_container_id(blog_id: str) -> str:
    """Compose a blog container id (e.g. ``blog:123``)."""
    return f"blog:{blog_id}"


def _parse_blog_container_id(item_id: str) -> str | None:
    """Return the blog id if ``item_id`` is a blog container, else ``None``."""
    if not item_id.startswith("blog:"):
        return None
    blog_id = item_id[len("blog:") :]
    return blog_id or None


def _post_id(blog_id: str, post_id: str) -> str:
    """Compose a post leaf id (e.g. ``123:456``)."""
    return f"{blog_id}:{post_id}"


def _parse_post_id(external_id: str) -> tuple[str, str]:
    """Inverse of ``_post_id``: ``123:456`` -> ``("123", "456")``."""
    blog_id, _, post = external_id.partition(":")
    if not blog_id or not post:
        raise ValueError(f"malformed external_id: {external_id!r}")
    return blog_id, post


def _slugify(title: str) -> str:
    """Reduce a post title to a filename stem.

    Blogger has no ``slug`` field — the readable part of a post's path lives
    in ``url`` — so the stem comes from the title.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug[:MAX_SLUG_LENGTH].strip("-") or "untitled"


# ── HTTP ─────────────────────────────────────────────────────────────────


def _make_client() -> httpx.AsyncClient:
    """Build an httpx client bound to the Blogger API root."""
    return httpx.AsyncClient(
        base_url=BLOGGER_API_ROOT,
        timeout=30.0,
        headers={"Accept": "application/json"},
    )


def _google_error_reason(response: httpx.Response) -> tuple[str, str]:
    """Pull ``(reason, message)`` out of a Google JSON error body."""
    try:
        error = response.json().get("error", {})
    except ValueError:
        return "", response.text
    message = error.get("message", "")
    errors = error.get("errors") or []
    reason = errors[0].get("reason", "") if errors else ""
    return reason, message


def _check_response(response: httpx.Response) -> None:
    """Map a Blogger API error onto the source-layer exception hierarchy.

    Raises:
        SourceAuthError: Credentials rejected (401).
        SourceForbiddenError: Blogger API not enabled, or the blog is private.
        SourceError: Quota exhausted (403), request rejected (400), or the
            blog/post is gone (404).
        httpx.HTTPStatusError: Any other failure.
    """
    if response.status_code < 400:
        return

    reason, message = _google_error_reason(response)

    if response.status_code == 401:
        raise SourceAuthError(f"Google rejected the credentials. {message}".strip())

    if response.status_code == 403:
        if reason == "accessNotConfigured":
            raise SourceForbiddenError(
                "The Blogger API is not enabled on this API key's Google Cloud "
                "project. Enable it under APIs & Services → Library → Blogger "
                "API, then retry."
            )
        if reason in _QUOTA_REASONS:
            raise SourceError(
                "Blogger API quota exceeded — this is a rate limit, not a key "
                f"problem. {message}".strip()
            )
        raise SourceForbiddenError(
            "Blogger refused the request. The blog may be private — this "
            f"source reads public blogs only. {message}".strip()
        )

    if response.status_code == 404:
        raise SourceError(f"Not found on Blogger. {message}".strip(), status_code=404)

    if response.status_code == 400:
        # Google's own text is specific here — a bad key says so, and so does a
        # malformed parameter. Classifying further would guess at the difference.
        raise SourceError(
            f"Blogger rejected the request. {message}".strip(), status_code=400
        )

    response.raise_for_status()


async def _get(
    client: httpx.AsyncClient,
    api_key: str,
    url: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GET a Blogger endpoint, authenticating with the API key.

    Header rather than the ``key=`` query param: httpx embeds the URL in every
    error it raises, which would put the key into logs and error bodies.
    """
    response = await client.get(url, params=params, headers={"x-goog-api-key": api_key})
    _check_response(response)
    return response.json()


async def _fetch_blog(
    client: httpx.AsyncClient, api_key: str, blog_url: str
) -> dict[str, Any]:
    """Resolve one public blog URL to its Blogger blog resource.

    Raises:
        SourceAuthError: The API key was rejected.
        SourceForbiddenError: Blogger API not enabled, or the blog is private.
        ValueError: No public blog at that URL.
    """
    try:
        return await _get(client, api_key, "/blogs/byurl", params={"url": blog_url})
    except SourceError as e:
        if e.status_code == 404:
            raise ValueError(
                f"No public Blogger blog found at {blog_url} — check the URL, "
                "and note that private blogs cannot be read."
            ) from e
        raise


async def _fetch_blogs(
    client: httpx.AsyncClient, api_key: str, blog_urls: list[str]
) -> list[dict[str, Any]]:
    """Resolve every configured URL, concurrently, reporting all failures.

    ``gather`` would surface only the first failure, so someone who mistyped
    three URLs would fix them one round-trip at a time. Every URL is resolved
    and the failures are reported together.

    A problem with the key itself (rejected, Blogger API disabled, quota)
    fails every URL identically — that case is re-raised as its own typed
    error rather than listed once per blog, so the picker still shows "check
    your API key" instead of a wall of repeats.

    Raises:
        SourceAuthError / SourceForbiddenError / SourceError: A key-level
            problem affecting every URL.
        ValueError: One or more URLs are not readable public blogs.
    """
    results = await asyncio.gather(
        *(_fetch_blog(client, api_key, url) for url in blog_urls),
        return_exceptions=True,
    )

    blogs: list[dict[str, Any]] = []
    failures: list[tuple[str, BaseException]] = []
    for url, result in zip(blog_urls, results, strict=True):
        if isinstance(result, BaseException):
            failures.append((url, result))
        else:
            blogs.append(result)

    if not failures:
        return blogs

    messages = {str(error) for _, error in failures}
    if len(failures) == len(blog_urls) and len(messages) == 1:
        raise failures[0][1]

    raise ValueError(
        "Could not read "
        + ("this blog: " if len(failures) == 1 else f"{len(failures)} blogs: ")
        + "; ".join(f"{url} — {error}" for url, error in failures)
    )


async def _list_posts_page(
    client: httpx.AsyncClient,
    api_key: str,
    blog_id: str,
    page_token: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch one page of a blog's posts, newest-updated first.

    Returns the rows plus Blogger's own ``nextPageToken`` (``None`` when the
    listing is exhausted), which the caller passes straight through as a
    ``SourcePage`` cursor — that is what drives the picker's "Load more".

    ``status`` and ``view`` are deliberately not sent: they are admin-level
    filters needing an account token, and the public listing already returns
    exactly the published posts this source can read.
    """
    params: dict[str, Any] = {
        "maxResults": PAGE_SIZE,
        "orderBy": "updated",
        "fetchBodies": "false",
        "fetchImages": "false",
    }
    if page_token:
        params["pageToken"] = page_token
    payload = await _get(client, api_key, f"/blogs/{blog_id}/posts", params=params)
    return payload.get("items") or [], payload.get("nextPageToken")


async def _validate_connection(cfg: BlogspotBrowseConfig) -> None:
    """Verify the key works and every configured blog resolves.

    Raises:
        SourceAuthError: The API key was rejected.
        SourceForbiddenError: Blogger API not enabled, or a blog is private.
        ValueError: A configured URL is not a public Blogger blog.
    """
    async with _make_client() as client:
        await _fetch_blogs(client, cfg.api_key, cfg.blog_url_list)


def _to_blog_item(blog: dict[str, Any]) -> SourceItem:
    """Map a Blogger blog to a container ``SourceItem`` for the picker."""
    blog_id = str(blog["id"])
    return SourceItem(
        external_id=_blog_container_id(blog_id),
        display_name=blog.get("name") or blog_id,
        parent_id=None,
        is_container=True,
        # A blog is itself pickable: picking it subscribes to the whole blog,
        # including posts published after the pick.
        is_leaf=True,
        metadata={
            "blog_id": blog_id,
            "url": blog.get("url"),
            "post_count": (blog.get("posts") or {}).get("totalItems"),
        },
    )


def _to_post_item(blog_id: str, parent_id: str, post: dict[str, Any]) -> SourceItem:
    """Map a Blogger post row to a leaf ``SourceItem`` for the picker."""
    post_id = str(post["id"])
    return SourceItem(
        external_id=_post_id(blog_id, post_id),
        display_name=post.get("title") or f"(untitled post {post_id})",
        parent_id=parent_id,
        is_container=False,
        is_leaf=True,
        metadata={
            "blog_id": blog_id,
            "post_id": post_id,
            "updated": post.get("updated"),
            "published": post.get("published"),
            "url": post.get("url"),
        },
    )


# ── Runtime objects ──────────────────────────────────────────────────────


class BlogspotBrowser:
    """Picker-time browsing of public Blogger blogs.

    Built by ``BlogspotProvider.for_browse``. ``list_items(None)`` returns one
    container per configured blog URL; ``list_items("blog:{id}")`` returns one
    page of that blog's posts, newest-updated first, plus Blogger's
    ``nextPageToken`` so the picker can fetch more on demand.
    """

    def __init__(self, config: BlogspotBrowseConfig) -> None:
        self.config = config

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        async with _make_client() as client:
            if parent_id is None:
                blogs = await _fetch_blogs(
                    client, self.config.api_key, self.config.blog_url_list
                )
                return SourcePage(
                    items=[_to_blog_item(blog) for blog in blogs],
                    next_cursor=None,
                )

            blog_id = _parse_blog_container_id(parent_id)
            if blog_id is None:
                return SourcePage(items=[], next_cursor=None)

            rows, next_token = await _list_posts_page(
                client, self.config.api_key, blog_id, cursor
            )
            return SourcePage(
                items=[_to_post_item(blog_id, parent_id, row) for row in rows],
                next_cursor=next_token,
            )


class BlogspotSource:
    """Ingest-time access to public Blogger blogs.

    Built by ``BlogspotProvider.for_ingest``. Each poll walks the selected
    blogs' post listings and emits an event per post whose ``updated`` has
    changed since the last emit. ``_fingerprints`` caches those values (also
    filled by ``fetch``) so the synchronous ``fingerprint()`` drift-check has
    something to read without a network call, and doubles as the re-emit
    suppressor. ``_watermarks`` records the newest ``updated`` seen per blog
    so later polls can stop walking once they reach older posts.

    Polling needs no URL resolution: picks already carry blog ids, so only
    the browser ever calls ``blogs/byurl``.
    """

    def __init__(self, config: BlogspotDatasetConfig) -> None:
        self.config = config
        self._fingerprints: dict[str, str] = {}
        self._watermarks: dict[str, str] = {}

    async def list_items(
        self, parent_id: str | None = None, cursor: str | None = None
    ) -> SourcePage:
        """Delegate to a transient ``BlogspotBrowser`` using the browse subset."""
        browser = BlogspotBrowser(
            BlogspotBrowseConfig.model_validate(self.config.model_dump())
        )
        return await browser.list_items(parent_id, cursor)

    @asynccontextmanager
    async def fetch(self, external_id: str) -> AsyncIterator[IngestFile]:
        """Download a post's HTML body to a tempfile and yield it.

        Caches the post's ``updated`` as a fingerprint on the way.
        """
        blog_id, post_id = _parse_post_id(external_id)
        # Scope the client to the request — closed before the (slow) ingest.
        async with _make_client() as client:
            post = await _get(
                client, self.config.api_key, f"/blogs/{blog_id}/posts/{post_id}"
            )

        body: str = post.get("content") or ""
        title: str = post.get("title") or ""
        updated = post.get("updated")
        if updated:
            self._fingerprints[external_id] = updated

        # {slug}_{postId}.html — the post id disambiguates posts that share a
        # title. Full identity travels in metadata.
        filename = f"{_slugify(title)}_{post_id}.html"

        fd, tmp_str = tempfile.mkstemp(
            prefix=f"blogspot_{blog_id}_{post_id}_", suffix=".html"
        )
        os.close(fd)
        tmp_path = Path(tmp_str)
        tmp_path.write_text(body, encoding="utf-8")
        try:
            yield IngestFile(
                path=tmp_path,
                filename=filename,
                file_size=tmp_path.stat().st_size,
                metadata={
                    "source": BlogspotProvider.NAME,
                    "blog_id": blog_id,
                    "post_id": post_id,
                    "title": title,
                    "url": post.get("url"),
                    # Datetimes, not raw strings: the vector store turns each
                    # into an ISO value plus a filterable epoch int. The
                    # fingerprint above still uses the raw `updated`.
                    "updated": parse_datetime(updated),
                    "published": parse_datetime(post.get("published")),
                    "tags": post.get("labels"),
                    "author": (post.get("author") or {}).get("displayName"),
                },
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    def fingerprint(self, external_id: str) -> str:
        """Return the cached ``updated`` timestamp for a post.

        The cache is filled by ``change_stream`` polls and ``fetch``. A miss
        (e.g. right after restart, before the first poll) raises ``OSError``,
        which the ingestion manager treats as a best-effort skip — it
        proceeds with the job's recorded fingerprint.
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
        """Poll the selected blogs every ``poll_interval_seconds``.

        The manager supplies the dataset's pick ids from the selection table.
        Ids are self-describing: ``blog:{id}`` is a whole-blog subscription
        that expands to every post in that blog (and keeps picking up posts
        published later), while ``{blogId}:{postId}`` is a single post. Both
        kinds resolve against the same per-blog listing walk, so a whole-blog
        pick costs no more requests than a handful of individual ones.
        """
        return self._change_stream_impl(selected_ids)

    async def _change_stream_impl(
        self, selected_ids: list[str]
    ) -> AsyncIterator[SourceChangeEvent]:
        whole_blogs, posts_by_blog = self._group_picks(selected_ids)
        blog_ids = sorted(whole_blogs | set(posts_by_blog))

        polls = 0

        # One client for the life of the stream; closed when the consuming
        # task is cancelled and the generator unwinds.
        async with _make_client() as client:
            while True:
                if polls and polls % FULL_SWEEP_EVERY_POLLS == 0:
                    # Re-emit everything next walk so FAILED jobs re-queue.
                    self._fingerprints.clear()
                    self._watermarks.clear()

                for blog_id in blog_ids:
                    try:
                        async for event in self._poll_blog(
                            client,
                            blog_id,
                            whole_blog=blog_id in whole_blogs,
                            picked_posts=posts_by_blog.get(blog_id, set()),
                        ):
                            yield event
                    except (httpx.HTTPError, SourceError, ValueError) as e:
                        logger.warning(
                            "Blogspot poll failed for blog %s: %s", blog_id, e
                        )
                polls += 1
                await asyncio.sleep(self.config.poll_interval_seconds)

    @staticmethod
    def _group_picks(
        selected_ids: list[str],
    ) -> tuple[set[str], dict[str, set[str]]]:
        """Split picks into whole-blog subscriptions and per-blog post ids.

        A blog covered by a whole-blog pick drops its individual post picks —
        they are already covered, and keeping them would make the scope test
        ambiguous. Malformed ids are skipped (and logged) so one bad entry
        can't abort the whole poll.
        """
        whole_blogs: set[str] = set()
        posts_by_blog: dict[str, set[str]] = {}

        for item_id in selected_ids:
            blog_id = _parse_blog_container_id(item_id)
            if blog_id is not None:
                whole_blogs.add(blog_id)
                continue
            try:
                blog_id, post_id = _parse_post_id(item_id)
            except ValueError:
                logger.warning("Skipping malformed selected id: %r", item_id)
                continue
            posts_by_blog.setdefault(blog_id, set()).add(post_id)

        for blog_id in whole_blogs:
            posts_by_blog.pop(blog_id, None)
        return whole_blogs, posts_by_blog

    async def _poll_blog(
        self,
        client: httpx.AsyncClient,
        blog_id: str,
        whole_blog: bool,
        picked_posts: set[str],
    ) -> AsyncIterator[SourceChangeEvent]:
        """Walk one blog's post listing and emit events for changed posts.

        The listing is requested newest-updated first, so once it reaches a
        post no newer than the previous walk's newest, everything after it is
        older still and the walk stops. The first walk (no watermark) pages
        through the whole blog to establish the baseline — cheap, because
        bodies are not fetched.

        Posts unchanged since the last emit are skipped rather than re-emitted:
        the scanner loads its dedup map once per source task, so re-emitting a
        large blog every poll would cost a DB read per post indefinitely.
        """
        watermark = self._watermarks.get(blog_id)
        newest: str | None = None
        page_token: str | None = None

        while True:
            rows, page_token = await _list_posts_page(
                client, self.config.api_key, blog_id, page_token
            )
            if not rows:
                break

            descending = self._is_descending(rows)
            reached_watermark = False

            for row in rows:
                updated = row.get("updated")
                if not updated:
                    continue
                if newest is None or updated > newest:
                    newest = updated

                # Everything from here on is older than the last walk saw.
                if watermark is not None and updated <= watermark:
                    reached_watermark = True
                    if descending:
                        break
                    continue

                post_id = str(row["id"])
                if not whole_blog and post_id not in picked_posts:
                    continue

                external_id = _post_id(blog_id, post_id)
                if self._fingerprints.get(external_id) == updated:
                    continue
                self._fingerprints[external_id] = updated
                yield SourceChangeEvent(
                    event_type="updated",
                    external_id=external_id,
                    fingerprint=updated,
                )

            # Only trust the early stop when the page really is ordered
            # newest-first; otherwise keep paging and rely on the per-post
            # watermark test above.
            if reached_watermark and descending:
                break
            if not page_token:
                break

        if newest is not None:
            self._watermarks[blog_id] = newest

    @staticmethod
    def _is_descending(rows: list[dict[str, Any]]) -> bool:
        """Whether a page is ordered newest-``updated``-first."""
        stamps = [row.get("updated") for row in rows if row.get("updated")]
        return all(a >= b for a, b in zip(stamps, stamps[1:], strict=False))


class BlogspotProvider:
    """Registry description and factories for the Blogspot source.

    Exposes metadata, the browse/dataset config schemas, and factories that
    build a ``BlogspotBrowser`` or ``BlogspotSource`` from a raw config dict.
    Both validators hit the live Blogger API so a bad key or an unreachable
    blog fails fast instead of at first ingest.
    """

    NAME = "blogspot"

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return "Blogspot / Blogger source (public blogs, Blogger API v3)"

    @classmethod
    def icon(cls) -> str:
        return "✍️"

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    def browse_schema(cls) -> dict[str, Any]:
        return BlogspotBrowseConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return BlogspotDatasetConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    def selection_covers(cls, item_id: str, external_id: str) -> bool:
        """A blog pick covers every post in it; a post pick covers itself."""
        blog_id = _parse_blog_container_id(item_id)
        if blog_id is not None:
            return external_id.startswith(f"{blog_id}:")
        return external_id == item_id

    @classmethod
    async def validate_selection(cls, item_ids: list[str]) -> None:
        """No-op — post and blog existence is not probed at selection time.

        The picker only surfaces existing blogs and posts, and confirming each
        pick would mean an API round-trip per pick in the request path. Same
        stance as the WordPress source.
        """
        return None

    @classmethod
    async def validate_browse_config(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = BlogspotBrowseConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid browse configuration: {e}") from e
        await _validate_connection(cfg)

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        try:
            cfg = BlogspotDatasetConfig.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e
        await _validate_connection(cfg)

    @classmethod
    def for_browse(cls, configuration: dict[str, Any]) -> BlogspotBrowser:
        return BlogspotBrowser(BlogspotBrowseConfig.model_validate(configuration))

    @classmethod
    def for_ingest(cls, configuration: dict[str, Any]) -> BlogspotSource:
        return BlogspotSource(BlogspotDatasetConfig.model_validate(configuration))
