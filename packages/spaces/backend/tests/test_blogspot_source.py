"""Tests for the Blogspot (Blogger v3) public-blog source.

Covers the parts that carry real decisions rather than plumbing: the
``blog:`` / ``{blogId}:{postId}`` id space and what a whole-blog pick
covers, multi-blog URL parsing under one API key, the poll walk's re-emit
suppression and watermark early stop, and the error branching that keeps
quota exhaustion from being reported as a bad key.
"""

from __future__ import annotations

import httpx
import pytest

from syft_space.components.dataset_types.blogspot_chromadb import (
    BlogspotChromaDBDatasetType,
)
from syft_space.components.sources.blogspot import blogspot_source as bs
from syft_space.components.sources.blogspot.blogspot_source import (
    BlogspotBrowseConfig,
    BlogspotBrowser,
    BlogspotDatasetConfig,
    BlogspotProvider,
    BlogspotSource,
)
from syft_space.components.sources.errors import (
    SourceAuthError,
    SourceError,
    SourceForbiddenError,
)

API_KEY = "AIza-test-key"
BLOG_URL = "https://example.blogspot.com"
CONF = {"blogUrls": BLOG_URL, "apiKey": API_KEY}


def _response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status, json=payload, request=httpx.Request("GET", "https://x")
    )


def _google_error(status: int, reason: str, message: str = "nope") -> httpx.Response:
    return _response(
        status, {"error": {"message": message, "errors": [{"reason": reason}]}}
    )


def _mock_client(handler) -> httpx.AsyncClient:
    """A client bound to the Blogger root but served by ``handler``."""
    return httpx.AsyncClient(
        base_url=bs.BLOGGER_API_ROOT, transport=httpx.MockTransport(handler)
    )


def _post(post_id: str, updated: str, title: str = "T") -> dict:
    return {"id": post_id, "updated": updated, "title": title}


def _blog(blog_id: str, name: str = "A Blog", url: str = BLOG_URL) -> dict:
    return {"id": blog_id, "name": name, "url": url, "posts": {"totalItems": 42}}


# ── Configuration ────────────────────────────────────────────────────────


class TestBlogUrlParsing:
    def test_single_url(self):
        cfg = BlogspotBrowseConfig.model_validate(CONF)
        assert cfg.blog_url_list == [BLOG_URL]

    def test_comma_separated_urls(self):
        cfg = BlogspotBrowseConfig.model_validate(
            {**CONF, "blogUrls": "https://a.blogspot.com, https://b.blogspot.com"}
        )
        assert cfg.blog_url_list == ["https://a.blogspot.com", "https://b.blogspot.com"]

    def test_newline_separated_urls(self):
        cfg = BlogspotBrowseConfig.model_validate(
            {**CONF, "blogUrls": "https://a.blogspot.com\nhttps://b.blogspot.com"}
        )
        assert len(cfg.blog_url_list) == 2

    def test_trailing_slash_is_normalized(self):
        cfg = BlogspotBrowseConfig.model_validate(
            {**CONF, "blogUrls": "https://a.blogspot.com/"}
        )
        assert cfg.blog_url_list == ["https://a.blogspot.com"]

    def test_duplicates_are_dropped_preserving_order(self):
        cfg = BlogspotBrowseConfig.model_validate(
            {
                **CONF,
                "blogUrls": "https://b.blogspot.com, https://a.blogspot.com, "
                "https://b.blogspot.com/",
            }
        )
        assert cfg.blog_url_list == ["https://b.blogspot.com", "https://a.blogspot.com"]

    def test_missing_scheme_is_rejected(self):
        with pytest.raises(ValueError, match="scheme"):
            BlogspotBrowseConfig.model_validate({**CONF, "blogUrls": "example.com"})

    def test_empty_url_list_is_rejected(self):
        with pytest.raises(ValueError):
            BlogspotBrowseConfig.model_validate({**CONF, "blogUrls": "  , ,  "})

    def test_api_key_is_required(self):
        with pytest.raises(ValueError):
            BlogspotBrowseConfig.model_validate({"blogUrls": BLOG_URL})


# ── Id space ─────────────────────────────────────────────────────────────


class TestIdSpace:
    def test_blog_container_round_trip(self):
        assert bs._parse_blog_container_id(bs._blog_container_id("123")) == "123"

    def test_post_id_round_trip(self):
        assert bs._parse_post_id(bs._post_id("123", "456")) == ("123", "456")

    def test_post_id_is_not_a_blog_container(self):
        assert bs._parse_blog_container_id("123:456") is None

    def test_bare_prefix_is_not_a_container(self):
        assert bs._parse_blog_container_id("blog:") is None

    @pytest.mark.parametrize("bad", ["", "123", ":456", "123:"])
    def test_malformed_post_id_raises(self, bad):
        with pytest.raises(ValueError):
            bs._parse_post_id(bad)


class TestSelectionCovers:
    def test_blog_pick_covers_its_posts(self):
        assert BlogspotProvider.selection_covers("blog:123", "123:456")

    def test_blog_pick_does_not_cover_another_blog(self):
        assert not BlogspotProvider.selection_covers("blog:123", "999:456")

    def test_blog_pick_does_not_cover_id_prefixed_blog(self):
        # "12" must not swallow blog 123's posts — the colon is what stops it.
        assert not BlogspotProvider.selection_covers("blog:12", "123:456")

    def test_post_pick_covers_itself(self):
        assert BlogspotProvider.selection_covers("123:456", "123:456")

    def test_post_pick_covers_nothing_else(self):
        assert not BlogspotProvider.selection_covers("123:456", "123:457")


class TestSlugify:
    def test_basic_title(self):
        assert bs._slugify("Hello, World!") == "hello-world"

    def test_empty_title_falls_back(self):
        assert bs._slugify("") == "untitled"

    def test_punctuation_only_falls_back(self):
        assert bs._slugify("!!! ???") == "untitled"

    def test_long_title_is_capped(self):
        slug = bs._slugify("word " * 40)
        assert len(slug) <= bs.MAX_SLUG_LENGTH
        assert not slug.endswith("-")


# ── Error mapping ────────────────────────────────────────────────────────


class TestErrorMapping:
    def test_success_passes(self):
        bs._check_response(_response(200, {}))

    def test_401_is_an_auth_error(self):
        with pytest.raises(SourceAuthError):
            bs._check_response(_google_error(401, "authError"))

    def test_bad_key_surfaces_googles_own_message(self):
        # Observed live: a bad key is 400 / "badRequest", not "keyInvalid".
        # Google's text is already actionable, so it is passed through.
        with pytest.raises(SourceError) as exc:
            bs._check_response(
                _google_error(
                    400, "badRequest", "API key not valid. Please pass a valid API key."
                )
            )
        assert "API key not valid" in str(exc.value)
        assert exc.value.status_code == 400

    def test_malformed_request_is_not_blamed_on_the_key(self):
        # badRequest is Google's generic 400 reason — a bad pageToken lands
        # here too and must not send the reader to the console.
        with pytest.raises(SourceError) as exc:
            bs._check_response(
                _google_error(400, "badRequest", "Invalid value for pageToken.")
            )
        assert "API key" not in str(exc.value)
        assert "pageToken" in str(exc.value)

    def test_403_reason_is_not_hijacked_by_badRequest(self):
        # The reason check used to run before the 403 branch, so a 403 could
        # be misreported as bad credentials.
        with pytest.raises(SourceForbiddenError) as exc:
            bs._check_response(_google_error(403, "badRequest", "blog is private"))
        assert "private" in str(exc.value)

    def test_403_api_disabled_names_the_fix(self):
        with pytest.raises(SourceForbiddenError) as exc:
            bs._check_response(_google_error(403, "accessNotConfigured"))
        assert "not enabled" in str(exc.value)

    @pytest.mark.parametrize(
        "reason", ["rateLimitExceeded", "userRateLimitExceeded", "dailyLimitExceeded"]
    )
    def test_quota_is_not_reported_as_a_key_problem(self, reason):
        with pytest.raises(SourceError) as exc:
            bs._check_response(_google_error(403, reason))
        assert not isinstance(exc.value, SourceForbiddenError | SourceAuthError)
        assert "quota" in str(exc.value).lower()

    def test_other_403_suggests_a_private_blog(self):
        with pytest.raises(SourceForbiddenError) as exc:
            bs._check_response(_google_error(403, "forbidden"))
        assert "private" in str(exc.value)

    def test_404_carries_its_status(self):
        with pytest.raises(SourceError) as exc:
            bs._check_response(_google_error(404, "notFound"))
        assert exc.value.status_code == 404

    def test_other_status_raises_http_error(self):
        with pytest.raises(httpx.HTTPStatusError):
            bs._check_response(_google_error(500, "backendError"))


# ── Browser ──────────────────────────────────────────────────────────────


class TestBrowser:
    async def test_root_resolves_each_url_to_a_blog(self, monkeypatch):
        seen: list[dict] = []

        def handler(request):
            seen.append(dict(request.url.params))
            url = request.url.params.get("url")
            return _response(200, _blog("1" if "a." in url else "2", url=url))

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        browser = BlogspotBrowser(
            BlogspotBrowseConfig.model_validate(
                {**CONF, "blogUrls": "https://a.blogspot.com,https://b.blogspot.com"}
            )
        )
        page = await browser.list_items(None)

        assert {i.external_id for i in page.items} == {"blog:1", "blog:2"}
        assert all(i.is_container and i.is_leaf for i in page.items)  # whole-blog pick
        assert page.next_cursor is None

    async def test_blog_lists_posts_with_a_cursor(self, monkeypatch):
        def handler(request):
            return _response(
                200,
                {
                    "items": [_post("10", "2024-03-01T00:00:00Z", title="Hello")],
                    "nextPageToken": "next",
                },
            )

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        browser = BlogspotBrowser(BlogspotBrowseConfig.model_validate(CONF))
        page = await browser.list_items("blog:1")

        # next_cursor is what drives the picker's "Load more".
        assert page.next_cursor == "next"
        item = page.items[0]
        assert item.external_id == "1:10"
        assert item.parent_id == "blog:1"
        assert not item.is_container

    async def test_listing_does_not_send_admin_only_filters(self, monkeypatch):
        seen: dict = {}

        def handler(request):
            seen.update(request.url.params)
            return _response(200, {"items": []})

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        browser = BlogspotBrowser(BlogspotBrowseConfig.model_validate(CONF))
        await browser.list_items("blog:1")

        # status/view need an account token; sending them would 403.
        assert "status" not in seen
        assert "view" not in seen
        assert seen["orderBy"] == "updated"
        assert seen["fetchBodies"] == "false"

    async def test_unknown_parent_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            bs, "_make_client", lambda: _mock_client(lambda r: _response(200, {}))
        )
        browser = BlogspotBrowser(BlogspotBrowseConfig.model_validate(CONF))
        page = await browser.list_items("nonsense")
        assert page.items == [] and page.next_cursor is None

    async def test_untitled_post_stays_identifiable(self, monkeypatch):
        def handler(request):
            return _response(
                200, {"items": [_post("10", "2024-03-01T00:00:00Z", title="")]}
            )

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        browser = BlogspotBrowser(BlogspotBrowseConfig.model_validate(CONF))
        page = await browser.list_items("blog:1")
        assert "10" in page.items[0].display_name

    async def test_missing_blog_is_explained(self, monkeypatch):
        def handler(request):
            return _google_error(404, "notFound")

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        with pytest.raises(ValueError) as exc:
            await BlogspotProvider.validate_browse_config(CONF)
        assert "No public Blogger blog" in str(exc.value)

    async def test_every_configured_url_is_checked(self, monkeypatch):
        seen: list[str] = []

        def handler(request):
            url = request.url.params.get("url")
            seen.append(url)
            return _response(200, _blog("1", url=url))

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        await BlogspotProvider.validate_browse_config(
            {**CONF, "blogUrls": "https://a.blogspot.com,https://b.blogspot.com"}
        )
        assert sorted(seen) == ["https://a.blogspot.com", "https://b.blogspot.com"]

    async def test_all_bad_urls_are_reported_at_once(self, monkeypatch):
        def handler(request):
            url = request.url.params.get("url")
            if "good" in url:
                return _response(200, _blog("1", url=url))
            return _google_error(404, "notFound")

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        with pytest.raises(ValueError) as exc:
            await BlogspotProvider.validate_browse_config(
                {
                    **CONF,
                    "blogUrls": "https://good.blogspot.com,https://bad1.blogspot.com,"
                    "https://bad2.blogspot.com",
                }
            )
        message = str(exc.value)
        # Both bad URLs named, so they can be fixed in one pass.
        assert "bad1.blogspot.com" in message
        assert "bad2.blogspot.com" in message
        assert "good.blogspot.com" not in message

    async def test_key_level_failure_is_not_repeated_per_blog(self, monkeypatch):
        # Every URL fails identically, so the key is the problem — the picker
        # should say so once, not list the same error N times.
        def handler(request):
            return _google_error(403, "accessNotConfigured")

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        with pytest.raises(SourceForbiddenError) as exc:
            await BlogspotProvider.validate_browse_config(
                {**CONF, "blogUrls": "https://a.blogspot.com,https://b.blogspot.com"}
            )
        assert str(exc.value).count("not enabled") == 1

    async def test_bad_key_surfaces_googles_message(self, monkeypatch):
        def handler(request):
            return _google_error(
                400, "badRequest", "API key not valid. Please pass a valid API key."
            )

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        with pytest.raises(SourceError) as exc:
            await BlogspotProvider.validate_browse_config(CONF)
        assert "API key not valid" in str(exc.value)

    async def test_malformed_config_is_rejected_before_any_call(self):
        with pytest.raises(ValueError):
            await BlogspotProvider.validate_browse_config({"blogUrls": BLOG_URL})


# ── Pick grouping ────────────────────────────────────────────────────────


class TestGroupPicks:
    def test_splits_blogs_and_posts(self):
        whole, by_blog = BlogspotSource._group_picks(["blog:1", "2:20", "2:21"])
        assert whole == {"1"}
        assert by_blog == {"2": {"20", "21"}}

    def test_whole_blog_absorbs_its_own_post_picks(self):
        # Keeping both would make the scope test ambiguous.
        whole, by_blog = BlogspotSource._group_picks(["blog:1", "1:10"])
        assert whole == {"1"}
        assert by_blog == {}

    def test_malformed_ids_are_skipped(self):
        whole, by_blog = BlogspotSource._group_picks(["garbage", "blog:1"])
        assert whole == {"1"}
        assert by_blog == {}


class TestIsDescending:
    def test_descending_page(self):
        assert BlogspotSource._is_descending(
            [_post("1", "2024-03-01T00:00:00Z"), _post("2", "2024-01-01T00:00:00Z")]
        )

    def test_ascending_page(self):
        assert not BlogspotSource._is_descending(
            [_post("1", "2024-01-01T00:00:00Z"), _post("2", "2024-03-01T00:00:00Z")]
        )

    def test_empty_page(self):
        assert BlogspotSource._is_descending([])


# ── Poll walk ────────────────────────────────────────────────────────────


class TestPollBlog:
    def _source(self) -> BlogspotSource:
        return BlogspotSource(BlogspotDatasetConfig.model_validate(CONF))

    async def _drain(self, source, handler, **kwargs):
        async with _mock_client(handler) as client:
            return [
                event
                async for event in source._poll_blog(
                    client,
                    "1",
                    whole_blog=kwargs.get("whole_blog", True),
                    picked_posts=kwargs.get("picked_posts", set()),
                )
            ]

    async def test_first_walk_emits_every_post(self):
        rows = [
            _post("10", "2024-03-01T00:00:00Z"),
            _post("11", "2024-02-01T00:00:00Z"),
        ]

        def handler(request):
            return _response(200, {"items": rows})

        source = self._source()
        events = await self._drain(source, handler)
        assert [e.external_id for e in events] == ["1:10", "1:11"]
        assert all(e.event_type == "updated" for e in events)
        assert source._watermarks["1"] == "2024-03-01T00:00:00Z"

    async def test_unchanged_posts_are_not_re_emitted(self):
        rows = [_post("10", "2024-03-01T00:00:00Z")]

        def handler(request):
            return _response(200, {"items": rows})

        source = self._source()
        assert len(await self._drain(source, handler)) == 1
        # The scanner's dedup map is loaded once per task, so re-emitting
        # would cost a DB read per post forever.
        assert await self._drain(source, handler) == []

    async def test_edited_post_is_re_emitted(self):
        state = {"updated": "2024-03-01T00:00:00Z"}

        def handler(request):
            return _response(200, {"items": [_post("10", state["updated"])]})

        source = self._source()
        await self._drain(source, handler)
        state["updated"] = "2024-04-01T00:00:00Z"
        events = await self._drain(source, handler)
        assert [e.fingerprint for e in events] == ["2024-04-01T00:00:00Z"]

    async def test_fingerprint_is_readable_after_a_walk(self):
        def handler(request):
            return _response(200, {"items": [_post("10", "2024-03-01T00:00:00Z")]})

        source = self._source()
        await self._drain(source, handler)
        assert source.fingerprint("1:10") == "2024-03-01T00:00:00Z"

    async def test_fingerprint_miss_raises_oserror(self):
        # The manager treats this as a best-effort skip.
        with pytest.raises(OSError):
            self._source().fingerprint("1:404")

    async def test_watermark_stops_the_walk_early(self):
        pages = {
            None: {
                "items": [_post("10", "2024-03-01T00:00:00Z")],
                "nextPageToken": "p2",
            },
            "p2": {"items": [_post("11", "2024-01-01T00:00:00Z")]},
        }
        seen: list = []

        def handler(request):
            token = request.url.params.get("pageToken")
            seen.append(token)
            return _response(200, pages[token])

        source = self._source()
        await self._drain(source, handler)
        assert seen == [None, "p2"]  # first walk pages through everything

        seen.clear()
        await self._drain(source, handler)
        # Nothing newer than the watermark, so page 2 is never requested.
        assert seen == [None]

    async def test_whole_blog_pick_takes_every_post(self):
        rows = [
            _post("10", "2024-03-01T00:00:00Z"),
            _post("11", "2024-02-01T00:00:00Z"),
        ]

        def handler(request):
            return _response(200, {"items": rows})

        events = await self._drain(self._source(), handler, whole_blog=True)
        assert len(events) == 2

    async def test_individual_picks_ignore_unpicked_posts(self):
        rows = [
            _post("10", "2024-03-01T00:00:00Z"),
            _post("11", "2024-02-01T00:00:00Z"),
        ]

        def handler(request):
            return _response(200, {"items": rows})

        events = await self._drain(
            self._source(), handler, whole_blog=False, picked_posts={"10"}
        )
        assert [e.external_id for e in events] == ["1:10"]

    async def test_posts_without_a_timestamp_are_skipped(self):
        def handler(request):
            return _response(200, {"items": [{"id": "10"}]})

        assert await self._drain(self._source(), handler) == []


# ── Credential handling ──────────────────────────────────────────────────


class TestApiKeyIsNotInUrls:
    """httpx embeds request URLs in error messages, which reach logs."""

    async def test_key_is_sent_as_a_header(self, monkeypatch):
        seen: dict = {}

        def handler(request):
            seen["params"] = dict(request.url.params)
            seen["header"] = request.headers.get("x-goog-api-key")
            seen["url"] = str(request.url)
            return _response(200, _blog("1"))

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        await BlogspotBrowser(BlogspotBrowseConfig.model_validate(CONF)).list_items(
            None
        )

        assert seen["header"] == API_KEY
        assert "key" not in seen["params"]
        assert API_KEY not in seen["url"]

    async def test_key_does_not_leak_into_error_messages(self):
        # Unmapped statuses defer to raise_for_status, which embeds the URL.
        def handler(request):
            return _response(500, {"error": {"message": "backend error"}})

        async with _mock_client(handler) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc:
                await bs._get(client, API_KEY, "/blogs/byurl", {"url": BLOG_URL})
        assert API_KEY not in str(exc.value)


# ── Retry budget ─────────────────────────────────────────────────────────


class _StopPolling(Exception):
    """Ends the poll loop from inside the patched sleep."""


class TestFullSweep:
    """A FAILED job re-queues only on re-emit, so suppression must expire."""

    async def _run_polls(self, monkeypatch, handler, polls: int) -> list[str]:
        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))

        count = {"n": 0}

        async def fake_sleep(_seconds):
            count["n"] += 1
            if count["n"] >= polls:
                raise _StopPolling

        monkeypatch.setattr(bs.asyncio, "sleep", fake_sleep)

        source = BlogspotSource(BlogspotDatasetConfig.model_validate(CONF))
        emitted: list[str] = []
        with pytest.raises(_StopPolling):
            async for event in source.change_stream(["blog:1"]):
                emitted.append(event.external_id)
        return emitted

    async def test_unchanged_post_is_suppressed_between_sweeps(self, monkeypatch):
        def handler(request):
            return _response(200, {"items": [_post("10", "2024-03-01T00:00:00Z")]})

        # Stop before the first sweep is due.
        emitted = await self._run_polls(
            monkeypatch, handler, bs.FULL_SWEEP_EVERY_POLLS - 1
        )
        assert emitted == ["1:10"]

    async def test_sweep_re_emits_so_failed_jobs_can_retry(self, monkeypatch):
        def handler(request):
            return _response(200, {"items": [_post("10", "2024-03-01T00:00:00Z")]})

        # Run one poll past the sweep boundary.
        emitted = await self._run_polls(
            monkeypatch, handler, bs.FULL_SWEEP_EVERY_POLLS + 1
        )
        assert emitted == ["1:10", "1:10"]

    async def test_sweep_also_recovers_posts_older_than_the_watermark(
        self, monkeypatch
    ):
        # A backdated post sorts below the early stop until the sweep.
        state = {"rows": [_post("10", "2024-03-01T00:00:00Z")]}

        def handler(request):
            return _response(200, {"items": state["rows"]})

        monkeypatch.setattr(bs, "_make_client", lambda: _mock_client(handler))
        source = BlogspotSource(BlogspotDatasetConfig.model_validate(CONF))

        async def walk() -> list[str]:
            async with _mock_client(handler) as client:
                return [
                    e.external_id
                    async for e in source._poll_blog(
                        client, "1", whole_blog=True, picked_posts=set()
                    )
                ]

        assert await walk() == ["1:10"]
        # Appears with an older timestamp than the watermark.
        state["rows"] = [
            _post("10", "2024-03-01T00:00:00Z"),
            _post("11", "2020-01-01T00:00:00Z"),
        ]
        assert await walk() == []  # early stop skips past it

        source._fingerprints.clear()
        source._watermarks.clear()  # what the sweep does
        assert sorted(await walk()) == ["1:10", "1:11"]


# ── Binding ──────────────────────────────────────────────────────────────


class TestBinding:
    def test_split_config_separates_the_axes(self):
        source_cfg, store_cfg = BlogspotChromaDBDatasetType.split_config(
            {**CONF, "collectionName": "blog_posts", "httpPort": 9000}
        )
        assert source_cfg["blog_urls"] == BLOG_URL
        assert source_cfg["api_key"] == API_KEY
        assert store_cfg == {"collection_name": "blog_posts", "http_port": 9000}

    def test_redaction_drops_the_key_but_keeps_the_urls(self):
        redacted = BlogspotChromaDBDatasetType.redact_configuration(
            {**CONF, "collectionName": "c"}
        )
        assert redacted["blogUrls"] == BLOG_URL  # public addresses, not secret
        assert "apiKey" not in redacted

    def test_redaction_covers_snake_case_keys(self):
        redacted = BlogspotChromaDBDatasetType.redact_configuration(
            {"blog_urls": BLOG_URL, "api_key": "k"}
        )
        assert redacted == {"blog_urls": BLOG_URL}

    def test_browse_schema_requires_only_urls_and_key(self):
        schema = BlogspotProvider.browse_schema()
        assert set(schema["required"]) == {"blogUrls", "apiKey"}

    def test_the_key_is_marked_as_a_password(self):
        props = BlogspotProvider.browse_schema()["properties"]
        assert props["apiKey"]["format"] == "password"
        assert "format" not in props["blogUrls"]

    def test_dataset_schema_adds_the_poll_interval(self):
        schema = BlogspotProvider.configuration_schema()
        assert "pollIntervalSeconds" in schema["properties"]
        # Optional, so the picker's required-fields form leaves it alone.
        assert "pollIntervalSeconds" not in schema["required"]

    async def test_validate_selection_is_a_no_op(self):
        await BlogspotProvider.validate_selection(["blog:1", "1:10"])
