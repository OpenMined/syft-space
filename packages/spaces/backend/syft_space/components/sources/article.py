"""The HTML document an API-backed source hands to the chunker.

Title as an ``<h1>``, a byline, then the body. The heading names every
chunk of a long article; the byline puts the author, date, and tags into
the first chunk's text, where metadata alone would only be filterable.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser
from typing import Any

UNTITLED = "(untitled)"


class _TextOnly(HTMLParser):
    """Collects the text between tags; entities are decoded on the way."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Words of an HTML fragment, for sources whose titles arrive as HTML."""
    parser = _TextOnly()
    parser.feed(markup)
    parser.close()
    return "".join(parser.parts).strip()


def byline(metadata: dict[str, Any]) -> str:
    """``<p>By X. Published YYYY-MM-DD. Tags: a, b.</p>``, parts omitted
    when absent; empty when all are."""
    parts: list[str] = []
    if author := metadata.get("author"):
        parts.append(f"By {html.escape(author)}")
    if published := metadata.get("published"):
        parts.append(f"Published {published.date().isoformat()}")
    if tags := metadata.get("tags"):
        parts.append("Tags: " + ", ".join(html.escape(t) for t in tags))
    return f"<p>{'. '.join(parts)}.</p>" if parts else ""


def article_html(title: str, body: str, metadata: dict[str, Any]) -> str:
    """Assemble the document. ``title`` is text and is escaped; ``body`` is
    HTML, passed through. An empty body leaves only the heading and byline."""
    parts = [f"<h1>{html.escape(title) or UNTITLED}</h1>"]
    if line := byline(metadata):
        parts.append(line)
    if body:
        parts.append(body)
    return "\n".join(parts)
