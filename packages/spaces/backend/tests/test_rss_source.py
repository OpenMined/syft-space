"""Tests for the RSS / Atom source.

Covers the decisions rather than the plumbing: the ``feed:`` /
``{feedHash}:{itemHash}`` id space, the guid fallback that keeps
id-less feeds (Hacker News) stable, conditional GET, the per-hop scheme
check that makes HTTPS-only an SSRF guard, and the tolerance rules — a
``bozo`` feed with entries is still ingested, a link-only body still
becomes a titled document, and an oversized one is dropped.
"""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from syft_space.components.dataset_types.rss_chromadb import RssChromaDBDatasetType
from syft_space.components.sources.errors import SourceError
from syft_space.components.sources.rss import rss_source as rss
from syft_space.components.sources.rss.rss_source import (
    POLL_INTERVAL_CHOICES,
    RssBrowseConfig,
    RssBrowser,
    RssDatasetConfig,
    RssProvider,
    RssSource,
)

FEED_URL = "https://example.com/feed"
OTHER_URL = "https://other.example.com/rss"
CONF = {"feedUrls": FEED_URL}


def _rss(items: str, title: str = "Example Feed") -> bytes:
    return f"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>{title}</title><link>https://example.com</link>
{items}
</channel></rss>""".encode()


def _item(
    title: str = "Post",
    link: str = "https://example.com/post-1",
    body: str = "<p>Real prose here.</p>",
    guid: str = "",
    extra: str = "",
) -> str:
    guid_el = f"<guid>{guid}</guid>" if guid else ""
    return (
        f"<item><title>{title}</title><link>{link}</link>{guid_el}"
        f"<description><![CDATA[{body}]]></description>"
        f"<pubDate>Tue, 09 Sep 2026 10:00:00 GMT</pubDate>{extra}</item>"
    )


def _response(body: bytes, status: int = 200, **headers: str) -> httpx.Response:
    return httpx.Response(
        status,
        content=body,
        headers=headers,
        request=httpx.Request("GET", FEED_URL),
    )


def _serve(handler) -> httpx.AsyncClient:
    """A client with no base URL, so absolute feed URLs route unchanged."""
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    )


def _always(body: bytes, **headers: str):
    return lambda request: _response(body, **headers)


def _patch_client(monkeypatch, handler) -> None:
    monkeypatch.setattr(rss, "_make_client", lambda: _serve(handler))


# ── configuration ────────────────────────────────────────────────────────


class TestFeedUrlParsing:
    def test_single_url(self):
        assert RssBrowseConfig.model_validate(CONF).feed_url_list == [FEED_URL]

    def test_comma_and_newline_separated(self):
        cfg = RssBrowseConfig.model_validate({"feedUrls": f"{FEED_URL},\n{OTHER_URL}"})
        assert cfg.feed_url_list == [FEED_URL, OTHER_URL]

    def test_trailing_slash_is_normalized(self):
        cfg = RssBrowseConfig.model_validate({"feedUrls": f"{FEED_URL}/"})
        assert cfg.feed_url_list == [FEED_URL]

    def test_duplicates_are_dropped_preserving_order(self):
        cfg = RssBrowseConfig.model_validate(
            {"feedUrls": f"{OTHER_URL}, {FEED_URL}, {OTHER_URL}"}
        )
        assert cfg.feed_url_list == [OTHER_URL, FEED_URL]

    def test_an_empty_list_is_rejected(self):
        with pytest.raises(ValidationError):
            RssBrowseConfig.model_validate({"feedUrls": " , "})

    @pytest.mark.parametrize(
        "url",
        ["http://example.com/feed", "file:///etc/passwd", "https://"],
        ids=["plain http", "file", "no host"],
    )
    def test_non_https_is_refused_at_config_time(self, url):
        with pytest.raises(ValidationError):
            RssBrowseConfig.model_validate({"feedUrls": url})


class TestPollInterval:
    def test_defaults_to_an_hour(self):
        assert RssDatasetConfig.model_validate(CONF).poll_interval_seconds == 3600

    def test_the_choices_are_offered_in_the_schema(self):
        schema = RssProvider.configuration_schema()
        assert schema["properties"]["pollIntervalSeconds"]["enum"] == (
            POLL_INTERVAL_CHOICES
        )

    def test_an_off_list_interval_is_refused(self):
        with pytest.raises(ValidationError):
            RssDatasetConfig.model_validate({**CONF, "pollIntervalSeconds": 77})


# ── id space ─────────────────────────────────────────────────────────────


class TestIdSpace:
    def test_a_feed_id_round_trips(self):
        container = rss._feed_container_id(FEED_URL)
        assert container.startswith("feed:")
        assert rss._parse_feed_container_id(container) == rss._hash(FEED_URL)

    def test_an_item_id_carries_its_feed(self):
        item_id = rss._item_id(FEED_URL, "guid-1")
        feed_hash, item_hash = rss._parse_item_id(item_id)
        assert feed_hash == rss._hash(FEED_URL)
        assert item_hash == rss._hash("guid-1")

    def test_a_feed_id_is_not_a_valid_item_id(self):
        with pytest.raises(ValueError):
            rss._parse_item_id(rss._feed_container_id(FEED_URL))

    def test_two_feeds_never_share_an_item_id(self):
        assert rss._item_id(FEED_URL, "g") != rss._item_id(OTHER_URL, "g")

    def test_the_fingerprint_is_the_item_hash(self):
        source = RssSource(RssDatasetConfig.model_validate(CONF))
        item_id = rss._item_id(FEED_URL, "guid-1")
        assert source.fingerprint(item_id) == rss._hash("guid-1")


class TestEntryGuid:
    def test_id_wins(self):
        assert rss._entry_guid({"id": "urn:1", "link": "https://x"}) == "urn:1"

    def test_link_is_the_fallback(self):
        """Hacker News items carry no <guid>, so the link is the identity."""
        assert rss._entry_guid({"link": "https://x/1"}) == "https://x/1"

    def test_title_and_date_are_the_last_resort(self):
        guid = rss._entry_guid({"title": "T", "published": "Tue, 09 Sep 2026"})
        assert guid == "T|Tue, 09 Sep 2026"


class TestSelectionCovers:
    def test_a_feed_pick_covers_its_items(self):
        container = rss._feed_container_id(FEED_URL)
        item_id = rss._item_id(FEED_URL, "g")
        assert RssProvider.selection_covers(container, item_id)

    def test_a_feed_pick_does_not_cover_another_feed(self):
        container = rss._feed_container_id(FEED_URL)
        assert not RssProvider.selection_covers(container, rss._item_id(OTHER_URL, "g"))

    def test_an_item_pick_covers_only_itself(self):
        item_id = rss._item_id(FEED_URL, "g")
        assert RssProvider.selection_covers(item_id, item_id)
        assert not RssProvider.selection_covers(
            item_id, rss._item_id(FEED_URL, "other")
        )


class TestGroupPicks:
    def test_a_whole_feed_pick_absorbs_its_item_picks(self):
        container = rss._feed_container_id(FEED_URL)
        item_id = rss._item_id(FEED_URL, "g")
        whole, items = RssSource._group_picks([container, item_id])
        assert whole == {rss._hash(FEED_URL)} and items == {}

    def test_item_picks_group_by_feed(self):
        a, b = rss._item_id(FEED_URL, "g1"), rss._item_id(OTHER_URL, "g2")
        whole, items = RssSource._group_picks([a, b])
        assert whole == set()
        assert items == {rss._hash(FEED_URL): {a}, rss._hash(OTHER_URL): {b}}

    def test_a_malformed_pick_is_skipped_not_fatal(self):
        item_id = rss._item_id(FEED_URL, "g")
        whole, items = RssSource._group_picks(["garbage", item_id])
        assert items == {rss._hash(FEED_URL): {item_id}}


# ── fetch and parse ──────────────────────────────────────────────────────


class TestFetchFeed:
    async def test_a_feed_parses_into_entries(self):
        async with _serve(_always(_rss(_item()))) as client:
            feed = await rss._fetch_feed(client, FEED_URL)
        assert feed.title == "Example Feed" and len(feed.entries) == 1

    async def test_validators_are_sent_and_a_304_means_unchanged(self):
        seen: dict[str, str] = {}

        def handler(request):
            seen.update(request.headers)
            return _response(b"", status=304)

        async with _serve(handler) as client:
            feed = await rss._fetch_feed(
                client,
                FEED_URL,
                etag='W/"abc"',
                modified="Mon, 08 Sep 2026 00:00:00 GMT",
            )
        assert feed.unchanged and feed.entries == []
        assert seen["if-none-match"] == 'W/"abc"'
        assert seen["if-modified-since"] == "Mon, 08 Sep 2026 00:00:00 GMT"

    async def test_the_validators_come_back_for_the_next_poll(self):
        handler = _always(
            _rss(_item()),
            etag='W/"v2"',
            **{"last-modified": "Tue, 09 Sep 2026 10:00:00 GMT"},
        )
        async with _serve(handler) as client:
            feed = await rss._fetch_feed(client, FEED_URL)
        assert feed.etag == 'W/"v2"'
        assert feed.modified == "Tue, 09 Sep 2026 10:00:00 GMT"

    async def test_an_https_redirect_is_followed(self):
        def handler(request):
            if request.url.path == "/feed":
                return httpx.Response(
                    301,
                    headers={"location": "https://example.com/feed2"},
                    request=request,
                )
            return _response(_rss(_item()))

        async with _serve(handler) as client:
            feed = await rss._fetch_feed(client, FEED_URL)
        assert len(feed.entries) == 1

    async def test_a_redirect_to_http_is_refused_before_it_is_requested(self):
        """The check is per hop: inspecting ``history`` afterwards is too late."""
        requested: list[str] = []

        def handler(request):
            requested.append(str(request.url))
            return httpx.Response(
                302,
                headers={"location": "http://169.254.169.254/latest/meta-data/"},
                request=request,
            )

        async with _serve(handler) as client:
            with pytest.raises(SourceError, match="https"):
                await rss._fetch_feed(client, FEED_URL)
        assert requested == [FEED_URL]

    async def test_a_redirect_loop_stops(self):
        def handler(request):
            return httpx.Response(302, headers={"location": FEED_URL}, request=request)

        async with _serve(handler) as client:
            with pytest.raises(SourceError, match="redirects"):
                await rss._fetch_feed(client, FEED_URL)

    async def test_a_redirect_without_a_location_is_an_error(self):
        async with _serve(lambda r: httpx.Response(301, request=r)) as client:
            with pytest.raises(SourceError, match="location"):
                await rss._fetch_feed(client, FEED_URL)

    @pytest.mark.parametrize(
        ("status", "expected"), [(404, 404), (403, 403), (500, 502)]
    )
    async def test_an_http_error_maps_to_a_status(self, status, expected):
        async with _serve(lambda r: _response(b"", status=status)) as client:
            with pytest.raises(SourceError) as excinfo:
                await rss._fetch_feed(client, FEED_URL)
        assert excinfo.value.status_code == expected

    async def test_a_transport_failure_becomes_a_source_error(self):
        def handler(request):
            raise httpx.ConnectError("no route", request=request)

        async with _serve(handler) as client:
            with pytest.raises(SourceError, match="Could not fetch"):
                await rss._fetch_feed(client, FEED_URL)


class TestParseTolerance:
    def test_a_malformed_feed_with_entries_is_still_used(self):
        """A truncated feed is normal; entries that parsed are usable."""
        truncated = _rss(_item()).replace(b"</channel></rss>", b"")
        feed = rss._parse_feed(FEED_URL, _response(truncated))
        assert len(feed.entries) == 1

    @pytest.mark.parametrize(
        "body",
        [b"<html><body>hi</body></html>", b'{"items": []}', b"not xml"],
        ids=["a web page", "json", "plain text"],
    )
    def test_a_document_that_is_not_a_feed_is_an_error(self, body):
        """A web page parses cleanly into zero entries, so entry count
        alone cannot separate a mistyped URL from a quiet feed."""
        with pytest.raises(SourceError):
            rss._parse_feed(FEED_URL, _response(body))

    def test_a_feed_with_no_items_is_not_an_error(self):
        feed = rss._parse_feed(FEED_URL, _response(_rss("")))
        assert feed.entries == [] and feed.title == "Example Feed"


class TestEntryBody:
    def test_content_encoded_wins_over_the_summary(self):
        entry = {
            "content": [{"value": "<p>Full text</p>"}],
            "summary": "Excerpt…",
        }
        assert rss._entry_body(entry) == "<p>Full text</p>"

    def test_the_summary_is_used_when_there_is_no_content(self):
        assert rss._entry_body({"summary": "Excerpt"}) == "Excerpt"

    def test_an_empty_content_element_falls_through(self):
        entry = {"content": [{"value": "  "}], "summary": "Excerpt"}
        assert rss._entry_body(entry) == "Excerpt"


class TestHasProse:
    def test_prose_counts(self):
        assert rss._has_prose("<p>Some words</p>")

    def test_a_link_label_does_not(self):
        """A Hacker News body is one anchor; its label is not a document."""
        assert not rss._has_prose(
            '<a href="https://news.ycombinator.com/item?id=1">Comments</a>'
        )

    def test_markup_with_no_text_does_not(self):
        assert not rss._has_prose('<img src="x.png"/><br/>')

    def test_prose_beside_a_link_counts(self):
        assert rss._has_prose('<p>Words</p><a href="x">Comments</a>')


# ── metadata ─────────────────────────────────────────────────────────────


class TestEntryMetadata:
    def _one(self, extra: str = "", **kwargs) -> dict:
        feed = rss._parse_feed(FEED_URL, _response(_rss(_item(extra=extra, **kwargs))))
        return rss._entry_metadata(feed, feed.entries[0])

    def test_the_link_is_preserved_for_search_results(self):
        assert self._one()["url"] == "https://example.com/post-1"

    def test_the_comments_link_is_kept_separately(self):
        meta = self._one(extra="<comments>https://example.com/post-1#c</comments>")
        assert meta["comments_url"] == "https://example.com/post-1#c"

    def test_the_feed_identifies_itself(self):
        meta = self._one()
        assert meta["source"] == "rss"
        assert meta["feed_url"] == FEED_URL
        assert meta["feed_title"] == "Example Feed"

    def test_an_rfc_822_date_is_parsed(self):
        published = self._one()["published"]
        assert published is not None and published.year == 2026

    def test_categories_become_tags(self):
        meta = self._one(extra="<category>AI</category><category>ML</category>")
        assert meta["tags"] == ["AI", "ML"]

    def test_absent_fields_are_none_not_empty_strings(self):
        """``None`` is dropped by the vector store; ``''`` would be indexed."""
        meta = self._one(extra="<dc:creator></dc:creator>")
        assert meta["author"] is None and meta["tags"] is None

    def test_a_namespaced_author_is_read(self):
        feed = rss._parse_feed(
            FEED_URL,
            _response(
                _rss(_item(extra="<dc:creator>Ada</dc:creator>")).replace(
                    b'<rss version="2.0">',
                    b'<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">',
                )
            ),
        )
        assert rss._entry_metadata(feed, feed.entries[0])["author"] == "Ada"


# ── browse ───────────────────────────────────────────────────────────────


class TestBrowser:
    async def test_the_top_level_is_one_container_per_feed(self, monkeypatch):
        _patch_client(monkeypatch, _always(_rss(_item())))
        browser = RssBrowser(
            RssBrowseConfig.model_validate({"feedUrls": f"{FEED_URL}, {OTHER_URL}"})
        )

        page = await browser.list_items()

        assert [i.external_id for i in page.items] == [
            rss._feed_container_id(FEED_URL),
            rss._feed_container_id(OTHER_URL),
        ]
        assert all(i.is_container and i.is_leaf for i in page.items)
        assert page.next_cursor is None

    async def test_expanding_a_feed_lists_its_items(self, monkeypatch):
        _patch_client(monkeypatch, _always(_rss(_item(title="Hello"))))
        browser = RssBrowser(RssBrowseConfig.model_validate(CONF))

        page = await browser.list_items(rss._feed_container_id(FEED_URL))

        item = page.items[0]
        assert item.display_name == "Hello"
        assert item.parent_id == rss._feed_container_id(FEED_URL)
        assert not item.is_container

    async def test_an_unknown_parent_lists_nothing(self, monkeypatch):
        _patch_client(monkeypatch, _always(_rss(_item())))
        browser = RssBrowser(RssBrowseConfig.model_validate(CONF))

        assert (await browser.list_items("feed:deadbeef")).items == []
        assert (await browser.list_items("not-an-id")).items == []


# ── poll ─────────────────────────────────────────────────────────────────


class TestPollFeed:
    async def _poll(self, handler, source=None, **kwargs):
        source = source or RssSource(RssDatasetConfig.model_validate(CONF))
        async with _serve(handler) as client:
            return [
                event
                async for event in source._poll_feed(
                    client,
                    FEED_URL,
                    whole_feed=kwargs.pop("whole_feed", True),
                    picked_items=kwargs.pop("picked_items", set()),
                )
            ]

    async def test_a_whole_feed_pick_emits_every_item(self):
        body = _rss(
            _item(title="A", link="https://example.com/a")
            + _item(title="B", link="https://example.com/b")
        )
        events = await self._poll(_always(body))
        assert [e.event_type for e in events] == ["created", "created"]
        assert [e.metadata["title"] for e in events] == ["A", "B"]

    async def test_an_item_pick_emits_only_that_item(self):
        body = _rss(
            _item(title="A", link="https://example.com/a")
            + _item(title="B", link="https://example.com/b")
        )
        wanted = rss._item_id(FEED_URL, "https://example.com/b")
        events = await self._poll(
            _always(body), whole_feed=False, picked_items={wanted}
        )
        assert [e.external_id for e in events] == [wanted]

    async def test_a_304_emits_nothing(self):
        source = RssSource(RssDatasetConfig.model_validate(CONF))
        source._conditional[FEED_URL] = ('W/"abc"', None)
        events = await self._poll(_always(b"", status=304), source=source)
        assert events == []

    async def test_the_validators_are_remembered_between_polls(self):
        source = RssSource(RssDatasetConfig.model_validate(CONF))
        await self._poll(_always(_rss(_item()), etag='W/"v1"'), source=source)
        assert source._conditional[FEED_URL] == ('W/"v1"', None)

    async def test_a_link_only_item_is_still_emitted(self):
        """Subscribing to Hacker News must not yield an empty dataset."""
        body = _rss(
            _item(body='<a href="https://news.ycombinator.com/item?id=1">Comments</a>')
        )
        events = await self._poll(_always(body))
        assert len(events) == 1 and events[0].metadata["title"] == "Post"

    async def test_an_item_with_neither_prose_nor_a_title_is_skipped(self):
        body = _rss(f"<item><link>https://example.com/x</link>{''}</item>")
        assert await self._poll(_always(body)) == []

    async def test_an_oversized_body_is_skipped(self, monkeypatch):
        monkeypatch.setattr(rss, "MAX_BODY_BYTES", 100)
        events = await self._poll(_always(_rss(_item(body="<p>" + "x" * 200))))
        assert events == []

    async def test_only_the_newest_items_are_taken(self, monkeypatch):
        monkeypatch.setattr(rss, "MAX_ITEMS_PER_POLL", 2)
        body = _rss(
            "".join(
                _item(title=str(n), link=f"https://example.com/{n}") for n in range(5)
            )
        )
        events = await self._poll(_always(body))
        assert [e.metadata["title"] for e in events] == ["0", "1"]

    async def test_a_re_emitted_item_keeps_its_fingerprint(self):
        """Append-only: the same item polled twice is seen as unchanged."""
        handler = _always(_rss(_item()))
        first = await self._poll(handler)
        second = await self._poll(handler)
        assert first[0].fingerprint == second[0].fingerprint


class TestPollErrorIsolation:
    async def test_one_bad_feed_does_not_stop_the_other(self, monkeypatch):
        def handler(request):
            if "other" in str(request.url):
                return _response(b"", status=500)
            return _response(_rss(_item(title="Good")))

        _patch_client(monkeypatch, handler)
        source = RssSource(
            RssDatasetConfig.model_validate({"feedUrls": f"{OTHER_URL}, {FEED_URL}"})
        )
        picks = [
            rss._feed_container_id(OTHER_URL),
            rss._feed_container_id(FEED_URL),
        ]

        events = []
        async for event in source._change_stream_impl(picks):
            events.append(event)
            if len(events) == 1:
                break

        assert events[0].metadata["title"] == "Good"


# ── ingest ───────────────────────────────────────────────────────────────


class TestFetch:
    async def _document(self, body: str, monkeypatch) -> tuple[str, str]:
        _patch_client(monkeypatch, _always(_rss(_item(title="Hello", body=body))))
        source = RssSource(RssDatasetConfig.model_validate(CONF))
        external_id = rss._item_id(FEED_URL, "https://example.com/post-1")
        async with source.fetch(external_id) as file:
            return file.path.read_text(), file.filename

    async def test_the_title_becomes_the_heading_above_the_body(self, monkeypatch):
        document, _ = await self._document("<p>Words</p>", monkeypatch)
        assert document == "<h1>Hello</h1>\n<p>Words</p>"

    async def test_a_link_only_body_is_left_out(self, monkeypatch):
        """The title is still searchable; the anchor would be feed-wide noise."""
        document, _ = await self._document('<a href="x">Comments</a>', monkeypatch)
        assert document == "<h1>Hello</h1>"

    async def test_the_file_is_html_so_the_chunker_splits_it(self, monkeypatch):
        """``.txt`` and ``.json`` take a fast path that never chunks."""
        _, filename = await self._document("<p>Words</p>", monkeypatch)
        assert filename.endswith(".html")
        assert filename.startswith("hello_")

    async def test_the_tempfile_is_removed_afterwards(self, monkeypatch):
        _patch_client(monkeypatch, _always(_rss(_item())))
        source = RssSource(RssDatasetConfig.model_validate(CONF))
        external_id = rss._item_id(FEED_URL, "https://example.com/post-1")

        async with source.fetch(external_id) as file:
            path = file.path
        assert not path.exists()

    async def test_a_cold_fetch_re_finds_the_item_in_its_feed(self, monkeypatch):
        """Reached when the process restarted between emit and fetch."""
        _patch_client(monkeypatch, _always(_rss(_item())))
        source = RssSource(RssDatasetConfig.model_validate(CONF))
        assert source._bodies == {}

        external_id = rss._item_id(FEED_URL, "https://example.com/post-1")
        async with source.fetch(external_id) as file:
            assert file.external_id == external_id

    async def test_an_item_that_fell_out_of_the_window_is_an_error(self, monkeypatch):
        _patch_client(monkeypatch, _always(_rss(_item())))
        source = RssSource(RssDatasetConfig.model_validate(CONF))

        with pytest.raises(SourceError, match="no archive"):
            async with source.fetch(rss._item_id(FEED_URL, "gone")):
                pass

    async def test_an_item_from_an_unconfigured_feed_is_an_error(self, monkeypatch):
        _patch_client(monkeypatch, _always(_rss(_item())))
        source = RssSource(RssDatasetConfig.model_validate(CONF))

        with pytest.raises(SourceError, match="No configured feed"):
            async with source.fetch(rss._item_id(OTHER_URL, "g")):
                pass


# ── provider and binding ─────────────────────────────────────────────────


class TestProvider:
    def test_it_is_registered_and_enabled(self):
        from syft_space.components.sources.registry import (
            SOURCE_REGISTRY,
            register_builtin_sources,
        )

        register_builtin_sources()
        provider = SOURCE_REGISTRY.get("rss")
        assert provider is RssProvider and provider.enabled()

    def test_browse_asks_only_for_urls(self):
        assert list(RssProvider.browse_schema()["properties"]) == ["feedUrls"]

    def test_no_credential_is_asked_for(self):
        """Public feeds only; a private feed carries its token in the URL."""
        assert not {"apiKey", "token", "password"} & set(
            RssProvider.configuration_schema()["properties"]
        )

    async def test_validating_the_connection_fetches_every_feed(self, monkeypatch):
        requested: list[str] = []

        def handler(request):
            requested.append(str(request.url))
            return _response(_rss(_item()))

        _patch_client(monkeypatch, handler)
        await RssProvider.validate_configuration(
            {"feedUrls": f"{FEED_URL}, {OTHER_URL}"}
        )
        assert requested == [FEED_URL, OTHER_URL]

    async def test_an_empty_feed_still_validates(self, monkeypatch):
        """A feed between publications is configured correctly, just quiet."""
        _patch_client(monkeypatch, _always(_rss("")))
        await RssProvider.validate_configuration(CONF)

    async def test_an_unreachable_feed_fails_validation(self, monkeypatch):
        _patch_client(monkeypatch, _always(b"", status=404))
        with pytest.raises(SourceError):
            await RssProvider.validate_configuration(CONF)


class TestBinding:
    def test_it_is_registered(self):
        from syft_space.components.dataset_types import register_builtin_types
        from syft_space.components.dataset_types.registry import DatasetTypeRegistry

        registry = DatasetTypeRegistry()
        register_builtin_types(registry)
        assert registry.get_dataset_type("rss") is RssChromaDBDatasetType

    def test_the_flat_config_splits_along_the_two_axes(self):
        source_cfg, store_cfg = RssChromaDBDatasetType.split_config(
            {
                "collectionName": "feeds",
                "httpPort": 8123,
                "feedUrls": FEED_URL,
                "pollIntervalSeconds": 900,
            }
        )
        assert source_cfg == {"feed_urls": FEED_URL, "poll_interval_seconds": 900}
        assert store_cfg == {"collection_name": "feeds", "http_port": 8123}

    def test_the_schema_offers_both_axes(self):
        properties = RssChromaDBDatasetType.configuration_schema()["properties"]
        assert set(properties) == {
            "collectionName",
            "httpPort",
            "feedUrls",
            "pollIntervalSeconds",
        }

    async def test_a_missing_collection_name_is_generated(self, monkeypatch):
        _patch_client(monkeypatch, _always(_rss(_item())))
        configuration = {"feedUrls": FEED_URL}

        await RssChromaDBDatasetType.validate_configuration(configuration)

        assert configuration["collectionName"]

    async def test_a_bad_collection_name_is_refused(self):
        with pytest.raises(ValueError):
            await RssChromaDBDatasetType.validate_configuration(
                {"feedUrls": FEED_URL, "collectionName": "has spaces"}
            )
