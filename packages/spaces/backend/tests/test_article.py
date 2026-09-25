"""The article document shared by the API-backed sources."""

from datetime import datetime, timezone

from syft_space.components.sources.article import article_html, byline

PUBLISHED = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)


class TestByline:
    def test_all_three_parts(self):
        assert (
            byline({"author": "Ada", "published": PUBLISHED, "tags": ["AI", "ML"]})
            == "<p>By Ada. Published 2026-09-09. Tags: AI, ML.</p>"
        )

    def test_missing_parts_are_left_out(self):
        assert byline({"published": PUBLISHED}) == "<p>Published 2026-09-09.</p>"
        assert byline({"author": "Ada", "tags": None}) == "<p>By Ada.</p>"

    def test_nothing_gives_no_paragraph(self):
        assert byline({}) == ""
        assert byline({"author": None, "published": None, "tags": []}) == ""

    def test_values_are_escaped(self):
        assert byline({"author": "Ada & Bob <x>", "tags": ["R&D"]}) == (
            "<p>By Ada &amp; Bob &lt;x&gt;. Tags: R&amp;D.</p>"
        )


class TestArticleHtml:
    def test_heading_byline_body(self):
        document = article_html("Hello", "<p>Words</p>", {"author": "Ada"})
        assert document == "<h1>Hello</h1>\n<p>By Ada.</p>\n<p>Words</p>"

    def test_no_byline_when_metadata_is_bare(self):
        assert article_html("Hello", "<p>Words</p>", {}) == (
            "<h1>Hello</h1>\n<p>Words</p>"
        )

    def test_empty_body_leaves_heading_and_byline(self):
        assert article_html("Hello", "", {"author": "Ada"}) == (
            "<h1>Hello</h1>\n<p>By Ada.</p>"
        )

    def test_empty_title_is_named(self):
        assert article_html("", "<p>Words</p>", {}).startswith("<h1>(untitled)</h1>")

    def test_title_passes_through_unescaped(self):
        """Titles arrive as the source's HTML (WordPress renders them)."""
        assert article_html("A &amp; B", "", {}) == "<h1>A &amp; B</h1>"
