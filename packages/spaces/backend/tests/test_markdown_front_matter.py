"""Parsing a Markdown front matter header and heading the body with its title."""

from __future__ import annotations

from datetime import datetime, timezone

from syft_space.components.sources.local_file.markdown_front_matter import (
    MAX_HEADER_LINES,
    article_metadata,
    front_matter_metadata,
    split_front_matter,
    with_title_heading,
)

BOM = chr(0xFEFF)

ARTICLE = (
    "---\n"
    'title: "Ramp Hits $60 Billion Valuation"\n'
    'source: "Bloomberg"\n'
    'author: "Rebecca Torrence"\n'
    'url: "https://www.bloomberg.com/news/articles/x"\n'
    'published_date: "2026-10-09T20:36:10Z"\n'
    'ingested_at: "2026-10-10T08:11:29Z"\n'
    'method: "extension"\n'
    "---\n"
    "\n"
    "# Ramp Hits $60 Billion Valuation\n"
    "\n"
    "Body text.\n"
)


# ============== split_front_matter ==============


def test_quoted_values_are_unquoted():
    fields, body = split_front_matter(ARTICLE)
    assert fields == {
        "title": "Ramp Hits $60 Billion Valuation",
        "source": "Bloomberg",
        "author": "Rebecca Torrence",
        "url": "https://www.bloomberg.com/news/articles/x",
        "published_date": "2026-10-09T20:36:10Z",
        "ingested_at": "2026-10-10T08:11:29Z",
        "method": "extension",
    }
    assert body == "\n# Ramp Hits $60 Billion Valuation\n\nBody text.\n"


def test_unquoted_values_and_dates_stay_as_written():
    text = "---\ntitle: Plain title\npublished_date: 2026-10-09T20:36:10Z\n---\nBody"
    fields, body = split_front_matter(text)
    assert fields == {
        "title": "Plain title",
        "published_date": "2026-10-09T20:36:10Z",
    }
    assert body == "Body"


def test_bom_is_skipped():
    fields, body = split_front_matter(BOM + "---\ntitle: T\n---\nBody\n")
    assert fields == {"title": "T"}
    assert body == "Body\n"


def test_crlf_line_endings():
    text = '---\r\ntitle: "T"\r\nauthor: A\r\n---\r\nBody\r\n'
    fields, body = split_front_matter(text)
    assert fields == {"title": "T", "author": "A"}
    assert body == "Body\r\n"


def test_body_starts_right_after_header():
    fields, body = split_front_matter("---\ntitle: T\n---\n# Heading\ntext")
    assert fields == {"title": "T"}
    assert body == "# Heading\ntext"


def test_header_only_file_has_empty_body():
    fields, body = split_front_matter("---\ntitle: T\n---")
    assert fields == {"title": "T"}
    assert body == ""


def test_other_flat_keys_are_kept():
    text = "---\nurl: https://x\ntype: article\nfeed_id: 42\nupdated-at: 2026\n---\nB"
    fields, _ = split_front_matter(text)
    assert fields == {
        "url": "https://x",
        "type": "article",
        "feed_id": 42,
        "updated-at": 2026,
    }


def test_no_header_is_unchanged():
    text = "# Title\n\ntitle: not a header\n"
    assert split_front_matter(text) == (None, text)


def test_unclosed_header_is_unchanged():
    text = "---\ntitle: T\n\n# Body without a closing delimiter\n"
    assert split_front_matter(text) == (None, text)


def test_horizontal_rule_later_in_text_is_not_a_header():
    text = "# Title\n\nIntro.\n\n---\n\ntitle: value\n\n---\n\nMore.\n"
    assert split_front_matter(text) == (None, text)


def test_horizontal_rule_after_header_stays_in_body():
    fields, body = split_front_matter("---\ntitle: T\n---\nA\n\n---\n\nB\n")
    assert fields == {"title": "T"}
    assert body == "A\n\n---\n\nB\n"


def test_opening_rule_and_prose_is_not_a_header():
    text = "---\n\nJust a paragraph after a rule.\n\n---\n\nMore.\n"
    assert split_front_matter(text) == (None, text)


def test_note_lines_without_known_key_are_not_a_header():
    text = "---\nNote: read this first\nWarning: draft\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_key_with_spaces_is_not_a_header():
    text = "---\ntitle: T\nPublished on: 2026-10-09\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_nested_lines_are_not_a_header():
    text = "---\ntitle: T\ntags:\n  - ml\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_delimiter_must_be_exact():
    text = "--- \ntitle: T\n---\nBody\n"
    assert split_front_matter(text) == (None, text)
    text = "---\ntitle: T\n----\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_empty_header_is_unchanged():
    text = "---\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_closing_beyond_line_limit_is_unchanged():
    lines = "".join(f"k{i}: v\n" for i in range(MAX_HEADER_LINES + 5))
    text = f"---\ntitle: T\n{lines}---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_closing_beyond_size_limit_is_unchanged():
    text = "---\ntitle: " + "x" * (70 * 1024) + "\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_flat_fallback_when_yaml_fails():
    # Unbalanced inner quotes are invalid YAML; the flat parser still reads it.
    text = '---\ntitle: "He said "hi" today"\nauthor: A\n---\nBody'
    fields, body = split_front_matter(text)
    assert fields == {"title": 'He said "hi" today', "author": "A"}
    assert body == "Body"


def test_yaml_flow_list_and_empty_value():
    text = "---\ntitle: T\ntags: [ml, nlp]\ncategory:\n---\nBody"
    fields, _ = split_front_matter(text)
    assert fields == {"title": "T", "tags": ["ml", "nlp"], "category": None}


# ============== front_matter_metadata ==============


def test_metadata_keys_are_prefixed_and_sanitised():
    out = front_matter_metadata(
        {"title": "T", "Published-Date": "2026", "feed id": 7, "Draft": True}
    )
    assert out == {
        "doc_title": "T",
        "doc_published_date": "2026",
        "doc_feed_id": 7,
        "doc_draft": True,
    }


def test_metadata_scalars_only():
    out = front_matter_metadata(
        {
            "tags": ["ml", "nlp", 3],
            "empty": [],
            "none": None,
            "nested": {"a": 1},
            "score": 1.5,
        }
    )
    assert out == {"doc_tags": "ml, nlp, 3", "doc_score": 1.5}


# ============== article_metadata ==============


def test_article_keys_follow_the_api_sources():
    fields, _ = split_front_matter(ARTICLE)
    assert article_metadata(fields) == {
        "title": "Ramp Hits $60 Billion Valuation",
        "url": "https://www.bloomberg.com/news/articles/x",
        "author": "Rebecca Torrence",
        "published": datetime(2026, 10, 9, 20, 36, 10, tzinfo=timezone.utc),
    }


def test_bare_publication_date_is_midnight_utc():
    out = article_metadata({"published_date": "2026-10-09"})
    assert out == {"published": datetime(2026, 10, 9, tzinfo=timezone.utc)}


def test_keys_match_case_insensitively_and_scalars_become_text():
    out = article_metadata({"Title": 1984, "AUTHOR": ["A", "B"]})
    assert out == {"title": "1984", "author": "A, B"}


def test_blank_unparseable_and_nested_values_are_left_out():
    out = article_metadata(
        {"title": "  ", "url": {"a": 1}, "author": None, "published_date": "soon"}
    )
    assert out == {}


# ============== with_title_heading ==============


def test_title_heading_is_prepended():
    assert with_title_heading("T", "\nBody\n") == "# T\n\nBody\n"


def test_title_heading_is_not_doubled():
    body = "\n# Ramp Hits $60 Billion Valuation\n\nBody text.\n"
    assert with_title_heading("Ramp Hits $60 Billion Valuation", body) == body


def test_matching_h1_with_closing_hashes_and_spacing_is_not_doubled():
    body = "#  Ramp  Hits ##\nBody"
    assert with_title_heading("Ramp Hits", body) == body


def test_different_first_heading_gets_the_title_above_it():
    assert with_title_heading("T", "# Other\nBody") == "# T\n\n# Other\nBody"
    assert with_title_heading("T", "## T\nBody") == "# T\n\n## T\nBody"


def test_blank_title_leaves_body_unchanged():
    assert with_title_heading("  ", "Body") == "Body"


def test_title_whitespace_is_collapsed():
    assert with_title_heading(" A \t B ", "") == "# A B\n\n"
